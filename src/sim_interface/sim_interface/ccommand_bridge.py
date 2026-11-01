"""Sender ønsket kurs og fart fra autonomy til control sin PX4 som MAVLink-meldingen CCOMMAND.

Gjør det samme som jetson skal gjøre på båten. Meldingen er definert av control i
src/modules/mavlink/custom_messages/custom.xml i PX4-forken, og en kopi ligger i mavlink/custom.xml
her (scripts/sync_px4_msgs.sh oppdaterer den). Python-koden for meldingen lages fra kopien når
noden starter, så den alltid passer med definisjonen.

Leser /autonomy/desired/heading (rad, ENU: 0 = øst, mot klokka) og /autonomy/desired/speed (m/s),
og sender desired_course som kompasskurs i radianer (NED: 0 = nord, med klokka), som PX4 bruker.
Sender ingenting når verdiene er eldre enn timeout, så PX4 merker at autonomy er borte.
"""
import importlib.util
import math
import os
import socket
import tempfile

import rclpy
from ament_index_python.packages import get_package_share_directory
from pymavlink.generator import mavgen
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float64


def load_dialect(xml):
    """Lager og importerer pymavlink-koden for meldingene i xml."""
    out = os.path.join(tempfile.mkdtemp(prefix='ccommand_'), 'custom.py')
    opts = mavgen.Opts(out, wire_protocol='2.0', language='Python3', validate=False)
    if not mavgen.mavgen(opts, [xml]):
        raise RuntimeError(f'Klarte ikke å lage MAVLink-kode fra {xml}')
    spec = importlib.util.spec_from_file_location('ccommand_dialect', out)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def enu_to_compass(yaw):
    """ENU-yaw (0 = øst, mot klokka) til kompasskurs (0 = nord, med klokka), 0 til 2π."""
    return (math.pi / 2 - yaw) % (2 * math.pi)


class CcommandBridge(Node):

    def __init__(self):
        super().__init__('ccommand_bridge')
        default_xml = os.path.join(get_package_share_directory('sim_interface'), 'mavlink', 'custom.xml')
        xml = self.declare_parameter('xml', default_xml).value
        # PX4 i SITL tar imot fra jetson/onboard-datamaskinen på UDP 14580 (px4-rc.mavlink).
        self.target = (self.declare_parameter('host', '127.0.0.1').value,
                       self.declare_parameter('port', 14580).value)
        rate = self.declare_parameter('rate', 10.0).value
        self.timeout = self.declare_parameter('timeout', 0.5).value
        self.control_mode = self.declare_parameter('control_mode', 0).value  # 0 = VELOCITYHEADING
        self.is_ground_controlled = self.declare_parameter('is_ground_controlled', 0).value
        # Samme system som PX4 (1), komponent 191 = MAV_COMP_ID_ONBOARD_COMPUTER (jetson).
        system = self.declare_parameter('source_system', 1).value
        component = self.declare_parameter('source_component', 191).value

        dialect = load_dialect(xml)
        self.mav = dialect.MAVLink(None, srcSystem=system, srcComponent=component)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.heading = None  # (verdi, tid)
        self.speed = None
        self.sent = 0
        self.create_subscription(Float64, '/autonomy/desired/heading',
                                 lambda m: setattr(self, 'heading', (m.data, self.now())), 10)
        self.create_subscription(Float64, '/autonomy/desired/speed',
                                 lambda m: setattr(self, 'speed', (m.data, self.now())), 10)
        self.create_timer(1.0 / rate, self.send)
        self.create_timer(10.0, self.report)
        self.get_logger().info(
            f'Sender CCOMMAND til {self.target[0]}:{self.target[1]} ({rate:g} Hz, {xml})')

    def now(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def fresh(self, value):
        return value is not None and self.now() - value[1] <= self.timeout

    def send(self):
        if not (self.fresh(self.heading) and self.fresh(self.speed)):
            return
        msg = self.mav.ccommand_encode(
            desired_speed=self.speed[0], desired_course=enu_to_compass(self.heading[0]),
            desired_pos=[0.0, 0.0], desired_wrench=[0.0] * 3, desired_motor_output=[0.0] * 5,
            control_mode=self.control_mode, is_ground_controlled=self.is_ground_controlled)
        self.sock.sendto(msg.pack(self.mav), self.target)
        # pack() øker ikke sekvensnummeret (det gjør bare send()). Uten dette tror PX4 at meldinger mangler.
        self.mav.seq = (self.mav.seq + 1) % 256
        self.sent += 1

    def report(self):
        if self.sent:
            self.get_logger().info(f'{self.sent} CCOMMAND sendt siste 10 s')
        else:
            self.get_logger().info('Ingen CCOMMAND sendt siste 10 s (mangler ferske ønskede verdier)')
        self.sent = 0


def main():
    rclpy.init()
    node = CcommandBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
