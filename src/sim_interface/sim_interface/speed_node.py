"""Regner ut båtens fart forover fra GPS og heading."""
import math

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Float64

EARTH_RADIUS = 6378137.0


class SpeedNode(Node):

    def __init__(self):
        super().__init__('speed_node')
        # Tidskonstant for glatting (sekunder). GPS-posisjon derivert direkte gir mye støy.
        self.tau = self.declare_parameter('tau', 0.5).value

        self.origin = None
        self.last = None
        self.velocity = [0.0, 0.0]
        self.heading = None
        # Fart langs baugen i m/s. Negativ når båten går bakover.
        self.pub = self.create_publisher(Float64, '/autonomy/speed', 10)
        self.create_subscription(
            Float64, '/autonomy/heading', lambda m: setattr(self, 'heading', m.data), 10)
        self.create_subscription(
            NavSatFix, '/autonomy/gps/fix', self.on_gps, qos_profile_sensor_data)

    def on_gps(self, fix):
        if self.origin is None:
            self.origin = fix
        # cos(breddegrad) regnes med startbredden. Ellers gir bevegelse nord/sør falsk fart øst/vest.
        east = math.radians(fix.longitude - self.origin.longitude) \
            * EARTH_RADIUS * math.cos(math.radians(self.origin.latitude))
        north = math.radians(fix.latitude - self.origin.latitude) * EARTH_RADIUS
        stamp = fix.header.stamp.sec + fix.header.stamp.nanosec * 1e-9

        if self.last is not None:
            dt = stamp - self.last[0]
            if dt <= 0.0:
                return
            alpha = dt / (self.tau + dt)
            self.velocity[0] += alpha * ((east - self.last[1]) / dt - self.velocity[0])
            self.velocity[1] += alpha * ((north - self.last[2]) / dt - self.velocity[1])
            if self.heading is None:
                speed = math.hypot(*self.velocity)
            else:
                speed = self.velocity[0] * math.cos(self.heading) \
                    + self.velocity[1] * math.sin(self.heading)
            self.pub.publish(Float64(data=speed))
        self.last = (stamp, east, north)


def main():
    rclpy.init()
    node = SpeedNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
