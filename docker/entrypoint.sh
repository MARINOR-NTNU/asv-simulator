#!/bin/bash
set -e

if [ -f "/opt/ros/humble/setup.bash" ]; then
    source /opt/ros/humble/setup.bash
fi

if [ -f "/workspace/asv-simulator/install/setup.bash" ]; then
    source /workspace/asv-simulator/install/setup.bash
fi

export GZ_SIM_RESOURCE_PATH=/workspace/asv-simulator/models:/workspace/asv-simulator/worlds:$GZ_SIM_RESOURCE_PATH
export GZ_SIM_SYSTEM_PLUGIN_PATH=/workspace/asv-simulator/build/src/gazebo_plugins:$GZ_SIM_SYSTEM_PLUGIN_PATH

sudo chown -R asvdev:asvdev /workspace/asv-simulator 2>/dev/null || true

exec "$@"