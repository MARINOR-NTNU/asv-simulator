from setuptools import setup

package_name = 'asv_fastsim'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='chris',
    maintainer_email='christufte@icloud.com',
    description='Rask 2D-simulator av vår båt, uten grafikk, for mange tester.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'fastsim = asv_fastsim.fastsim_node:main',
        ],
    },
)
