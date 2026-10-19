"""Starter koblingen mot control sin PX4. Startes i tillegg til sim_interface.launch.py."""
from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    config = PathJoinSubstitution([FindPackageShare('sim_interface'), 'config', 'px4_bridge.yaml'])
    params = [config, {'use_sim_time': True}]
    return LaunchDescription([
        Node(package='sim_interface', executable='px4_motor_bridge', parameters=params),
        Node(package='sim_interface', executable='px4_seapath_bridge', parameters=params),
    ])
