"""Standardtester for regulatoren: sprang i kurs eller fart, med nøkkeltall, CSV og graf.

Sender ønsket kurs og fart på /autonomy/desired/{heading,speed}, som autonomy ellers gjør, og måler
hvordan båten svarer. Virker med alle regulatorer som leser kontrakten (stub_controller nå, control
sin regulator senere). Start simulatoren uten autonomy, så ingen andre sender ønskede verdier:

  ros2 launch sim_interface sim.launch.py control:=stub
  ros2 run sim_interface control_test --ros-args -p test:=heading_step -p step:=90.0

Tester:
  heading_step  holder kursen der båten peker, så sprang på step grader. Fart speed hele tiden.
  speed_step    holder kursen, fart start_speed, så sprang til speed.

Nøkkeltall (etter spranget):
  stigetid      tid fra 10 % til 90 % av spranget
  oversving     hvor langt forbi målet den går, i enheter og prosent av spranget
  tid til stabil  siste gang avviket var større enn tolerance, regnet fra spranget
  stasjonært avvik  snittavvik de siste tail sekundene (ønsket minus målt)
  motorbruk     snitt av |thrust| summert over motorene, i N

Resultatene lagres i output_dir (standard /root/results hvis den finnes, ellers mappa du står i).
"""
import csv
import json
import math
import os
import time

import rclpy
from rclpy.parameter import Parameter
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Float64

EARTH_RADIUS = 6378137.0
THRUSTERS = ('left', 'right', 'bow')


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def step_metrics(t, value, target, initial, t_step, tolerance, tail, unwrap_angle=False):
    """Nøkkeltall for et sprang fra initial til target ved t_step. Verdiene er lister med samme lengde."""
    if unwrap_angle:
        # Avvik som vinkel, så et sprang over ±180° regnes riktig.
        value = [target - wrap(target - v) for v in value]
    size = target - initial
    after = [(ti, v) for ti, v in zip(t, value) if ti >= t_step]
    if not after or size == 0:
        return {}
    sign = 1.0 if size > 0 else -1.0
    progress = [(ti, (v - initial) / size) for ti, v in after]

    def first_time(fraction):
        return next((ti - t_step for ti, p in progress if p >= fraction), None)

    t10, t90 = first_time(0.1), first_time(0.9)
    peak = max(sign * (v - target) for _, v in after)
    outside = [ti for ti, v in after if abs(target - v) > tolerance]
    settled = outside[-1] - t_step if outside else 0.0
    if outside and outside[-1] >= after[-1][0] - 1e-6:
        settled = None  # aldri stabil innenfor testen
    end = after[-1][0]
    last = [target - v for ti, v in after if ti >= end - tail]
    return {
        'stigetid_s': None if t10 is None or t90 is None else round(t90 - t10, 2),
        'oversving': round(max(0.0, peak), 3),
        'oversving_prosent': round(max(0.0, peak) / abs(size) * 100.0, 1),
        'tid_til_stabil_s': None if settled is None else round(settled, 2),
        'stasjonaert_avvik': round(sum(last) / len(last), 4) if last else None,
    }


class ControlTest(Node):

    def __init__(self):
        # Simuleringstid, så tidene stemmer også når simulatoren ikke går i sanntid.
        super().__init__('control_test', parameter_overrides=[
            Parameter('use_sim_time', Parameter.Type.BOOL, True)])
        self.test = self.declare_parameter('test', 'heading_step').value
        self.step = self.declare_parameter('step', 90.0).value          # grader (heading_step)
        self.speed = self.declare_parameter('speed', 1.0).value          # m/s
        self.start_speed = self.declare_parameter('start_speed', 0.5).value  # m/s (speed_step)
        self.settle = self.declare_parameter('settle', 15.0).value       # s før spranget
        self.duration = self.declare_parameter('duration', 40.0).value   # s etter spranget
        self.tail = self.declare_parameter('tail', 5.0).value            # s for stasjonært avvik
        default_out = '/root/results' if os.path.isdir('/root/results') else os.getcwd()
        self.output_dir = self.declare_parameter('output_dir', default_out).value
        self.label = self.declare_parameter('label', '').value
        if self.test not in ('heading_step', 'speed_step'):
            raise RuntimeError(f'Ukjent test {self.test!r}. Kjente: heading_step, speed_step')

        self.heading = self.speed_meas = self.position = None
        self.origin = None
        self.thrust = dict.fromkeys(THRUSTERS, 0.0)
        self.angle = {'left': 0.0, 'right': 0.0}
        self.rows = []
        self.t0 = self.t_step = None
        self.h0 = None
        self.done = False

        self.heading_pub = self.create_publisher(Float64, '/autonomy/desired/heading', 10)
        self.speed_pub = self.create_publisher(Float64, '/autonomy/desired/speed', 10)
        self.create_subscription(Float64, '/autonomy/heading', lambda m: setattr(self, 'heading', m.data), 10)
        self.create_subscription(Float64, '/autonomy/speed', lambda m: setattr(self, 'speed_meas', m.data), 10)
        self.create_subscription(NavSatFix, '/autonomy/gps/fix', self.on_gps, qos_profile_sensor_data)
        for side in THRUSTERS:
            self.create_subscription(Float64, f'/control/thruster/{side}/thrust',
                                     lambda m, s=side: self.thrust.__setitem__(s, m.data), 10)
        for side in ('left', 'right'):
            self.create_subscription(Float64, f'/control/thruster/{side}/angle',
                                     lambda m, s=side: self.angle.__setitem__(s, m.data), 10)
        self.create_timer(0.1, self.tick)
        self.get_logger().info(f'Venter på kurs og fart fra simulatoren ({self.test}).')

    def on_gps(self, fix):
        if self.origin is None:
            self.origin = (fix.latitude, fix.longitude)
        lat0, lon0 = self.origin
        self.position = (math.radians(fix.longitude - lon0) * EARTH_RADIUS * math.cos(math.radians(lat0)),
                         math.radians(fix.latitude - lat0) * EARTH_RADIUS)

    def setpoints(self, t):
        """Ønsket kurs (rad) og fart (m/s) ved tid t (s fra start)."""
        stepped = t >= self.settle
        if self.test == 'heading_step':
            return wrap(self.h0 + (math.radians(self.step) if stepped else 0.0)), self.speed
        return self.h0, self.speed if stepped else self.start_speed

    def tick(self):
        if self.done or self.heading is None or self.speed_meas is None:
            return
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.t0 is None:
            self.t0, self.h0 = now, self.heading
            self.get_logger().info(f'Start. Kurs nå {math.degrees(self.h0):.1f}°. Sprang etter {self.settle:.0f} s.')
        t = now - self.t0
        desired_heading, desired_speed = self.setpoints(t)
        self.heading_pub.publish(Float64(data=desired_heading))
        self.speed_pub.publish(Float64(data=desired_speed))
        if self.t_step is None and t >= self.settle:
            self.t_step = t
            self.get_logger().info('Sprang.')
        x, y = self.position or (float('nan'), float('nan'))
        self.rows.append([round(t, 3), desired_heading, self.heading, desired_speed, self.speed_meas,
                          *[self.thrust[s] for s in THRUSTERS], self.angle['left'], self.angle['right'], x, y])
        if t >= self.settle + self.duration:
            self.done = True
            self.finish()

    def finish(self):
        t = [r[0] for r in self.rows]
        if self.test == 'heading_step':
            # Målet uten wrap, så et sprang over ±180° blir riktig (step_metrics vrir målingene inn).
            target = self.h0 + math.radians(self.step)
            m = step_metrics(t, [r[2] for r in self.rows], target, self.h0, self.t_step,
                             math.radians(2.0), self.tail, unwrap_angle=True)
            for key in ('oversving', 'stasjonaert_avvik'):
                if m.get(key) is not None:
                    m[key + '_grader'] = round(math.degrees(m.pop(key)), 2)
            m.pop('oversving', None)
            m['toleranse'] = '2 grader'
        else:
            m = step_metrics(t, [r[4] for r in self.rows], self.speed, self.start_speed, self.t_step,
                             0.05 * abs(self.speed - self.start_speed), self.tail)
            m['oversving_m_s'] = m.pop('oversving', None)
            m['stasjonaert_avvik_m_s'] = m.pop('stasjonaert_avvik', None)
            m['toleranse'] = '5 % av spranget'
        after = [r for r in self.rows if r[0] >= self.t_step]
        m['motorbruk_N'] = round(sum(abs(r[5]) + abs(r[6]) + abs(r[7]) for r in after) / len(after), 2)
        m['test'] = self.test
        m['parametre'] = {'step_grader': self.step, 'speed': self.speed, 'start_speed': self.start_speed,
                          'settle_s': self.settle, 'duration_s': self.duration}

        os.makedirs(self.output_dir, exist_ok=True)
        name = f'{self.test}_{self.label + "_" if self.label else ""}{time.strftime("%Y%m%d_%H%M%S")}'
        base = os.path.join(self.output_dir, name)
        with open(base + '.csv', 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['t_s', 'onsket_kurs_rad', 'kurs_rad', 'onsket_fart_m_s', 'fart_m_s',
                        'thrust_left_N', 'thrust_right_N', 'thrust_bow_N', 'vinkel_left_rad',
                        'vinkel_right_rad', 'ost_m', 'nord_m'])
            w.writerows(self.rows)
        with open(base + '.json', 'w') as f:
            json.dump(m, f, indent=2, ensure_ascii=False)
        self.plot(base + '.png')
        self.get_logger().info('Resultat:\n' + json.dumps(m, indent=2, ensure_ascii=False))
        self.get_logger().info(f'Lagret {base}.csv, .json og .png')

    def plot(self, path):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        t = [r[0] for r in self.rows]
        fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
        ax[0].plot(t, [math.degrees(r[1]) for r in self.rows], 'k--', label='ønsket')
        ax[0].plot(t, [math.degrees(r[2]) for r in self.rows], label='målt')
        ax[0].set_ylabel('kurs [°]')
        ax[1].plot(t, [r[3] for r in self.rows], 'k--', label='ønsket')
        ax[1].plot(t, [r[4] for r in self.rows], label='målt')
        ax[1].set_ylabel('fart [m/s]')
        for i, side in enumerate(THRUSTERS):
            ax[2].plot(t, [r[5 + i] for r in self.rows], label=side)
        # Kommandoene på /control/thruster/..., før thruster_adapter og modellen begrenser dem.
        ax[2].set_ylabel('kommandert thrust [N]')
        ax[2].set_xlabel('tid [s]')
        for a in ax:
            a.axvline(self.t_step, color='grey', lw=0.8)
            a.grid(alpha=0.3)
            a.legend(loc='best', fontsize=8)
        fig.suptitle(f'{self.test}{" (" + self.label + ")" if self.label else ""}')
        fig.tight_layout()
        fig.savefig(path, dpi=110)


def main():
    rclpy.init()
    node = ControlTest()
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.1)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
