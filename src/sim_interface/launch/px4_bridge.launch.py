"""Starter koblingen mot control sin PX4. Startes i tillegg til sim_interface.launch.py."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def nodes(context):
    config = PathJoinSubstitution([FindPackageShare('sim_interface'), 'config', 'px4_bridge.yaml'])
    params = [config, {'use_sim_time': True}]
    # Overstyrer px4_bridge.yaml bare når argumentet er satt.
    forward = LaunchConfiguration('forward_thruster').perform(context)
    motor_params = params + [{'forward_thruster': forward}] if forward else params
    return [
        Node(package='sim_interface', executable='px4_motor_bridge', parameters=motor_params),
        Node(package='sim_interface', executable='px4_seapath_bridge', parameters=params),
        # Sensordata og klokke til PX4 over MAVLink. Gjør ingenting før PX4 kobler seg til (SITL).
        Node(package='sim_interface', executable='px4_hil_bridge', parameters=params),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'forward_thruster', default_value='',
            description='Motoren forward_propeller_thrust sendes til, f.eks. bow. Tom = ignoreres.'),
        OpaqueFunction(function=nodes),
    ])
