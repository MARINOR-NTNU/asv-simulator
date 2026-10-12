"""Oversetter /control/thruster/... til simulatorens egne thruster-topics."""
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float64

def clamp(value, limit):
    return max(-limit, min(limit, value))


class ThrusterAdapter(Node):

    def __init__(self):
        super().__init__('thruster_adapter')
        # Motorene på båten, og hvilke av dem som kan dreies.
        self.thrusters = self.declare_parameter('thrusters', ['left', 'right']).value
        steerable = self.declare_parameter('steerable', ['left', 'right']).value
        # Simulatorens topics. {side} byttes ut med motornavnet. Tom angle_topic = faste motorer.
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

        self.thrust = dict.fromkeys(self.thrusters, 0.0)
        self.angle = dict.fromkeys(self.thrusters, 0.0)
        # Hver motor har sin egen timeout, så en gammel verdi ikke blir stående.
        self.last_cmd = dict.fromkeys(self.thrusters, None)
        self.timed_out = dict.fromkeys(self.thrusters, True)
        self.thrust_pubs = {}
        self.angle_pubs = {}
        for side in self.thrusters:
            self.thrust_pubs[side] = self.create_publisher(
                Float64, thrust_topic.format(side=side), 10)
            self.create_subscription(
                Float64, f'/control/thruster/{side}/thrust',
                lambda msg, s=side: self.on_thrust(s, msg), 10)
            if angle_topic and side in steerable:
                self.angle_pubs[side] = self.create_publisher(
                    Float64, angle_topic.format(side=side), 10)
                self.create_subscription(
                    Float64, f'/control/thruster/{side}/angle',
                    lambda msg, s=side: self.on_angle(s, msg), 10)

        self.create_timer(1.0 / rate, self.publish)

    def on_thrust(self, side, msg):
        self.thrust[side] = clamp(msg.data, self.max_thrust)
        self.last_cmd[side] = self.get_clock().now()

    def on_angle(self, side, msg):
        self.angle[side] = clamp(msg.data, self.max_angle)

    def publish(self):
        now = self.get_clock().now()
        for side in self.thrusters:
            last = self.last_cmd[side]
            timed_out = last is None or (now - last).nanoseconds * 1e-9 > self.timeout
            if timed_out != self.timed_out[side]:
                self.get_logger().info(
                    f'{side}: ingen thrust-kommandoer, setter thrust til 0.' if timed_out
                    else f'{side}: mottar thrust-kommandoer.')
                self.timed_out[side] = timed_out
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
