"""Tester at control sin regulator i PX4 styrer båten etter ønsket kurs og fart (CCOMMAND).

Kjøres i simulator-containeren mens simulatoren, PX4 og ccommand_bridge kjører
(scripts/test_control.sh gjør alt):
    ros2 run sim_interface px4_ccommand_test

Sender ønsket kurs 90° fra der båten peker og 1 m/s på /autonomy/desired/..., som ccommand_bridge
sender til PX4 som CCOMMAND. Sjekker at PX4 gir motorkraft, at båten snur til ønsket kurs og holder
farten, og at motorene stopper når de ønskede verdiene forsvinner. RC er av hele tiden.
Avslutter med kode 1 hvis noen test feiler.
"""
import math
import sys
import time

import rclpy
from px4_msgs.msg import MotorOutput
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Float64

SPEED = 1.0          # m/s, ønsket fart
TURN = math.pi / 2   # rad, ønsket kurs i forhold til der båten peker ved start
HEADING_LIMIT = math.radians(10)


def angle_diff(a, b):
    return math.atan2(math.sin(a - b), math.cos(a - b))


class Px4CcommandTest:

    def __init__(self):
        self.node = rclpy.create_node('px4_ccommand_test')
        self.motor = None
        self.values = {}
        self.failed = False
        self.desired = None  # (heading, speed), sendes hver 0,1 s når satt
        self.node.create_subscription(MotorOutput, '/fmu/out/motor_output',
                                      lambda m: setattr(self, 'motor', m), qos_profile_sensor_data)
        for topic in ('/autonomy/heading', '/autonomy/speed'):
            self.node.create_subscription(Float64, topic,
                                          lambda m, t=topic: self.values.__setitem__(t, m.data), 10)
        self.heading_pub = self.node.create_publisher(Float64, '/autonomy/desired/heading', 10)
        self.speed_pub = self.node.create_publisher(Float64, '/autonomy/desired/speed', 10)
        self.last_sent = 0.0

    def spin(self, seconds, until=None):
        """Spinner i seconds sekunder, eller til until() er sann. Gir tiden det tok, eller None."""
        start = time.monotonic()
        while time.monotonic() - start < seconds:
            rclpy.spin_once(self.node, timeout_sec=0.05)
            if self.desired and time.monotonic() - self.last_sent >= 0.1:
                self.heading_pub.publish(Float64(data=self.desired[0]))
                self.speed_pub.publish(Float64(data=self.desired[1]))
                self.last_sent = time.monotonic()
            if until and until():
                return time.monotonic() - start
        return None

    def check(self, ok, text):
        print(f'  {"✓" if ok else "✗"} {text}', flush=True)
        self.failed |= not ok

    def thrust(self):
        m = self.motor
        return max(abs(m.port_side_thrust), abs(m.starboard_thrust)) if m else 0.0

    def run(self):
        # Venter også på MotorOutput, så sjekken av om motorene står stille under ser riktig verdi.
        self.spin(5.0, until=lambda: '/autonomy/heading' in self.values and self.motor is not None)
        if '/autonomy/heading' not in self.values:
            self.check(False, 'Mangler /autonomy/heading. Kjører simulatoren?')
            return False

        # Sender fra første stund, så test_control.sh kan sjekke at PX4 tar imot CCOMMAND selv om
        # resten av kjeden ikke virker.
        print(f'Ønsket kurs {math.degrees(TURN):.0f}° fra der båten peker, {SPEED:g} m/s, RC av')
        target = self.values['/autonomy/heading'] + TURN
        idle = self.thrust() < 1.0
        self.desired = (target, SPEED)
        if not idle:
            # Ellers ser kraft som er igjen fra RC-testen ut som kraft fra CCOMMAND.
            self.spin(15.0)
            self.check(False, f'Motorene går allerede før CCOMMAND sendes ({self.thrust():g} %), så '
                              'kraft fra CCOMMAND kan ikke testes. Følger trolig av at motorene ikke '
                              'stopper når RC forsvinner.')
            self.desired = None
            return False
        took = self.spin(15.0, until=lambda: self.thrust() >= 1.0)
        if took is None:
            why = ('PX4 sender ingen MotorOutput (switch_motor_output startet?)' if self.motor is None
                   else 'PX4 gir ingen motorkraft fra CCOMMAND')
            self.check(False, f'{why} etter 15 s. PX4 trenger en mottaker for CCOMMAND og en vei fra '
                              'den til regulatorene og MotorOutput.')
            print('  ✗ Kursen nås (følger av feilen over)')
            print('  ✗ Farten holdes (følger av feilen over)')
            print('  ✗ Motorene stopper når CCOMMAND forsvinner (følger av feilen over)')
            self.desired = None
            return False
        self.check(True, f'PX4 gir motorkraft fra CCOMMAND (etter {took:.1f} s)')

        error = lambda: abs(angle_diff(self.values['/autonomy/heading'], target))  # noqa: E731
        took = self.spin(40.0, until=lambda: error() < HEADING_LIMIT)
        if took is None:
            self.check(False, f'Kursen nås ikke på 40 s (feil {math.degrees(error()):.0f}°). Sjekk '
                              'fortegnet og enheten på desired_course (kompasskurs i radianer).')
        else:
            self.check(True, f'Kursen nås innen 10° (etter {took:.1f} s)')

        self.spin(15.0)
        speed = self.values.get('/autonomy/speed', float('nan'))
        self.check(abs(speed - SPEED) <= 0.3,
                   f'Farten holdes ({speed:.2f} m/s etter 15 s til, ønsket {SPEED:g} m/s)')
        self.check(math.degrees(error()) < 15,
                   f'Kursen holdes ({math.degrees(error()):.1f}° feil)')

        print('Sikkerhet: CCOMMAND forsvinner (autonomy stopper)')
        self.desired = None
        took = self.spin(8.0, until=lambda: self.thrust() < 1.0)
        if took is None:
            self.check(False, f'Motorene går fortsatt etter 8 s uten CCOMMAND ({self.thrust():g} %).')
        else:
            # Ikke avtalt med control. Forslag: som RC, 0,5 s timeout pluss margin.
            self.check(took <= 1.5, f'Motorene stopper når CCOMMAND forsvinner (etter {took:.1f} s, '
                                    'krav 1,5 s, ikke avtalt med control ennå)')
        return not self.failed


def main():
    rclpy.init()
    test = Px4CcommandTest()
    try:
        ok = test.run()
    except KeyboardInterrupt:
        ok = False
    print('\nAlle CCOMMAND-testene bestod.' if ok else '\nNoen CCOMMAND-tester feilet (✗ over).')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
