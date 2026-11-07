"""Sender simulatorens sensor-topics videre til de faste /autonomy/...-navnene."""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rosidl_runtime_py.utilities import get_message


class SensorRelay(Node):

    def __init__(self):
        super().__init__('sensor_relay')
        # Tre like lange lister: fra-topic, til-topic og meldingstype.
        inputs = self.declare_parameter('inputs', ['']).value
        outputs = self.declare_parameter('outputs', ['']).value
        types = self.declare_parameter('types', ['']).value
        if not (len(inputs) == len(outputs) == len(types)):
            raise RuntimeError('inputs, outputs og types må være like lange.')

        for src, dst, type_name in zip(inputs, outputs, types):
            if not src:
                continue
            msg_type = get_message(type_name)
            pub = self.create_publisher(msg_type, dst, 10)
            # raw=True sender bytes rett videre uten å pakke ut meldingen.
            self.create_subscription(
                msg_type, src, pub.publish, qos_profile_sensor_data, raw=True)
            self.get_logger().info(f'{src} -> {dst} [{type_name}]')


def main():
    rclpy.init()
    node = SensorRelay()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
