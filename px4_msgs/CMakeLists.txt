cmake_minimum_required(VERSION 3.8)
project(px4_msgs)

find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(rosidl_default_generators REQUIRED)

# Meldingene kopieres inn med scripts/sync_px4_msgs.sh
file(GLOB PX4_MSGS RELATIVE "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/msg/*.msg")

rosidl_generate_interfaces(${PROJECT_NAME}
  ${PX4_MSGS}
  DEPENDENCIES builtin_interfaces
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
