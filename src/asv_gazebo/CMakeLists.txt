cmake_minimum_required(VERSION 3.8)
project(asv_gazebo)

find_package(ament_cmake REQUIRED)

install(DIRECTORY models launch DESTINATION share/${PROJECT_NAME})

ament_package()
