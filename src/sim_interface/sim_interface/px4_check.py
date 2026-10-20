"""Sjekker koblingen mellom control sin PX4 og simulatoren, ledd for ledd, og sier hvor den stopper.

Kjøres i simulator-containeren mens simulatoren kjører:
    ros2 run sim_interface px4_check

PX4 sine forbindelser lages av agenten, som ikke er en ROS-node. De vises derfor med et
plassholdernavn i stedet for et nodenavn (_CREATED_BY_BARE_DDS_APP_ med agent v2.4.2 og Humble,
testet mot ekte PX4 2026-10-20). Det er slik verktøyet ser at PX4 er koblet til.
"""
import math
import os
import subprocess
import sys
import time

import rclpy
from px4_msgs.msg import MotorOutput, SeapathData
from rclpy.qos import qos_profile_sensor_data
from rosgraph_msgs.msg import Clock

# Nodenavnene agenten gir PX4 sine forbindelser. Det første er det vi ser med agent v2.4.2.
PX4_NODE_NAMES = ('_CREATED_BY_BARE_DDS_APP_', '_NODE_NAME_UNKNOWN_')
MOTOR = '/fmu/out/motor_output'
SEAPATH = '/fmu/in/seapath_data'
MOTOR_FIELDS = ('forward_propeller_thrust', 'port_side_thrust', 'port_side_angle',
                'starboard_thrust', 'starboard_angle')


class Report:

    def __init__(self):
        self.failed = False

    def section(self, title):
        print(f'\n{title}')

    def ok(self, text):
        print(f'  ✓ {text}')

    def info(self, text):
        print(f'  – {text}')

    def fail(self, text, hints):
        print(f'  ✗ {text}')
        for hint in hints:
            print(f'      → {hint}')
        self.failed = True


def udp_port_open(port):
    for path in ('/proc/net/udp', '/proc/net/udp6'):
        try:
            lines = open(path).read().splitlines()[1:]
        except OSError:
            continue
        if any(line.split()[1].endswith(f':{port:04X}') for line in lines):
            return True
    return False


def main():
    rclpy.init()
    node = rclpy.create_node('px4_check')
    wait = node.declare_parameter('wait', 5.0).value
    port = node.declare_parameter('agent_port', 8888).value

    counts = {'clock': 0, 'motor': 0, 'seapath': 0}
    last = {}

    def on_motor(msg):
        counts['motor'] += 1
        last['motor'] = msg

    node.create_subscription(Clock, '/clock', lambda m: counts.__setitem__('clock', counts['clock'] + 1), 10)
    node.create_subscription(MotorOutput, MOTOR, on_motor, qos_profile_sensor_data)
    node.create_subscription(
        SeapathData, SEAPATH, lambda m: counts.__setitem__('seapath', counts['seapath'] + 1),
        qos_profile_sensor_data)

    print(f'Lytter i {wait:.0f} s ...')
    end = time.monotonic() + wait
    while time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.05)

    r = Report()
    nodes = {name for name, _ in node.get_node_names_and_namespaces()}
    domain = os.environ.get('ROS_DOMAIN_ID', '0')

    r.section('Simulatoren')
    if counts['clock']:
        r.ok('Simulatoren kjører (/clock)')
    else:
        r.fail('Ingen /clock', ['Start simulatoren: ros2 launch sim_interface sim.launch.py control:=px4'])
    for name in ('px4_motor_bridge', 'px4_seapath_bridge', 'thruster_adapter'):
        if name in nodes:
            r.ok(f'{name} kjører')
        else:
            r.fail(f'{name} kjører ikke', ['Start med control:=px4 i sim.launch.py'])
    if counts['seapath']:
        r.ok(f'SeapathData sendes til PX4: {counts["seapath"] / wait:.0f} Hz (vegg-tid)')
    elif 'px4_seapath_bridge' not in nodes:
        r.info('Ingen SeapathData (følger av at px4_seapath_bridge ikke kjører)')
    else:
        r.fail('Ingen SeapathData på ' + SEAPATH,
               ['px4_seapath_bridge trenger /autonomy/imu og /autonomy/gps/fix. Sjekk dem med ros2 topic hz.'])

    r.section('Agenten')
    running = subprocess.run(['pgrep', '-x', 'MicroXRCEAgent'], capture_output=True).returncode == 0
    if running:
        r.ok('MicroXRCEAgent kjører')
    else:
        r.fail('MicroXRCEAgent kjører ikke',
               ['sim.launch.py starter den med control:=px4. Ellers: MicroXRCEAgent udp4 -p 8888'])
    if udp_port_open(port):
        r.ok(f'Noe lytter på UDP-port {port}')
    elif running:
        r.fail(f'Ingen lytter på UDP-port {port}',
               ['Agenten kjører på en annen port, eller over serie (kortet på USB).'])

    r.section('PX4')
    topics = node.get_topic_names_and_types()
    from_px4 = [t for t, _ in topics if t.startswith('/fmu/') and any(
        e.node_name in PX4_NODE_NAMES for e in
        node.get_publishers_info_by_topic(t) + node.get_subscriptions_info_by_topic(t))]
    if from_px4:
        r.ok(f'PX4 er koblet til agenten ({len(from_px4)} /fmu-topics fra PX4)')
    elif not running:
        r.info('PX4 kan ikke koble til (følger av at agenten ikke kjører)')
    else:
        r.fail('PX4 er ikke koblet til agenten', [
            'Kjører PX4, og er uxrce_dds_client startet? (uxrce_dds_client status i PX4-konsollen)',
            f'Samme PC og --net=host: PX4 skal finne agenten på 127.0.0.1:{port}. '
            'Annen PC: sett UXRCE_DDS_AG_IP til IP-en til simulator-PC-en.',
            f'ROS_DOMAIN_ID her er {domain}. Den må være lik UXRCE_DDS_DOM_ID i PX4.'])

    pubs = node.get_publishers_info_by_topic(MOTOR)
    px4_pubs = [p for p in pubs if p.node_name in PX4_NODE_NAMES]
    other_pubs = sorted({p.node_name for p in pubs if p.node_name not in PX4_NODE_NAMES})
    if px4_pubs:
        wrong = {p.topic_type for p in px4_pubs} - {'px4_msgs/msg/MotorOutput'}
        if wrong:
            r.fail(f'PX4 sender {MOTOR} med typen {", ".join(wrong)}',
                   ['Typen må være px4_msgs::msg::MotorOutput i dds_topics.yaml.'])
        else:
            r.ok(f'PX4 sender {MOTOR}')
    elif from_px4:
        r.fail(f'PX4 sender ikke {MOTOR}', [
            'Mangler i src/modules/uxrce_dds_client/dds_topics.yaml under publications, '
            'eller PX4 er bygget fra en gren uten den.'])
    if other_pubs:
        r.info(f'{MOTOR} kommer også fra {", ".join(other_pubs)}, ikke fra PX4 (f.eks. ros2 topic pub).')

    if any(s.node_name in PX4_NODE_NAMES for s in node.get_subscriptions_info_by_topic(SEAPATH)):
        r.ok(f'PX4 tar imot {SEAPATH}')
    elif from_px4:
        r.fail(f'PX4 tar ikke imot {SEAPATH}', [
            'Mangler i dds_topics.yaml under subscriptions, eller PX4 er bygget fra en gren uten den.'])

    r.section('Data fra PX4')
    if counts['motor']:
        m = last['motor']
        values = [getattr(m, f) for f in MOTOR_FIELDS]
        r.ok(f'MotorOutput kommer: {counts["motor"] / wait:.0f} Hz (vegg-tid)')
        r.info('Siste verdier: ' + ', '.join(f'{f} {v:g}' for f, v in zip(MOTOR_FIELDS, values)))
        if any(not math.isfinite(v) for v in values):
            r.fail('MotorOutput inneholder NaN eller uendelig',
                   ['Broen sender ikke slike verdier videre. Sjekk modulen som lager MotorOutput i PX4.'])
        elif all(abs(v) in (0.0, 1.0) for v in values):
            r.info('Verdiene ser ut som plassholdere (0 og ±1). Regulatorveien til control er kanskje '
                   'ikke koblet på, eller RC-modus er ikke valgt.')
        elif any(900.0 <= abs(v) <= 2100.0 for v in values):
            r.info('Verdiene ser ut som rå RC-verdier (ca. 1000–2000 µs), ikke -100..100 %. '
                   'Juster thrust_offset og *_thrust_scale i config/px4_bridge.yaml.')
    elif pubs:
        r.fail(f'{MOTOR} finnes, men det kommer ingen data', [
            'MotorOutput.msg er ikke lik hos control og i px4_msgs. Kjør scripts/sync_px4_msgs.sh '
            'mot grenen PX4 er bygget fra, og bygg imaget på nytt.',
            'Modulen som publiserer MotorOutput i PX4 kjører ikke (f.eks. switch_motor_output).',
            'Agenten kjører i en annen container enn broene: da stopper shared memory i Fast-DDS dataene.'])
    else:
        r.info('Ingen MotorOutput å sjekke.')

    print('\nAlt ser bra ut.' if not r.failed else '\nStart med den første ✗ over.')
    node.destroy_node()
    rclpy.shutdown()
    sys.exit(1 if r.failed else 0)


if __name__ == '__main__':
    main()
