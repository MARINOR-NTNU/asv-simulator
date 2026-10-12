"""Oversetter /control/thruster/... til simulatorens egne thruster-topics."""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float64

SIDES = ('left', 'right')


def clamp(value, limit):
    return max(-limit, min(limit, value))


class ThrusterAdapter(Node):

    def __init__(self):
        super().__init__('thruster_adapter')
        # Simulatorens topics. {side} byttes ut med left/right. Tom angle_topic = faste motorer.
        thrust_topic = self.declare_parameter('thrust_topic', '').value
        angle_topic = self.declare_parameter('angle_topic', '').value
        # Grenser i kontraktens enheter (newton og radianer).
        self.max_thrust = self.declare_parameter('max_thrust', 0.0).value
        self.max_angle = self.declare_parameter('max_angle', 0.0).value
        # Omregning fra kontraktens enheter til simulatorens.
        self.thrust_scale = self.declare_parameter('thrust_scale', 1.0).value
        self.angle_scale = self.declare_parameter('angle_scale', 1.0).value
        self.timeout = self.declare_parameter('timeout', 0.5).value
        rate = self.declare_parameter('rate', 20.0).value

        if not thrust_topic:
            raise RuntimeError('thrust_topic er ikke satt. Start med config/<sim>.yaml.')

        self.thrust = dict.fromkeys(SIDES, 0.0)
        self.angle = dict.fromkeys(SIDES, 0.0)
        self.last_cmd = None
        self.timed_out = True
        self.thrust_pubs = {}
        self.angle_pubs = {}
        for side in SIDES:
            self.thrust_pubs[side] = self.create_publisher(
                Float64, thrust_topic.format(side=side), 10)
            self.create_subscription(
                Float64, f'/control/thruster/{side}/thrust',
                lambda msg, s=side: self.on_thrust(s, msg), 10)
            if angle_topic:
                self.angle_pubs[side] = self.create_publisher(
                    Float64, angle_topic.format(side=side), 10)
                self.create_subscription(
                    Float64, f'/control/thruster/{side}/angle',
                    lambda msg, s=side: self.on_angle(s, msg), 10)

        self.create_timer(1.0 / rate, self.publish)

    def on_thrust(self, side, msg):
        self.thrust[side] = clamp(msg.data, self.max_thrust)
        self.last_cmd = self.get_clock().now()

    def on_angle(self, side, msg):
        self.angle[side] = clamp(msg.data, self.max_angle)

    def publish(self):
        now = self.get_clock().now()
        timed_out = (self.last_cmd is None
                     or (now - self.last_cmd).nanoseconds * 1e-9 > self.timeout)
        if timed_out != self.timed_out:
            self.get_logger().info(
                'Ingen thrust-kommandoer, setter thrust til 0.' if timed_out
                else 'Mottar thrust-kommandoer.')
            self.timed_out = timed_out
        for side in SIDES:
            thrust = 0.0 if timed_out else self.thrust[side]
            self.thrust_pubs[side].publish(Float64(data=thrust * self.thrust_scale))
            if side in self.angle_pubs:
                self.angle_pubs[side].publish(
                    Float64(data=self.angle[side] * self.angle_scale))


def main():
    rclpy.init()
    node = ThrusterAdapter()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
