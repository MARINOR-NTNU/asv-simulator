"""Starter en verden med vår egen ASV: open_water (vår, uten land) eller en VRX-verden som sydney_regatta.

Modellen og open_water lages fra xacro når den startes, med valgene under:
  sensor_noise:=true     støy på IMU og GPS
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

from asv_gazebo.scenario import WORLDS

BRIDGES = [
    '/asv/thrusters/left/thrust@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/thrusters/right/thrust@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/thrusters/bow/thrust@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/thrusters/left/pos@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/thrusters/right/pos@std_msgs/msg/Float64]ignition.msgs.Double',
    '/asv/sensors/imu@sensor_msgs/msg/Imu[ignition.msgs.IMU',
    '/asv/sensors/gps@sensor_msgs/msg/NavSatFix[ignition.msgs.NavSat',
]


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
        doc = xacro.process_file(
            os.path.join(share, 'worlds', 'open_water.sdf.xacro'),
            mappings={k: arg(k) for k in ('wind_speed', 'wind_direction', 'wind_gust')})
        with open(os.path.join(out, 'open_water.sdf'), 'w') as f:
            f.write(doc.toxml())
        actions.append(AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', out, prepend=True))
    elif float(arg('wind_speed')) > 0:
        print(f'[asv.launch.py] Vind finnes bare i open_water, ikke i {world}. Kjører uten vind.')

    model = xacro.process_file(
        os.path.join(share, 'models', 'asv', 'model.sdf.xacro'),
        mappings={'sensor_noise': arg('sensor_noise')}).toxml()

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
    actions.append(Node(
        package='ros_gz_bridge', executable='parameter_bridge', output='screen',
        arguments=BRIDGES + [joint_states + '@sensor_msgs/msg/JointState[ignition.msgs.Model'],
        remappings=[(joint_states, '/asv/joint_states')]))
    return actions


def generate_launch_description():
    share = get_package_share_directory('asv_gazebo')
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='open_water', choices=list(WORLDS)),
        DeclareLaunchArgument('headless', default_value='False'),
        DeclareLaunchArgument('sensor_noise', default_value='false', description='true = støy på IMU og GPS'),
        DeclareLaunchArgument('wind_speed', default_value='0', description='m/s, bare open_water'),
        DeclareLaunchArgument('wind_direction', default_value='0', description='grader, 0 = mot øst'),
        DeclareLaunchArgument('wind_gust', default_value='0', description='0 = jevn vind'),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(share, 'models')),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(share, 'worlds')),
        OpaqueFunction(function=launch),
    ])
