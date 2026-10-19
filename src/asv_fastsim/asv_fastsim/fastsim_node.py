"""Rask 2D-simulator av båten: publiserer /clock, IMU og GPS, og leser motorkommandoer.

Topicene ligner dem i Gazebo (/asv/...), men under /fast/, og kobles til sim_interface med
config/fast.yaml. Noden er klokka selv, så den skal ikke kjøre med use_sim_time.
"""
import math
import os
import threading
import time

import rclpy
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Quaternion
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import Imu, JointState, NavSatFix, NavSatStatus
from std_msgs.msg import Float64

from asv_fastsim.model import BoatModel

EARTH_RADIUS = 6378137.0


class FastSim(Node):

    def __init__(self):
        super().__init__('fastsim')
        default_sdf = os.path.join(
            get_package_share_directory('asv_gazebo'), 'models', 'asv', 'model.sdf')
        sdf = self.declare_parameter('model', default_sdf).value
        self.dt = self.declare_parameter('dt', 0.01).value
        # 1 = sanntid, 10 = ti ganger raskere, 0 = så fort maskinen klarer.
        self.real_time_factor = self.declare_parameter('real_time_factor', 1.0).value
        self.imu_period = 1.0 / self.declare_parameter('imu_rate', 100.0).value
        self.gps_period = 1.0 / self.declare_parameter('gps_rate', 20.0).value
        # Startsted: samme som vår båt i sydney_regatta i Gazebo.
        self.lat0 = self.declare_parameter('latitude', -33.722768768890596).value
        self.lon0 = self.declare_parameter('longitude', 150.67399110173986).value
        angle_gain = self.declare_parameter('angle_gain', 50.0).value

        self.model = BoatModel(sdf, angle_gain=angle_gain)
        self.model.yaw = self.declare_parameter('yaw', 1.0).value   # radianer ENU
        self.get_logger().info(
            f'Modell fra {sdf}: {self.model.mass:.1f} kg, '
            f'thrustere {", ".join(self.model.thrusters)}.')

        for name, thruster in self.model.thrusters.items():
            self.create_subscription(
                Float64, f'/fast/thrusters/{name}/thrust',
                lambda m, n=name: self.model.set_thrust(n, m.data), 10)
            if thruster.steerable:
                self.create_subscription(
                    Float64, f'/fast/thrusters/{name}/pos',
                    lambda m, n=name: self.model.set_angle(n, m.data), 10)
        self.clock_pub = self.create_publisher(Clock, '/clock', 10)
        self.imu_pub = self.create_publisher(Imu, '/fast/sensors/imu', 10)
        self.gps_pub = self.create_publisher(NavSatFix, '/fast/sensors/gps', 10)
        self.joint_pub = self.create_publisher(JointState, '/fast/joint_states', 10)

    def stamp(self, t):
        sec = int(t)
        return sec, int(round((t - sec) * 1e9))

    def run(self):
        t = 0.0
        next_imu = next_gps = 0.0
        wall_start = time.monotonic()
        while rclpy.ok():
            self.model.step(self.dt)
            t += self.dt
            sec, nsec = self.stamp(t)
            clock = Clock()
            clock.clock.sec, clock.clock.nanosec = sec, nsec
            self.clock_pub.publish(clock)
            if t >= next_imu:
                self.publish_imu(sec, nsec)
                next_imu += self.imu_period
            if t >= next_gps:
                self.publish_gps(sec, nsec)
                next_gps += self.gps_period
            if self.real_time_factor > 0.0:
                ahead = t / self.real_time_factor - (time.monotonic() - wall_start)
                if ahead > 0.0:
                    time.sleep(ahead)

    def publish_imu(self, sec, nsec):
        m = self.model
        msg = Imu()
        msg.header.stamp.sec, msg.header.stamp.nanosec = sec, nsec
        msg.header.frame_id = 'asv/base_link'
        # Orienteringen er i ENU, som i Gazebo (orientation_reference_frame ENU).
        msg.orientation = Quaternion(z=math.sin(m.yaw / 2.0), w=math.cos(m.yaw / 2.0))
        msg.angular_velocity.z = m.r
        msg.linear_acceleration.x = m.u_dot - m.v * m.r
        msg.linear_acceleration.y = m.v_dot + m.u * m.r
        msg.linear_acceleration.z = 9.81
        self.imu_pub.publish(msg)

        joints = JointState()
        joints.header = msg.header
        for t in m.thrusters.values():
            if t.steerable:
                joints.name.append(t.pod_joint)
                joints.position.append(t.angle)
        self.joint_pub.publish(joints)

    def publish_gps(self, sec, nsec):
        east, north = self.model.origin_position()
        msg = NavSatFix()
        msg.header.stamp.sec, msg.header.stamp.nanosec = sec, nsec
        msg.header.frame_id = 'asv/navsat'
        msg.status.status = NavSatStatus.STATUS_FIX
        msg.status.service = NavSatStatus.SERVICE_GPS
        # Flat jord med fast referansebredde, ellers gir nord/sør falsk forflytning øst/vest.
        msg.latitude = self.lat0 + math.degrees(north / EARTH_RADIUS)
        msg.longitude = self.lon0 + math.degrees(
            east / (EARTH_RADIUS * math.cos(math.radians(self.lat0))))
        msg.altitude = 0.0
        self.gps_pub.publish(msg)


def main():
    rclpy.init()
    node = FastSim()
    # Motorkommandoene tas imot i en egen tråd. Med spin_once i simuleringsløkka ble bare én
    # melding behandlet per steg, så kommandoene hopet seg opp og kom fram for sent.
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()
    try:
        node.run()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass


if __name__ == '__main__':
    main()
