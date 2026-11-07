"""Midlertidig erstatning for control: regulerer heading og fart med thrust."""
import math

import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float64

LIVE_PARAMETERS = (
    'kp', 'thrust_per_mps', 'speed_kp', 'speed_ki', 'speed_integral_zone', 'max_thrust')


class StubController(Node):

    def __init__(self):
        super().__init__('stub_controller')
        # Heading: newton per radian feil (P-regulator).
        self.kp = self.declare_parameter('kp', 300.0).value
        # Fart: foroverkobling (newton per m/s ønsket fart) pluss PI-regulator på målt fart.
        # Alle verdier gjelder per motor.
        self.thrust_per_mps = self.declare_parameter('thrust_per_mps', 200.0).value
        self.speed_kp = self.declare_parameter('speed_kp', 0.0).value
        self.speed_ki = self.declare_parameter('speed_ki', 0.0).value
        # I-leddet er bare aktivt når fartsfeilen er mindre enn dette (m/s). Ellers bygger det
        # seg opp under akselerasjonen, og båten skyter over ønsket fart.
        self.speed_integral_zone = self.declare_parameter('speed_integral_zone', 0.3).value
        self.max_thrust = self.declare_parameter('max_thrust', 1e9).value
        self.period = 0.1

        self.heading = None
        self.desired_heading = None
        self.desired_speed = 0.0
        self.speed = None
        self.integral = 0.0
        self.create_subscription(
            Float64, '/autonomy/heading', lambda m: setattr(self, 'heading', m.data), 10)
        self.create_subscription(
            Float64, '/autonomy/desired/heading',
            lambda m: setattr(self, 'desired_heading', m.data), 10)
        self.create_subscription(
            Float64, '/autonomy/desired/speed',
            lambda m: setattr(self, 'desired_speed', m.data), 10)
        self.create_subscription(
            Float64, '/autonomy/speed', lambda m: setattr(self, 'speed', m.data), 10)

        self.pubs = {
            side: self.create_publisher(Float64, f'/control/thruster/{side}/thrust', 10)
            for side in ('left', 'right')}
        self.add_on_set_parameters_callback(self.on_parameters)
        self.create_timer(self.period, self.step)

    def on_parameters(self, params):
        # Lar verdiene endres mens noden kjører, med ros2 param set.
        for param in params:
            if param.name in LIVE_PARAMETERS:
                setattr(self, param.name, param.value)
        return SetParametersResult(successful=True)

    def base_thrust(self):
        base = self.thrust_per_mps * self.desired_speed
        if self.speed is None:
            # Ingen fartsmåling: bare foroverkobling, som før.
            return base
        error = self.desired_speed - self.speed
        if self.desired_speed == 0.0:
            self.integral = 0.0
        elif abs(error) < self.speed_integral_zone:
            self.integral += self.speed_ki * error * self.period
            # Begrens integralet, så det ikke vokser mens motorene står i maks.
            self.integral = max(-self.max_thrust, min(self.max_thrust, self.integral))
        base += self.speed_kp * error + self.integral
        return max(-self.max_thrust, min(self.max_thrust, base))

    def step(self):
        if self.heading is None or self.desired_heading is None:
            return
        error = self.desired_heading - self.heading
        error = math.atan2(math.sin(error), math.cos(error))
        base = self.base_thrust()
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
