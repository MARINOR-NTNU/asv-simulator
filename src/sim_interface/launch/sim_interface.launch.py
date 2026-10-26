"""Starter grensesnittet mot valgt simulator og båt: sim:=vrx, vrx_asv eller unity.

thrust_time_constant:=0.3 gir treghet i motorene (overstyrer verdien i config/<sim>.yaml).
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def nodes(context):
    config = PathJoinSubstitution(
        [FindPackageShare('sim_interface'), 'config', [LaunchConfiguration('sim'), '.yaml']])
    params = [config, {'use_sim_time': True}]
    # Overstyrer config/<sim>.yaml bare når argumentet er satt.
    tau = LaunchConfiguration('thrust_time_constant').perform(context)
    adapter_params = params + [{'thrust_time_constant': float(tau)}] if tau else params
    return [
        Node(package='sim_interface', executable='thruster_adapter', parameters=adapter_params),
        Node(package='sim_interface', executable='sensor_relay', parameters=params),
        Node(package='sim_interface', executable='heading_node', parameters=params),
        Node(package='sim_interface', executable='speed_node', parameters=params),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('sim', default_value='vrx', choices=['vrx', 'vrx_asv', 'unity']),
        DeclareLaunchArgument('thrust_time_constant', default_value='',
                              description='sekunder, treghet i motorene. Tom = verdien i config'),
        OpaqueFunction(function=nodes),
    ])
