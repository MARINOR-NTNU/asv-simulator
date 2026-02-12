FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Oslo

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    vim \
    nano \
    software-properties-common \
    lsb-release \
    gnupg2 \
    && rm -rf /var/lib/apt/lists/*

RUN wget https://packages.osrfoundation.org/gazebo.gpg -O /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

RUN apt-get update && apt-get install -y \
    gz-fortress \
    libgz-sim8-dev \
    libgz-plugin2-dev \
    libgz-common5-dev \
    libgz-math7-dev \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    libeigen3-dev \
    libyaml-cpp-dev \
    libgtest-dev \
    libgmock-dev \
    libspdlog-dev \
    && rm -rf /var/lib/apt/lists/*

RUN add-apt-repository universe && \
    curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" | tee /etc/apt/sources.list.d/ros2.list > /dev/null

RUN apt-get update && apt-get install -y \
    ros-humble-desktop \
    ros-humble-ros-gz \
    python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

ARG USERNAME=asvdev
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && apt-get update \
    && apt-get install -y sudo \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && rm -rf /var/lib/apt/lists/*

RUN echo "source /opt/ros/humble/setup.bash" >> /home/$USERNAME/.bashrc

WORKDIR /workspace
RUN mkdir -p /workspace/asv-simulator && chown -R $USERNAME:$USERNAME /workspace

USER $USERNAME

ENV GZ_SIM_RESOURCE_PATH=/workspace/asv-simulator/models:/workspace/asv-simulator/worlds
ENV GZ_SIM_SYSTEM_PLUGIN_PATH=/workspace/asv-simulator/build/src/gazebo_plugins

COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/bin/bash"]