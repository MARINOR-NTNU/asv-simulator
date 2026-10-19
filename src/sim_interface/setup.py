from glob import glob

from setuptools import setup

package_name = 'sim_interface'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='chris',
    maintainer_email='christufte@icloud.com',
    description='Simulatoruavhengig grensesnitt mellom autonomy/control og ASV-simulatoren.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'thruster_adapter = sim_interface.thruster_adapter:main',
            'sensor_relay = sim_interface.sensor_relay:main',
            'heading_node = sim_interface.heading_node:main',
            'speed_node = sim_interface.speed_node:main',
            'fake_heading = sim_interface.fake_heading:main',
            'stub_controller = sim_interface.stub_controller:main',
            'waypoint_follower = sim_interface.waypoint_follower:main',
            'px4_motor_bridge = sim_interface.px4_motor_bridge:main',
            'px4_seapath_bridge = sim_interface.px4_seapath_bridge:main',
            'px4_check = sim_interface.px4_check:main',
        ],
    },
)
