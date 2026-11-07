"""Regner ut båtens heading (yaw) fra IMU-en."""
import math

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Imu
from std_msgs.msg import Float64


def yaw_from_quaternion(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


class HeadingNode(Node):

    def __init__(self):
        super().__init__('heading_node')
        # Heading er yaw i radianer i ENU: 0 = øst, positiv mot klokka.
        self.pub = self.create_publisher(Float64, '/autonomy/heading', 10)
        self.create_subscription(
            Imu, '/autonomy/imu', self.on_imu, qos_profile_sensor_data)

    def on_imu(self, msg):
        self.pub.publish(Float64(data=yaw_from_quaternion(msg.orientation)))


def main():
    rclpy.init()
    node = HeadingNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
