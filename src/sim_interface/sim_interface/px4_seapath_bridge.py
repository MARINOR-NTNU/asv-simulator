"""Lager control sin SeapathData fra simulatorens IMU og GPS og sender den til PX4 (uXRCE-DDS).

Erstatter seapath-driveren i PX4 når vi kjører i simulatoren.
"""
import math
import time

import rclpy
from px4_msgs.msg import SeapathData
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu, NavSatFix, NavSatStatus

from sim_interface.frames import attitude_enu_to_ned, euler_from_quaternion, rates_flu_to_frd

EARTH_RADIUS = 6378137.0


class Px4SeapathBridge(Node):

    def __init__(self):
        super().__init__('px4_seapath_bridge')
        topic = self.declare_parameter('seapath_topic', '/fmu/in/seapath_data').value
        # Tidskonstant for glatting av farten (sekunder). GPS-posisjon derivert direkte gir mye støy.
        self.tau = self.declare_parameter('tau', 0.5).value
        # Tidskonstant for middelhøyden heave regnes fra (sekunder). Må være mye lengre enn bølgeperioden.
        self.heave_tau = self.declare_parameter('heave_tau', 20.0).value
        rate = self.declare_parameter('rate', 50.0).value

        self.imu = None
        self.fix = None
        self.origin = None
        self.last = None
        self.velocity = [0.0, 0.0, 0.0]  # nord, øst, ned
        self.alt_mean = None
        self.heave = 0.0
        # Reliable fungerer både mot en reliable og en best effort leser i agenten.
        self.pub = self.create_publisher(SeapathData, topic, 10)
        self.create_subscription(
            Imu, '/autonomy/imu', lambda m: setattr(self, 'imu', m), qos_profile_sensor_data)
        self.create_subscription(
            NavSatFix, '/autonomy/gps/fix', self.on_gps, qos_profile_sensor_data)
        self.create_timer(1.0 / rate, self.publish)

    def on_gps(self, fix):
        self.fix = fix
        if self.origin is None:
            self.origin = fix
            self.alt_mean = fix.altitude
        # cos(breddegrad) regnes med startbredden. Ellers gir bevegelse nord/sør falsk fart øst/vest.
        north = math.radians(fix.latitude - self.origin.latitude) * EARTH_RADIUS
        east = math.radians(fix.longitude - self.origin.longitude) \
            * EARTH_RADIUS * math.cos(math.radians(self.origin.latitude))
        down = -(fix.altitude - self.origin.altitude)
        stamp = fix.header.stamp.sec + fix.header.stamp.nanosec * 1e-9

        if self.last is not None:
            dt = stamp - self.last[0]
            if dt <= 0.0:
                return
            alpha = dt / (self.tau + dt)
            for i, pos in enumerate((north, east, down)):
                self.velocity[i] += alpha * ((pos - self.last[i + 1]) / dt - self.velocity[i])
            self.alt_mean += dt / (self.heave_tau + dt) * (fix.altitude - self.alt_mean)
        # Heave er høyden under middelhøyden (positiv ned). Startpunktet duger ikke, for båten
        # setter seg i vannet de første sekundene.
        self.heave = -(fix.altitude - self.alt_mean)
        self.last = (stamp, north, east, down)

    def publish(self):
        if self.imu is None or self.last is None:
            return
        q = self.imu.orientation
        roll, pitch, heading = attitude_enu_to_ned(*euler_from_quaternion(q.x, q.y, q.z, q.w))
        w = self.imu.angular_velocity
        roll_rate, pitch_rate, yaw_rate = rates_flu_to_frd(w.x, w.y, w.z)

        msg = SeapathData()
        # 0 betyr at PX4 setter sin egen tid når meldingen kommer fram. Sim-tid ville blitt feil der.
        msg.timestamp = 0
        msg.timestamp_sample = 0
        # Simulatoren har ingen UTC-tid, så vi bruker klokka på maskinen.
        msg.time_utc_usec = int(time.time() * 1e6)
        msg.latitude_deg = self.fix.latitude
        msg.longitude_deg = self.fix.longitude
        msg.height_ellipsoid_m = self.fix.altitude
        msg.vel_n_m_s, msg.vel_e_m_s, msg.vel_d_m_s = self.velocity
        msg.roll_rad = roll
        msg.pitch_rad = pitch
        msg.heading_rad = heading
        msg.roll_rate_rad_s = roll_rate
        msg.pitch_rate_rad_s = pitch_rate
        msg.yaw_rate_rad_s = yaw_rate
        # Forsinket heave finnes ikke i simulatoren.
        msg.heave_m = self.heave
        msg.delayed_heave_time_utc_usec = 0
        msg.delayed_heave_m = 0.0
        msg.status = SeapathData.STATUS_DELAYED_HEAVE_INVALID
        if self.fix.status.status < NavSatStatus.STATUS_FIX:
            msg.status |= SeapathData.STATUS_HORIZ_INVALID | SeapathData.STATUS_VERT_INVALID
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = Px4SeapathBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
