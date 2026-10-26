cmake_minimum_required(VERSION 3.8)
project(asv_hydrodynamics)

find_package(ament_cmake REQUIRED)
find_package(gz-sim7 REQUIRED)
find_package(gz-plugin2 REQUIRED COMPONENTS register)
find_package(sdformat13 REQUIRED)
find_package(Eigen3 REQUIRED)

# Gazebo-plugin. Installeres i lib/, der Gazebo i VRX-imaget allerede leter etter plugins.
add_library(CurrentHydrodynamics SHARED src/CurrentHydrodynamics.cc)
target_include_directories(CurrentHydrodynamics PRIVATE ${EIGEN3_INCLUDE_DIRS})
target_link_libraries(CurrentHydrodynamics PUBLIC
  gz-sim7::core
  gz-plugin2::register
  sdformat13::sdformat13)
install(TARGETS CurrentHydrodynamics DESTINATION lib)

ament_package()
