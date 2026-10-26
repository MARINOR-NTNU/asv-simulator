"""Er simulatoren PX4 venter på i SITL: sender simulatorens IMU og GPS som HIL_SENSOR og HIL_GPS (MAVLink).

Med none_iris venter PX4 ved oppstart på en simulator på TCP 4560, og i lockstep går klokka til PX4
bare når den får HIL_SENSOR. Tidsstempelet er simuleringstiden, så PX4 følger simulatorens klokke.
Motorkommandoene kommer ikke herfra, men som MotorOutput via agenten (px4_motor_bridge).
Det PX4 sender tilbake (HEARTBEAT, HIL_ACTUATOR_CONTROLS), leses og kastes.
"""
import math
import socket

import rclpy
from pymavlink.dialects.v20 import common as mavlink
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, NavSatFix, NavSatStatus

from sim_interface.frames import enu_to_flu, rates_flu_to_frd

EARTH_RADIUS = 6378137.0
# fields_updated i HIL_SENSOR: bit 0-12 er akselerometer, gyro, kompass, trykk, differansetrykk,
# trykkhøyde og temperatur. Differansetrykk (airspeed) er utelatt, for det har ikke en båt.
FIELDS = 0x1FFF & ~(1 << 10)


def pressure_hpa(altitude):
    """Lufttrykk i standardatmosfæren (hPa) ved en høyde over havet (m)."""
    return 1013.25 * (1.0 - 2.25577e-5 * altitude) ** 5.25588


def stamp_us(stamp):
    return stamp.sec * 1_000_000 + stamp.nanosec // 1000


class Px4HilBridge(Node):

    def __init__(self):
        super().__init__('px4_hil_bridge')
        port = self.declare_parameter('port', 4560).value
        # Jordas magnetfelt i NED (gauss) der båten er. PX4 sammenligner det med sin egen modell
        # for stedet, så det må passe med GPS-posisjonen. Se config/px4_bridge.yaml.
        self.mag_ned = self.declare_parameter('mag_ned', [0.244, 0.054, -0.512]).value
        # Tidskonstant for glatting av farten fra GPS (sekunder), som i px4_seapath_bridge.
        self.tau = self.declare_parameter('tau', 0.5).value

        self.mav = mavlink.MAVLink(None, srcSystem=1, srcComponent=1)
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(('0.0.0.0', port))
        self.server.listen(1)
        self.server.setblocking(False)
        self.client = None
        self.last_sensor_us = 0

        self.altitude = 0.0
        self.origin = None
        self.last = None
        self.velocity = [0.0, 0.0, 0.0]  # nord, øst, ned
        self.create_subscription(Imu, '/autonomy/imu', self.on_imu, qos_profile_sensor_data)
        self.create_subscription(
            NavSatFix, '/autonomy/gps/fix', self.on_gps, qos_profile_sensor_data)
        self.create_timer(0.02, self.poll)
        self.get_logger().info(f'Venter på at PX4 kobler seg til på TCP {port}.')

    def poll(self):
        if self.client is None:
            try:
                self.client, _ = self.server.accept()
            except BlockingIOError:
                return
            # Uten venting, så en PX4 som henger ikke stopper noden. Er sendebufferen full,
            # henger PX4, og da kobles den fra (send under).
            self.client.setblocking(False)
            self.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.last_sensor_us = 0
            self.get_logger().info('PX4 er koblet til.')
        # Tømmer det PX4 sender, ellers blir bufferen full og PX4 stopper.
        try:
            while self.client.recv(65536):
                pass
            self.disconnect()  # recv ga b'': PX4 har lukket forbindelsen
        except BlockingIOError:
            pass
        except OSError:
            self.disconnect()

    def disconnect(self):
        if self.client is not None:
            self.client.close()
            self.client = None
            self.get_logger().info('PX4 koblet fra. Venter på ny tilkobling.')

    def send(self, msg):
        if self.client is None:
            return
        try:
            self.client.sendall(msg.pack(self.mav))
        except OSError:
            self.disconnect()

    def on_imu(self, msg):
        t = stamp_us(msg.header.stamp)
        # PX4 sin klokke kan ikke gå bakover.
        if t <= self.last_sensor_us:
            return
        self.last_sensor_us = t
        a = msg.linear_acceleration
        w = msg.angular_velocity
        q = msg.orientation
        mn, me, md = self.mag_ned
        mx, my, mz = enu_to_flu((q.x, q.y, q.z, q.w), (me, mn, -md))
        gx, gy, gz = rates_flu_to_frd(w.x, w.y, w.z)
        # FLU -> FRD: y og z snur fortegn. I ro viser akselerometeret -9,81 i z (FRD).
        self.send(self.mav.hil_sensor_encode(
            t, a.x, -a.y, -a.z, gx, gy, gz, mx, -my, -mz,
            pressure_hpa(self.altitude), 0.0, self.altitude, 20.0, FIELDS))

    def on_gps(self, fix):
        if self.origin is None:
            self.origin = fix
        north = math.radians(fix.latitude - self.origin.latitude) * EARTH_RADIUS
        east = math.radians(fix.longitude - self.origin.longitude) \
            * EARTH_RADIUS * math.cos(math.radians(self.origin.latitude))
        down = -(fix.altitude - self.origin.altitude)
        t = stamp_us(fix.header.stamp)
        if self.last is not None:
            dt = (t - self.last[0]) * 1e-6
            if dt <= 0.0:
                return
            alpha = dt / (self.tau + dt)
            for i, pos in enumerate((north, east, down)):
                self.velocity[i] += alpha * ((pos - self.last[i + 1]) / dt - self.velocity[i])
        self.last = (t, north, east, down)
        self.altitude = fix.altitude

        vn, ve, vd = self.velocity
        speed = math.hypot(vn, ve)
        # Kurs over grunn i centigrader. 65535 betyr ukjent, når båten nesten står stille.
        cog = int(math.degrees(math.atan2(ve, vn)) % 360.0 * 100) if speed > 0.05 else 65535
        fix_type = 3 if fix.status.status >= NavSatStatus.STATUS_FIX else 1
        self.send(self.mav.hil_gps_encode(
            t, fix_type, int(fix.latitude * 1e7), int(fix.longitude * 1e7),
            int(fix.altitude * 1000), 100, 100, int(speed * 100),
            int(vn * 100), int(ve * 100), int(vd * 100), cog, 10))


def main():
    rclpy.init()
    node = Px4HilBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
