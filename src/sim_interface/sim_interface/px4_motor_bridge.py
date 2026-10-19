"""Oversetter control sin MotorOutput fra PX4 (uXRCE-DDS) til /control/thruster/...

Erstatter motor_writer i PX4 når vi kjører i simulatoren. thruster_adapter tar seg av
begrensning og timeout videre.
"""
import math

import rclpy
from px4_msgs.msg import MotorOutput
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from std_msgs.msg import Float64


class Px4MotorBridge(Node):

    def __init__(self):
        super().__init__('px4_motor_bridge')
        topic = self.declare_parameter('motor_output_topic', '/fmu/out/motor_output').value
        # Enhetene i MotorOutput er ikke avklart med control. Det som sendes videre er
        # (verdi - offset) * scale, så standardverdiene sender alt rett videre som newton og radianer.
        self.thrust_offset = self.declare_parameter('thrust_offset', 0.0).value
        self.thrust_scale = self.declare_parameter('thrust_scale', 1.0).value
        self.angle_offset = self.declare_parameter('angle_offset', 0.0).value
        self.angle_scale = self.declare_parameter('angle_scale', 1.0).value
        # Motoren forward_propeller_thrust sendes til, f.eks. bow. Tom = ignoreres (WAM-V har ingen).
        forward = self.declare_parameter('forward_thruster', '').value

        # Felt i MotorOutput -> topic under /control/thruster/. Babord = left, styrbord = right.
        targets = [
            ('port_side_thrust', 'left/thrust'),
            ('port_side_angle', 'left/angle'),
            ('starboard_thrust', 'right/thrust'),
            ('starboard_angle', 'right/angle'),
        ]
        if forward:
            targets.append(('forward_propeller_thrust', f'{forward}/thrust'))
        self.outputs = [
            (field, self.create_publisher(Float64, f'/control/thruster/{name}', 10))
            for field, name in targets
        ]
        self.receiving = False

        # PX4 publiserer best effort, så abonnementet må også være best effort.
        self.create_subscription(
            MotorOutput, topic, self.on_motor_output, qos_profile_sensor_data)

    def on_motor_output(self, msg):
        if not self.receiving:
            self.get_logger().info('Mottar MotorOutput fra PX4.')
            self.receiving = True
        for field, publisher in self.outputs:
            value = getattr(msg, field)
            if not math.isfinite(value):
                self.get_logger().warn(
                    f'{field} er {value}, sendes ikke videre.', throttle_duration_sec=1.0)
                continue
            if field.endswith('angle'):
                value = (value - self.angle_offset) * self.angle_scale
            else:
                value = (value - self.thrust_offset) * self.thrust_scale
            publisher.publish(Float64(data=value))


def main():
    rclpy.init()
    node = Px4MotorBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
