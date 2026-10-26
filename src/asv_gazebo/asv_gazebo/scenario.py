"""Testoppsett (scenarier): hvilke ting som står i verdenen, og hvor.

Et scenario er en yaml-fil i scenarios/ med en liste over ting. Posisjonene er x, y i meter
(øst, nord) fra båtens startsted, så samme scenario kan brukes i alle verdenene. Hver type ting
har én funksjon som lager SDF-en. En ny type legges til med en ny funksjon i TYPES.

Ingen ROS-avhengigheter utenom pakkestien, så modulen kan brukes av launch-filer og noder.
"""
import os

import yaml
from ament_index_python.packages import get_package_share_directory

# Båtens startsted i hver verden (meter i verdenens koordinater, og yaw i radianer). z er løftet
# slik at vannlinjen havner i z = 0. open_water har GPS-origo der båten starter i sydney_regatta,
# så båten starter på samme GPS-posisjon i begge.
WORLDS = {
    'open_water': {'x': 0.0, 'y': 0.0, 'z': 0.145, 'yaw': 1.0},
    'sydney_regatta': {'x': -532.0, 'y': 162.0, 'z': 0.145, 'yaw': 1.0},
}

# Bøyerekka som følger med sydney_regatta (x = -528, y = 186 til 191). Fjernes før et scenario
# settes inn, så bare scenariets ting står der.
SYDNEY_BUOYS = ['mb_marker_buoy_red', 'mb_marker_buoy_black', 'mb_marker_buoy_green',
                'mb_marker_buoy_white', 'mb_round_buoy_orange', 'mb_round_buoy_black']

COLORS = {
    'red': '0.7921 0.0039 0.0274',
    'green': '0.0 0.6 0.1',
    'yellow': '0.9 0.75 0.0',
    'white': '0.9 0.9 0.9',
    'black': '0.05 0.05 0.05',
}

MARKER_MESH = ('https://fuel.gazebosim.org/1.0/openrobotics/models/mb_marker_buoy_red/'
               'tip/files/meshes/mb_marker_buoy.dae')


def buoy(name, color='red'):
    """Markørbøye, samme form, masse og oppdrift som mb_marker_buoy_* i sydney_regatta."""
    rgb = COLORS[color]
    return f"""<sdf version="1.9"><model name="{name}">
<link name="link">
  <inertial><pose>0 0 -0.3 0 0 0</pose><mass>20</mass>
    <inertia><ixx>2.316</ixx><iyy>2.316</iyy><izz>0.225</izz></inertia></inertial>
  <collision name="collision_inner"><pose>0 -0.02 0.02 0 0 0</pose>
    <geometry><cylinder><radius>0.15</radius><length>1.15</length></cylinder></geometry></collision>
  <collision name="collision_outer"><pose>0 0 -0.3 0 0 0</pose>
    <geometry><cylinder><radius>0.325</radius><length>0.1</length></cylinder></geometry></collision>
  <visual name="visual"><pose>0 0 0 1.57079 0 0</pose>
    <geometry><mesh><uri>{MARKER_MESH}</uri></mesh></geometry>
    <material><ambient>{rgb}</ambient><diffuse>{rgb}</diffuse></material></visual>
</link>
<plugin name="vrx::PolyhedraBuoyancyDrag" filename="libPolyhedraBuoyancyDrag.so">
  <fluid_density>1000</fluid_density><fluid_level>0.0</fluid_level>
  <linear_drag>25.0</linear_drag><angular_drag>2.0</angular_drag>
  <buoyancy name="collision_outer"><link_name>link</link_name><pose>0 0 -0.3 0 0 0</pose>
    <geometry><cylinder><radius>0.325</radius><length>0.1</length></cylinder></geometry></buoyancy>
  <wavefield><topic>/vrx/wavefield/parameters</topic></wavefield>
</plugin>
</model></sdf>"""


# type i scenariofila -> funksjon. Feltene utenom type, name, x, y og yaw sendes til funksjonen.
TYPES = {
    'buoy': buoy,
}


def path(scenario):
    """Stien til et scenario: et navn i scenarios/ (uten .yaml) eller en sti til en fil."""
    if os.path.isfile(scenario):
        return scenario
    return os.path.join(
        get_package_share_directory('asv_gazebo'), 'scenarios', f'{scenario}.yaml')


def load(scenario):
    """Tingene i et scenario, som en liste med dicts (type, name, x, y, yaw og egne felt)."""
    with open(path(scenario)) as f:
        objects = (yaml.safe_load(f) or {}).get('objects', [])
    for obj in objects:
        if obj['type'] not in TYPES:
            raise ValueError(f'Ukjent type {obj["type"]!r} i {scenario}. Kjente: {", ".join(TYPES)}')
    return objects


def sdf(obj):
    """SDF-en til én ting fra scenariofila."""
    extra = {k: v for k, v in obj.items() if k not in ('type', 'name', 'x', 'y', 'yaw')}
    return TYPES[obj['type']](obj['name'], **extra)


def world_pose(obj, world):
    """Posisjonen til en ting i verdenens koordinater: (x, y, yaw)."""
    start = WORLDS[world]
    return start['x'] + obj['x'], start['y'] + obj['y'], obj.get('yaw', 0.0)
