"""Starter grensesnittet mot valgt simulator: sim:=vrx eller sim:=unity."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config = PathJoinSubstitution(
        [FindPackageShare('sim_interface'), 'config', [LaunchConfiguration('sim'), '.yaml']])
    params = [config, {'use_sim_time': True}]
    return LaunchDescription([
        DeclareLaunchArgument('sim', default_value='vrx', choices=['vrx', 'unity']),
        Node(package='sim_interface', executable='thruster_adapter', parameters=params),
        Node(package='sim_interface', executable='sensor_relay', parameters=params),
        Node(package='sim_interface', executable='heading_node', parameters=params),
    ])
