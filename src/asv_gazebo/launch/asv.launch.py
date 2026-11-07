"""Starter en verden med vår egen ASV: open_water (vår, uten land) eller en VRX-verden som sydney_regatta.

Modellen og open_water lages fra xacro når den startes, med valgene under:
  sensor_noise:=true     støy på IMU og GPS
  wave_height:=0.3       største bølgeutslag i m, med wave_period (s) og wave_direction (rad), bare open_water
  current_speed:=0.5     strøm i m/s, med current_direction (grader, 0 = mot øst), i alle verdenene
  wind_speed:=5          vind i m/s (bare open_water), med wind_direction (grader, 0 = mot øst)
                         og wind_gust (hvor mye vinden varierer)
"""
import os
import tempfile

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import vrx_gz.launch
import xacro
import yaml

from asv_gazebo.scenario import WORLDS
from asv_gazebo.waves import gain_for_height

BRIDGES = [
    '/asv/thrusters/left/thrust@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/thrusters/right/thrust@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/thrusters/bow/thrust@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/thrusters/left/pos@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/thrusters/right/pos@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/sensors/imu@sensor_msgs/msg/Imu[ignition.msgs.IMU',
    '/asv/sensors/gps@sensor_msgs/msg/NavSatFix[ignition.msgs.NavSat',
]


def sensor_bridges(config_path):
    """Broer fra Gazebo til ROS for sensorene i components.yaml, med navnene autonomy leser."""
    with open(config_path) as f:
        sensors = (yaml.safe_load(f) or {}).get('sensors') or []
    bridges, remaps = [], []
    for s in sensors:
        n, base = s['name'], f'/asv/sensors/{s["name"]}'
        if s['type'] == 'lidar':
            pairs = [(f'{base}/scan/points', 'sensor_msgs/msg/PointCloud2', 'PointCloudPacked',
                      f'/autonomy/lidar/{n}/points'),
                     (f'{base}/scan', 'sensor_msgs/msg/LaserScan', 'LaserScan', f'/autonomy/lidar/{n}/scan')]
        else:
            pairs = [(f'{base}/image_raw', 'sensor_msgs/msg/Image', 'Image', f'/autonomy/camera/{n}/image_raw'),
                     (f'{base}/camera_info', 'sensor_msgs/msg/CameraInfo', 'CameraInfo',
                      f'/autonomy/camera/{n}/camera_info')]
        for gz_topic, ros_type, gz_type, ros_topic in pairs:
            bridges.append(f'{gz_topic}@{ros_type}[ignition.msgs.{gz_type}')
            remaps.append((gz_topic, ros_topic))
    return bridges, remaps


def launch(context, *args, **kwargs):
    def arg(name):
        return LaunchConfiguration(name).perform(context)

    world = arg('world')
    headless = arg('headless').lower() == 'true'
    share = get_package_share_directory('asv_gazebo')
    actions = []

    # Verdenen lages med vindvalgene og legges først i stien Gazebo leter i. VRX-verdenene er faste.
    if world == 'open_water':
        out = tempfile.mkdtemp(prefix='asv_worlds_')
        mappings = {k: arg(k) for k in ('wind_speed', 'wind_direction', 'wind_gust', 'wave_period',
                                        'wave_direction')}
        # VRX vil ha gain, ikke høyde. Samme formel som VRX bruker.
        mappings['wave_gain'] = str(gain_for_height(float(arg('wave_height')), float(arg('wave_period'))))
        doc = xacro.process_file(
            os.path.join(share, 'worlds', 'open_water.sdf.xacro'), mappings=mappings)
        with open(os.path.join(out, 'open_water.sdf'), 'w') as f:
            f.write(doc.toxml())
        # Vannshaderen i VRX finner teksturene sine som materials/textures/ ved siden av fila vannet
        # ble lest fra. Vannet står i verdensfila, så den mappa må finnes her.
        os.symlink(os.path.join(get_package_share_directory('vrx_gz'), 'models', 'coast_waves',
                                'materials'), os.path.join(out, 'materials'))
        actions.append(AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', out, prepend=True))
    elif float(arg('wind_speed')) > 0:
        print(f'[asv.launch.py] Vind finnes bare i open_water, ikke i {world}. Kjører uten vind.')

    model = xacro.process_file(
        os.path.join(share, 'models', 'asv', 'model.sdf.xacro'),
        mappings={k: arg(k) for k in ('sensor_noise', 'current_speed', 'current_direction')}).toxml()

    joint_states = f'/world/{world}/model/asv/joint_state'
    actions += vrx_gz.launch.simulation(world, headless)
    actions += vrx_gz.launch.competition_bridges(world)
    spawn_args = ['-name', 'asv', '-string', model]
    # Startstedet står i asv_gazebo/scenario.py, så scenariene vet hvor båten starter.
    start = WORLDS[world]
    for key, value in (('x', start['x']), ('y', start['y']), ('z', start['z']), ('Y', start['yaw'])):
        spawn_args.extend(['-' + key, str(value)])
    actions.append(Node(
        package='ros_gz_sim', executable='create', output='screen', arguments=spawn_args))
    # Sensorene fra components.yaml går rett til /autonomy/..., uten sensor_relay.
    extra, remaps = sensor_bridges(os.path.join(share, 'models', 'asv', 'components.yaml'))
    actions.append(Node(
        package='ros_gz_bridge', executable='parameter_bridge', output='screen',
        arguments=BRIDGES + extra + [joint_states + '@sensor_msgs/msg/JointState[ignition.msgs.Model'],
        remappings=[(joint_states, '/asv/joint_states')] + remaps))
    return actions


def generate_launch_description():
    share = get_package_share_directory('asv_gazebo')
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='open_water', choices=list(WORLDS)),
        DeclareLaunchArgument('headless', default_value='False'),
        DeclareLaunchArgument('sensor_noise', default_value='false', description='true = støy på IMU og GPS'),
        DeclareLaunchArgument('current_speed', default_value='0', description='m/s, strøm'),
        DeclareLaunchArgument('current_direction', default_value='0', description='grader, 0 = mot øst'),
        DeclareLaunchArgument('wave_height', default_value='0.11',
                              description='m, største bølgeutslag over middelvannstand (open_water)'),
        DeclareLaunchArgument('wave_period', default_value='5', description='s (open_water)'),
        DeclareLaunchArgument('wave_direction', default_value='0.0', description='rad (open_water)'),
        DeclareLaunchArgument('wind_speed', default_value='0', description='m/s, bare open_water'),
        DeclareLaunchArgument('wind_direction', default_value='0', description='grader, 0 = mot øst'),
        DeclareLaunchArgument('wind_gust', default_value='0', description='0 = jevn vind'),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(share, 'models')),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(share, 'worlds')),
        OpaqueFunction(function=launch),
    ])
