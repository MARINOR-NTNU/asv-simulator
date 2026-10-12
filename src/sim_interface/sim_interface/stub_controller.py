"""Midlertidig erstatning for control: P-regulator fra heading-feil til thrust."""
import math

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float64


class StubController(Node):

    def __init__(self):
        super().__init__('stub_controller')
        # Newton per radian heading-feil, og newton per m/s ønsket fart (åpen sløyfe).
        self.kp = self.declare_parameter('kp', 300.0).value
        self.thrust_per_mps = self.declare_parameter('thrust_per_mps', 200.0).value

        self.heading = None
        self.desired_heading = None
        self.desired_speed = 0.0
        self.create_subscription(
            Float64, '/autonomy/heading', lambda m: setattr(self, 'heading', m.data), 10)
        self.create_subscription(
            Float64, '/autonomy/desired/heading',
            lambda m: setattr(self, 'desired_heading', m.data), 10)
        self.create_subscription(
            Float64, '/autonomy/desired/speed',
            lambda m: setattr(self, 'desired_speed', m.data), 10)

        self.pubs = {
            side: self.create_publisher(Float64, f'/control/thruster/{side}/thrust', 10)
            for side in ('left', 'right')}
        self.add_on_set_parameters_callback(self.on_parameters)
        self.create_timer(0.1, self.step)

    def on_parameters(self, params):
        # Lar verdiene endres mens noden kjører, med ros2 param set.
        for param in params:
            if param.name in ('kp', 'thrust_per_mps'):
                setattr(self, param.name, param.value)
        return SetParametersResult(successful=True)

    def step(self):
        if self.heading is None or self.desired_heading is None:
            return
        error = self.desired_heading - self.heading
        error = math.atan2(math.sin(error), math.cos(error))
        base = self.thrust_per_mps * self.desired_speed
        turn = self.kp * error
        # Positiv feil betyr sving mot venstre, altså mer thrust på høyre motor.
        self.pubs['left'].publish(Float64(data=base - turn))
        self.pubs['right'].publish(Float64(data=base + turn))


def main():
    rclpy.init()
    node = StubController()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
