"""Starter en verden med vår egen ASV: open_water (vår, uten land) eller en VRX-verden som sydney_regatta."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import AppendEnvironmentVariable, DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import vrx_gz.launch

# Startsted per verden. z er løftet slik at vannlinjen havner i z = 0. I sydney_regatta er det
# samme sted som WAM-V, og open_water har GPS-origo der, så båten starter på samme GPS-posisjon.
SPAWN = {
    'open_water': {'x': '0', 'y': '0', 'z': '0.145', 'Y': '1.0'},
    'sydney_regatta': {'x': '-532', 'y': '162', 'z': '0.145', 'Y': '1.0'},
}

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
    world = LaunchConfiguration('world').perform(context)
    headless = LaunchConfiguration('headless').perform(context).lower() == 'true'
    model = os.path.join(
        get_package_share_directory('asv_gazebo'), 'models', 'asv', 'model.sdf')

    joint_states = f'/world/{world}/model/asv/joint_state'

    processes = vrx_gz.launch.simulation(world, headless)
    processes.extend(vrx_gz.launch.competition_bridges(world))
    spawn_args = ['-name', 'asv', '-file', model]
    for key, value in SPAWN[world].items():
        spawn_args.extend(['-' + key, value])
    processes.append(Node(
        package='ros_gz_sim', executable='create', output='screen', arguments=spawn_args))
    processes.append(Node(
        package='ros_gz_bridge', executable='parameter_bridge', output='screen',
        arguments=BRIDGES + [joint_states + '@sensor_msgs/msg/JointState[ignition.msgs.Model'],
        remappings=[(joint_states, '/asv/joint_states')]))
    return processes


def generate_launch_description():
    share = get_package_share_directory('asv_gazebo')
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='open_water', choices=list(SPAWN)),
        DeclareLaunchArgument('headless', default_value='False'),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(share, 'models')),
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH', os.path.join(share, 'worlds')),
        OpaqueFunction(function=launch),
    ])
