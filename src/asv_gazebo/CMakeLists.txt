cmake_minimum_required(VERSION 3.8)
project(asv_gazebo)

find_package(ament_cmake REQUIRED)
find_program(XACRO xacro REQUIRED)

# model.sdf lages fra model.sdf.xacro og filene i xacro/. Gazebo og asv_fastsim leser den
# installerte model.sdf.
set(MODEL_DIR ${CMAKE_CURRENT_SOURCE_DIR}/models/asv)
file(GLOB MODEL_XACRO ${MODEL_DIR}/model.sdf.xacro ${MODEL_DIR}/xacro/*.xacro)
add_custom_command(
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/model.sdf
  COMMAND ${XACRO} ${MODEL_DIR}/model.sdf.xacro -o ${CMAKE_CURRENT_BINARY_DIR}/model.sdf
  DEPENDS ${MODEL_XACRO}
  COMMENT "Lager model.sdf fra xacro")
add_custom_target(asv_model ALL DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/model.sdf)

install(DIRECTORY models launch DESTINATION share/${PROJECT_NAME}
  PATTERN "*.xacro" EXCLUDE PATTERN "xacro" EXCLUDE)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/model.sdf DESTINATION share/${PROJECT_NAME}/models/asv)

ament_package()
