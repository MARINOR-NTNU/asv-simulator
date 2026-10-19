"""Starter simulatoren og grensesnittet, med valg for hva som står for autonomy og control.

  sim:=vrx_asv | vrx | fast     vår båt (standard), WAM-V, eller vår båt i den raske 2D-simulatoren
  control:=none | stub | px4    ingen, stub_controller, eller control sin PX4 (broene og agenten)
  autonomy:=none | fake | path  ingen, fake_heading, eller waypoint_follower

control er ett valg, så stub_controller og PX4 kan ikke styre motorene samtidig.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, IncludeLaunchDescription
from launch.conditions import LaunchConfigurationEquals
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def include(package, name, arguments, condition=None):
    path = PathJoinSubstitution([FindPackageShare(package), 'launch', name])
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(path), launch_arguments=arguments.items(),
        condition=condition)


def generate_launch_description():
    def arg(name):
        return LaunchConfiguration(name)

    def number(name):
        return ParameterValue(arg(name), value_type=float)

    def when(name, value):
        return LaunchConfigurationEquals(name, value)

    share = FindPackageShare('sim_interface')
    config = PathJoinSubstitution([share, 'config', [arg('sim'), '.yaml']])
    path = PathJoinSubstitution([share, 'config', [arg('path'), '.yaml']])
    sim_time = {'use_sim_time': True}

    return LaunchDescription([
        DeclareLaunchArgument('sim', default_value='vrx_asv', choices=['vrx_asv', 'vrx', 'fast']),
        DeclareLaunchArgument(
            'real_time_factor', default_value='1.0',
            description='sim:=fast: 1 = sanntid, 10 = ti ganger raskere, 0 = så fort det går'),
        DeclareLaunchArgument('headless', default_value='false', description='true = uten Gazebo-vindu'),
        DeclareLaunchArgument('control', default_value='none', choices=['none', 'stub', 'px4']),
        DeclareLaunchArgument('autonomy', default_value='none', choices=['none', 'fake', 'path']),
        DeclareLaunchArgument('heading', default_value='0.0', description='autonomy:=fake, radianer ENU'),
        DeclareLaunchArgument('speed', default_value='1.0', description='autonomy:=fake, m/s'),
        DeclareLaunchArgument('sweep_rate', default_value='0.0', description='autonomy:=fake'),
        DeclareLaunchArgument('path', default_value='path_demo', description='autonomy:=path'),
        DeclareLaunchArgument(
            'forward_thruster', default_value='',
            description='control:=px4: motoren forward_propeller_thrust sendes til, f.eks. bow'),
        DeclareLaunchArgument('agent_port', default_value='8888', description='control:=px4'),

        # Simulatoren
        include('asv_gazebo', 'asv.launch.py', {'headless': arg('headless')},
                when('sim', 'vrx_asv')),
        include('vrx_gz', 'competition.launch.py',
                {'world': 'sydney_regatta', 'headless': arg('headless')}, when('sim', 'vrx')),
        # Den raske simulatoren er klokka selv, så den kjører ikke med use_sim_time.
        Node(package='asv_fastsim', executable='fastsim', condition=when('sim', 'fast'),
             parameters=[{'real_time_factor': number('real_time_factor')}]),

        # Grensesnittet (thruster_adapter, sensor_relay, heading_node, speed_node)
        include('sim_interface', 'sim_interface.launch.py', {'sim': arg('sim')}),

        # Autonomy
        Node(package='sim_interface', executable='fake_heading', condition=when('autonomy', 'fake'),
             parameters=[{**sim_time, 'heading': number('heading'), 'speed': number('speed'),
                          'sweep_rate': number('sweep_rate')}]),
        Node(package='sim_interface', executable='waypoint_follower',
             condition=when('autonomy', 'path'), parameters=[path, sim_time]),

        # Control
        Node(package='sim_interface', executable='stub_controller', condition=when('control', 'stub'),
             parameters=[config, sim_time]),
        include('sim_interface', 'px4_bridge.launch.py',
                {'forward_thruster': arg('forward_thruster')}, when('control', 'px4')),
        ExecuteProcess(
            cmd=['MicroXRCEAgent', 'udp4', '-p', arg('agent_port')], output='screen',
            condition=when('control', 'px4')),
    ])
