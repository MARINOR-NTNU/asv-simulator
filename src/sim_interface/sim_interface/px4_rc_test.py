"""Tester control sin PX4 hele veien til motorene med virtuell RC, og skriver ✓ eller ✗ per test.

Kjøres i simulator-containeren mens simulatoren og PX4 kjører (scripts/test_control.sh gjør alt):
    ros2 run sim_interface px4_rc_test

Bruker rc_channels i px4_hil_bridge som fjernkontroll. Kanalene hos control (rcPublisher):
0 baug, 1 babord, 2 styrbord, 3 vinkel, 6 modus (SC), 7 manuell (SD). Avslutter med kode 1 hvis
noen test feiler.
"""
import math
import sys
import time

import rclpy
from px4_msgs.msg import MotorOutput
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
from rcl_interfaces.srv import SetParameters
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Float64

NEUTRAL = [1500, 1500, 1500, 1500, 1500, 1500, 1800, 1800]  # manuell motorstyring, alt i midten


def rc(**channels):
    """RC-kanaler med noen endret fra nøytral, f.eks. rc(port=1700)."""
    names = {'bow': 0, 'port': 1, 'starboard': 2, 'angle': 3}
    values = list(NEUTRAL)
    for name, value in channels.items():
        values[names[name]] = value
    return values


class Px4RcTest:

    def __init__(self):
        self.node = rclpy.create_node('px4_rc_test')
        self.motor = None
        self.motor_count = 0
        self.values = {}
        self.failed = False
        self.node.create_subscription(MotorOutput, '/fmu/out/motor_output', self.on_motor,
                                      qos_profile_sensor_data)
        for topic in ('/control/thruster/left/thrust', '/control/thruster/bow/thrust',
                      '/control/thruster/left/angle', '/autonomy/heading', '/autonomy/speed'):
            self.node.create_subscription(Float64, topic,
                                          lambda m, t=topic: self.values.__setitem__(t, m.data), 10)
        self.param_client = self.node.create_client(SetParameters, '/px4_hil_bridge/set_parameters')

    def on_motor(self, msg):
        self.motor = msg
        self.motor_count += 1

    def spin(self, seconds):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            rclpy.spin_once(self.node, timeout_sec=0.05)

    def set_rc(self, channels):
        value = ParameterValue(type=ParameterType.PARAMETER_INTEGER_ARRAY, integer_array_value=channels)
        future = self.param_client.call_async(
            SetParameters.Request(parameters=[Parameter(name='rc_channels', value=value)]))
        rclpy.spin_until_future_complete(self.node, future, timeout_sec=5.0)
        if not future.done():
            raise RuntimeError('Fikk ikke satt rc_channels i px4_hil_bridge. Kjører den?')

    def check(self, ok, text):
        print(f'  {"✓" if ok else "✗"} {text}', flush=True)
        self.failed |= not ok

    def run(self):
        if not self.param_client.wait_for_service(timeout_sec=10.0):
            print('  ✗ px4_hil_bridge svarer ikke. Start simulatoren med control:=px4.')
            return False

        print('Uten RC')
        self.set_rc([0])
        self.motor_count = 0
        self.spin(3.0)
        if self.motor_count == 0:
            self.check(False, 'Ingen MotorOutput fra PX4 uten RC (switch_motor_output startet?). '
                              'Resten av testene trenger MotorOutput.')
            return False
        m = self.motor
        zero = all(abs(v) < 1.0 for v in (m.port_side_thrust, m.starboard_thrust, m.forward_propeller_thrust))
        self.check(zero, f'MotorOutput er 0 uten RC (babord {m.port_side_thrust:g}, styrbord '
                         f'{m.starboard_thrust:g}, baug {m.forward_propeller_thrust:g})')

        print('Forover: babord og styrbord på 1700 µs')
        self.set_rc(rc(port=1700, starboard=1700))
        self.spin(2.0)
        m = self.motor
        self.check(38 <= m.port_side_thrust <= 42 and 38 <= m.starboard_thrust <= 42,
                   f'MotorOutput 40 % (babord {m.port_side_thrust:g}, styrbord {m.starboard_thrust:g})')
        left = self.values.get('/control/thruster/left/thrust', float('nan'))
        self.check(19 <= left <= 21, f'Broen gir 20 N (/control/thruster/left/thrust {left:.1f} N)')
        self.spin(13.0)
        speed = self.values.get('/autonomy/speed', float('nan'))
        self.check(1.3 <= speed <= 1.9, f'Båten går forover, ca. 1,6 m/s etter 15 s ({speed:.2f} m/s)')

        print('Sving: bare babord på 1700 µs')
        self.set_rc(rc(port=1700))
        self.spin(1.0)
        before = self.values['/autonomy/heading']
        self.spin(4.0)
        turn = math.atan2(math.sin(self.values['/autonomy/heading'] - before),
                          math.cos(self.values['/autonomy/heading'] - before))
        self.check(turn < -0.3, f'Båten svinger med klokka, mot styrbord ({turn:+.2f} rad på 4 s)')

        print('Baug: 1700 µs')
        self.set_rc(rc(bow=1700))
        self.spin(2.0)
        bow = self.values.get('/control/thruster/bow/thrust', float('nan'))
        self.check(-11 <= bow <= -9, f'Baugen skyves mot styrbord, -10 N i kontrakten ({bow:.1f} N)')

        print('Vinkel: 1750 µs')
        self.set_rc(rc(angle=1750))
        self.spin(2.0)
        angle = self.values.get('/control/thruster/left/angle', float('nan'))
        self.check(0.70 <= angle <= 0.87,
                   f'45° mot babord ({angle:.3f} rad = {math.degrees(angle):.1f}°)')

        print('Sikkerhet: RC forsvinner mens motorene går (40 %)')
        self.set_rc(rc(port=1700, starboard=1700))
        self.spin(2.0)
        self.set_rc([0])
        start = time.monotonic()
        stopped = None
        while time.monotonic() - start < 8.0:
            self.spin(0.1)
            if abs(self.motor.port_side_thrust) < 1.0 and abs(self.motor.starboard_thrust) < 1.0:
                stopped = time.monotonic() - start
                break
        if stopped is None:
            self.check(False, f'Motorene går fortsatt etter 8 s uten RC (babord '
                              f'{self.motor.port_side_thrust:g} %). switch_motor_output må sjekke at '
                              'RC-meldingen er fersk.')
        else:
            self.check(stopped <= 1.0, f'Motorene stopper når RC forsvinner (etter {stopped:.1f} s, '
                                       'krav 1 s)')
        self.set_rc([0])
        return not self.failed


def main():
    rclpy.init()
    test = Px4RcTest()
    try:
        ok = test.run()
    except KeyboardInterrupt:
        ok = False
    print('\nAlle testene bestod.' if ok else '\nNoen tester feilet (✗ over).')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
