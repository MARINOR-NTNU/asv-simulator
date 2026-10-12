"""Midlertidig erstatning for autonomy: sender ønsket heading og fart."""
import math

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float64


class FakeHeading(Node):

    def __init__(self):
        super().__init__('fake_heading')
        self.heading = self.declare_parameter('heading', 0.0).value
        self.speed = self.declare_parameter('speed', 1.0).value
        # sweep_rate > 0 dreier ønsket heading jevnt (rad/s). 0 gir fast heading.
        self.sweep_rate = self.declare_parameter('sweep_rate', 0.0).value
        self.period = 0.1

        self.heading_pub = self.create_publisher(Float64, '/autonomy/desired/heading', 10)
        self.speed_pub = self.create_publisher(Float64, '/autonomy/desired/speed', 10)
        self.add_on_set_parameters_callback(self.on_parameters)
        self.create_timer(self.period, self.publish)

    def on_parameters(self, params):
        # Lar verdiene endres mens noden kjører, med ros2 param set.
        for param in params:
            if param.name in ('heading', 'speed', 'sweep_rate'):
                setattr(self, param.name, param.value)
        return SetParametersResult(successful=True)

    def publish(self):
        self.heading += self.sweep_rate * self.period
        self.heading = math.atan2(math.sin(self.heading), math.cos(self.heading))
        self.heading_pub.publish(Float64(data=self.heading))
        self.speed_pub.publish(Float64(data=self.speed))


def main():
    rclpy.init()
    node = FakeHeading()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
