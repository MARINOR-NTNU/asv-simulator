"""Starter grensesnittet mot valgt simulator og båt: sim:=vrx, vrx_asv eller unity."""
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
        DeclareLaunchArgument('sim', default_value='vrx', choices=['vrx', 'vrx_asv', 'unity']),
        Node(package='sim_interface', executable='thruster_adapter', parameters=params),
        Node(package='sim_interface', executable='sensor_relay', parameters=params),
        Node(package='sim_interface', executable='heading_node', parameters=params),
        Node(package='sim_interface', executable='speed_node', parameters=params),
    ])
