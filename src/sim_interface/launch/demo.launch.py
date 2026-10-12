"""Hele kjeden med midlertidige erstatninger for autonomy og control."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    def number(name):
        return ParameterValue(LaunchConfiguration(name), value_type=float)

    config = PathJoinSubstitution(
        [FindPackageShare('sim_interface'), 'config', [LaunchConfiguration('sim'), '.yaml']])

    return LaunchDescription([
        DeclareLaunchArgument('sim', default_value='vrx', choices=['vrx', 'vrx_asv', 'unity']),
        DeclareLaunchArgument('heading', default_value='0.0'),
        DeclareLaunchArgument('speed', default_value='1.0'),
        DeclareLaunchArgument('sweep_rate', default_value='0.0'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(PathJoinSubstitution(
                [FindPackageShare('sim_interface'), 'launch', 'sim_interface.launch.py'])),
            launch_arguments={'sim': LaunchConfiguration('sim')}.items()),
        Node(package='sim_interface', executable='fake_heading', parameters=[{
            'use_sim_time': True,
            'heading': number('heading'),
            'speed': number('speed'),
            'sweep_rate': number('sweep_rate'),
        }]),
        Node(package='sim_interface', executable='stub_controller',
             parameters=[config, {'use_sim_time': True}]),
    ])
