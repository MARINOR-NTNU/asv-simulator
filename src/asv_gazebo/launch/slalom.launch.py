"""Legger ut en slalåmløype i en kjørende verden (world:=open_water eller sydney_regatta).

Startes etter asv.launch.py, med samme world. Banen gjennom løypa er sim_interface/config/path_slalom.yaml.
Fire bøyer står på linje nordover i x = 0 (meter øst/nord fra startstedet til båten), 7 m
fra hverandre. Båten skal annenhver gang på østsiden og vestsiden av dem. Rød bøye skal
ligge på babord side når båten passerer, grønn på styrbord.

I sydney_regatta fjernes også bøyerekka som følger med verdenen, slik at bare løypa står igjen.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction, TimerAction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# Startstedet til båten per verden, samme som SPAWN i asv.launch.py.
ORIGIN = {'open_water': (0.0, 0.0), 'sydney_regatta': (-532.0, 162.0)}

# (navn, farge, x, y) i meter fra startstedet. Båten kjører nordover og passerer
# 1 og 3 på østsiden (bøyen er på babord) og 2 og 4 på vestsiden (bøyen er på styrbord).
BUOYS = [
    ('slalom1_red', 'red', 0.0, 4.0),
    ('slalom2_green', 'green', 0.0, 11.0),
    ('slalom3_red', 'red', 0.0, 18.0),
    ('slalom4_green', 'green', 0.0, 25.0),
]

# Bøyerekka fra sydney_regatta.sdf (x = -528, y = 186 til 191).
WORLD_BUOYS = ['mb_marker_buoy_red', 'mb_marker_buoy_black', 'mb_marker_buoy_green',
               'mb_marker_buoy_white', 'mb_round_buoy_orange', 'mb_round_buoy_black']

COLORS = {'red': '0.7921 0.0039 0.0274', 'green': '0.0 0.6 0.1'}

MESH = ('https://fuel.gazebosim.org/1.0/openrobotics/models/mb_marker_buoy_red/'
        'tip/files/meshes/mb_marker_buoy.dae')

# Samme bøye og oppdrift som mb_marker_buoy_* i sydney_regatta.sdf.
SDF = """<sdf version="1.9"><model name="{name}">
<link name="link">
  <inertial><pose>0 0 -0.3 0 0 0</pose><mass>20</mass>
    <inertia><ixx>2.316</ixx><iyy>2.316</iyy><izz>0.225</izz></inertia></inertial>
  <collision name="collision_inner"><pose>0 -0.02 0.02 0 0 0</pose>
    <geometry><cylinder><radius>0.15</radius><length>1.15</length></cylinder></geometry></collision>
  <collision name="collision_outer"><pose>0 0 -0.3 0 0 0</pose>
    <geometry><cylinder><radius>0.325</radius><length>0.1</length></cylinder></geometry></collision>
  <visual name="visual"><pose>0 0 0 1.57079 0 0</pose>
    <geometry><mesh><uri>{mesh}</uri></mesh></geometry>
    <material><ambient>{color}</ambient><diffuse>{color}</diffuse></material></visual>
</link>
<plugin name="vrx::PolyhedraBuoyancyDrag" filename="libPolyhedraBuoyancyDrag.so">
  <fluid_density>1000</fluid_density><fluid_level>0.0</fluid_level>
  <linear_drag>25.0</linear_drag><angular_drag>2.0</angular_drag>
  <buoyancy name="collision_outer"><link_name>link</link_name><pose>0 0 -0.3 0 0 0</pose>
    <geometry><cylinder><radius>0.325</radius><length>0.1</length></cylinder></geometry></buoyancy>
  <wavefield><topic>/vrx/wavefield/parameters</topic></wavefield>
</plugin>
</model></sdf>"""


def launch(context):
    world = LaunchConfiguration('world').perform(context)
    ox, oy = ORIGIN[world]
    removals = [ExecuteProcess(output='screen', cmd=[
        'gz', 'service', '-s', f'/world/{world}/remove',
        '--reqtype', 'gz.msgs.Entity', '--reptype', 'gz.msgs.Boolean', '--timeout', '5000',
        '--req', f'name: "{name}" type: MODEL'])
        for name in WORLD_BUOYS] if world == 'sydney_regatta' else []
    spawns = []
    for name, color, x, y in BUOYS:
        sdf = SDF.format(name=name, mesh=MESH, color=COLORS[color])
        spawns.append(Node(
            package='ros_gz_sim', executable='create', output='screen',
            arguments=['-name', name, '-string', sdf,
                       '-x', str(ox + x), '-y', str(oy + y), '-z', '0']))
    # Venter litt så fjerningen er ferdig før løypa settes inn.
    return removals + [TimerAction(period=3.0, actions=spawns)]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('world', default_value='open_water', choices=list(ORIGIN)),
        OpaqueFunction(function=launch),
    ])
