FROM osrf/ros:humble-desktop

ENV DEBIAN_FRONTEND=noninteractive
ENV GZ_VERSION=garden

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget lsb-release gnupg git python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Gazebo Garden fra OSRF-repoet
RUN wget https://packages.osrfoundation.org/gazebo.gpg -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" > /etc/apt/sources.list.d/gazebo-stable.list \
 && apt-get update \
 && apt-get install -y gz-garden python3-sdformat13 ros-humble-joy ros-humble-topic-tools \
 && rm -rf /var/lib/apt/lists/*

# VRX og ros_gz (humble-grenene) i en workspace
WORKDIR /root/vrx_ws/src
RUN git clone -b humble https://github.com/osrf/vrx.git \
 && git clone -b humble https://github.com/gazebosim/ros_gz.git

WORKDIR /root/vrx_ws
RUN apt-get update \
 && rosdep update \
 && rosdep install -r --from-paths src -i -y --rosdistro humble \
      --skip-keys "gz-cmake3 gz-common5 gz-fuel-tools8 gz-gui7 gz-launch6 gz-math7 gz-msgs9 gz-physics6 gz-plugin2 gz-rendering7 gz-sensors7 gz-sim7 gz-tools2 gz-transport12 gz-utils2 sdformat13" \
 && rm -rf /var/lib/apt/lists/*

# Ett kompileringsløp om gangen, så bygget ikke tar alt minnet
RUN . /opt/ros/humble/setup.sh \
 && MAKEFLAGS="-j1" colcon build --merge-install --executor sequential --parallel-workers 1

# Micro XRCE-DDS Agent v2.4.2 (v2-protokollen PX4 bruker som standard, anbefalt for Humble).
# Bygges mot Fast-DDS fra ROS Humble, fordi standardbygget laster ned en Fast-DDS-gren som ikke finnes lenger.
RUN . /opt/ros/humble/setup.sh \
 && git clone --depth 1 -b v2.4.2 https://github.com/eProsima/Micro-XRCE-DDS-Agent.git /tmp/xrce_agent \
 && cmake -S /tmp/xrce_agent -B /tmp/xrce_agent/build -DUAGENT_USE_SYSTEM_FASTDDS=ON -DUAGENT_USE_SYSTEM_FASTCDR=ON \
 && MAKEFLAGS="-j1" cmake --build /tmp/xrce_agent/build \
 && cmake --install /tmp/xrce_agent/build \
 && ldconfig \
 && rm -rf /tmp/xrce_agent

# PX4-meldingene fra control (se px4_msgs/SOURCE.txt). Eget lag etter VRX, så VRX ikke bygges på nytt.
COPY px4_msgs /root/vrx_ws/src/px4_msgs
RUN . /opt/ros/humble/setup.sh \
 && MAKEFLAGS="-j1" colcon build --merge-install --executor sequential --parallel-workers 1 --packages-select px4_msgs

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
