"""Setter inn tingene i et scenario (scenarios/<navn>.yaml) i en kjørende verden.

  ros2 launch asv_gazebo scenario.launch.py scenario:=slalom world:=open_water

world må være den samme som simulatoren kjører. scenario kan også være en sti til en yaml-fil.
I sydney_regatta fjernes først bøyerekka som følger med verdenen.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from asv_gazebo import scenario as sc


def launch(context):
    world = LaunchConfiguration('world').perform(context)
    removals = [ExecuteProcess(output='screen', cmd=[
        'gz', 'service', '-s', f'/world/{world}/remove',
        '--reqtype', 'gz.msgs.Entity', '--reptype', 'gz.msgs.Boolean', '--timeout', '5000',
        '--req', f'name: "{name}" type: MODEL'])
        for name in sc.SYDNEY_BUOYS] if world == 'sydney_regatta' else []
    spawns = []
    for obj in sc.load(LaunchConfiguration('scenario').perform(context)):
        x, y, yaw = sc.world_pose(obj, world)
        spawns.append(Node(
            package='ros_gz_sim', executable='create', output='screen',
            arguments=['-world', world, '-name', obj['name'], '-string', sc.sdf(obj),
                       '-x', str(x), '-y', str(y), '-z', '0', '-Y', str(yaw)]))
    # Venter litt så fjerningen er ferdig før tingene settes inn.
    return removals + [TimerAction(period=3.0, actions=spawns)] if removals else spawns


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('scenario', description='navn i scenarios/ eller sti til en yaml-fil'),
        DeclareLaunchArgument('world', default_value='open_water', choices=list(sc.WORLDS)),
        OpaqueFunction(function=launch),
    ])
