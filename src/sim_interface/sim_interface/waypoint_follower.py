"""Følger en bane av punkter: sender ønsket heading og fart mot neste punkt."""
import math

import rclpy
from geometry_msgs.msg import Point
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import Float64


class WaypointFollower(Node):

    def __init__(self):
        super().__init__('waypoint_follower')
        # Punktene er x1, y1, x2, y2, ... i meter (øst, nord) fra nullpunktet (se origin).
        flat = self.declare_parameter('waypoints', [0.0, 0.0]).value
        self.waypoints = list(zip(flat[0::2], flat[1::2]))
        self.speed = self.declare_parameter('speed', 1.0).value
        # Et punkt regnes som nådd når båten er nærmere enn radius (meter).
        self.radius = self.declare_parameter('radius', 2.0).value
        self.loop = self.declare_parameter('loop', False).value
        # Fast nullpunkt for banen som [breddegrad, lengdegrad]. [0, 0] betyr der båten er
        # når noden starter. Med fast nullpunkt havner banen riktig selv om båten har drevet.
        origin = self.declare_parameter('origin', [0.0, 0.0]).value
        self.origin = tuple(origin) if any(origin) else None
        self.started = False
        self.index = 0
        self.done = False
        self.heading = 0.0
        self.heading_pub = self.create_publisher(Float64, '/autonomy/desired/heading', 10)
        self.speed_pub = self.create_publisher(Float64, '/autonomy/desired/speed', 10)
        self.position_pub = self.create_publisher(Point, '/autonomy/position', 10)
        self.add_on_set_parameters_callback(self.on_parameters)
        self.create_subscription(
            NavSatFix, '/autonomy/gps/fix', self.on_gps, qos_profile_sensor_data)

    def on_parameters(self, params):
        for param in params:
            if param.name in ('speed', 'radius', 'loop'):
                setattr(self, param.name, param.value)
        return SetParametersResult(successful=True)

    def to_local(self, fix):
        # Flat jord rundt startpunktet. Godt nok for baner på noen hundre meter.
        lat, lon = self.origin
        east = math.radians(fix.longitude - lon) * 6378137.0 * math.cos(math.radians(lat))
        north = math.radians(fix.latitude - lat) * 6378137.0
        return east, north

    def on_gps(self, fix):
        if not self.started:
            self.started = True
            if self.origin is None:
                self.origin = (fix.latitude, fix.longitude)
            self.get_logger().info(f'Start. Følger {len(self.waypoints)} punkter.')
        x, y = self.to_local(fix)
        self.position_pub.publish(Point(x=x, y=y))

        if not self.done:
            wx, wy = self.waypoints[self.index]
            if math.hypot(wx - x, wy - y) < self.radius:
                self.get_logger().info(
                    f'Nådde punkt {self.index + 1} av {len(self.waypoints)} ({wx:.1f}, {wy:.1f}).')
                self.index += 1
                if self.index == len(self.waypoints):
                    self.index = 0
                    self.done = not self.loop
                    if self.done:
                        self.get_logger().info('Banen er ferdig. Stopper.')
            wx, wy = self.waypoints[self.index]
            self.heading = math.atan2(wy - y, wx - x)

        self.heading_pub.publish(Float64(data=self.heading))
        self.speed_pub.publish(Float64(data=0.0 if self.done else self.speed))


def main():
    rclpy.init()
    node = WaypointFollower()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
