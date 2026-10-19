"""Følger en bane: grensesnittet, midlertidig control og waypoint_follower."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare('sim_interface')
    config = PathJoinSubstitution([share, 'config', [LaunchConfiguration('sim'), '.yaml']])
    path = PathJoinSubstitution([share, 'config', [LaunchConfiguration('path'), '.yaml']])

    return LaunchDescription([
        DeclareLaunchArgument('sim', default_value='vrx', choices=['vrx', 'vrx_asv', 'fast', 'unity']),
        DeclareLaunchArgument('path', default_value='path_demo'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([share, 'launch', 'sim_interface.launch.py'])),
            launch_arguments={'sim': LaunchConfiguration('sim')}.items()),
        Node(package='sim_interface', executable='waypoint_follower',
             parameters=[path, {'use_sim_time': True}]),
        Node(package='sim_interface', executable='stub_controller',
             parameters=[config, {'use_sim_time': True}]),
    ])
