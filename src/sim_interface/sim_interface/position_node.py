"""Regner ut båtens posisjon i meter (x øst, y nord) fra GPS."""
import math

import rclpy
from geometry_msgs.msg import Point
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import NavSatFix

EARTH_RADIUS = 6378137.0


class PositionNode(Node):

    def __init__(self):
        super().__init__('position_node')
        # Fast nullpunkt som [breddegrad, lengdegrad]. [0, 0] betyr der båten er ved første GPS-måling.
        origin = self.declare_parameter('origin', [0.0, 0.0]).value
        self.origin = tuple(origin) if any(origin) else None
        # x øst og y nord i meter fra nullpunktet. z er alltid 0.
        self.pub = self.create_publisher(Point, '/autonomy/position', 10)
        self.create_subscription(
            NavSatFix, '/autonomy/gps/fix', self.on_gps, qos_profile_sensor_data)

    def on_gps(self, fix):
        if self.origin is None:
            self.origin = (fix.latitude, fix.longitude)
            self.get_logger().info(f'Nullpunkt: {fix.latitude:.7f}, {fix.longitude:.7f}')
        # Flat jord rundt nullpunktet. Godt nok for noen hundre meter.
        lat, lon = self.origin
        east = math.radians(fix.longitude - lon) * EARTH_RADIUS * math.cos(math.radians(lat))
        north = math.radians(fix.latitude - lat) * EARTH_RADIUS
        self.pub.publish(Point(x=east, y=north))


def main():
    rclpy.init()
    node = PositionNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
