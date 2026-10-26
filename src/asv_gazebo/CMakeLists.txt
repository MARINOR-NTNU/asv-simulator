cmake_minimum_required(VERSION 3.8)
project(asv_gazebo)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_program(XACRO xacro REQUIRED)

# model.sdf lages fra model.sdf.xacro og filene i xacro/ som standardversjon (uten valg). Ved oppstart
# lager asv.launch.py modellen på nytt med valgene som er gitt.
set(MODEL_DIR ${CMAKE_CURRENT_SOURCE_DIR}/models/asv)
file(GLOB MODEL_XACRO ${MODEL_DIR}/model.sdf.xacro ${MODEL_DIR}/xacro/*.xacro)
add_custom_command(
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/model.sdf
  COMMAND ${XACRO} ${MODEL_DIR}/model.sdf.xacro -o ${CMAKE_CURRENT_BINARY_DIR}/model.sdf
  DEPENDS ${MODEL_XACRO}
  COMMENT "Lager model.sdf fra xacro")
add_custom_target(asv_model ALL DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/model.sdf)

# Verdenene lages på samme måte, og Gazebo finner dem ved navn (asv.launch.py legger mappa til
# GZ_SIM_RESOURCE_PATH).
file(GLOB WORLD_XACRO ${CMAKE_CURRENT_SOURCE_DIR}/worlds/*.sdf.xacro)
foreach(src ${WORLD_XACRO})
  get_filename_component(name ${src} NAME_WE)
  add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/worlds/${name}.sdf
    COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_CURRENT_BINARY_DIR}/worlds
    COMMAND ${XACRO} ${src} -o ${CMAKE_CURRENT_BINARY_DIR}/worlds/${name}.sdf
    DEPENDS ${src}
    COMMENT "Lager ${name}.sdf fra xacro")
  list(APPEND WORLDS ${CMAKE_CURRENT_BINARY_DIR}/worlds/${name}.sdf)
endforeach()
add_custom_target(asv_worlds ALL DEPENDS ${WORLDS})

# Vannflaten til open_water: tett rutenett rundt båten (se scripts/make_ocean_mesh.py).
find_package(Python3 REQUIRED COMPONENTS Interpreter)
add_custom_command(
  OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/ocean.obj
  COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/scripts/make_ocean_mesh.py
          ${CMAKE_CURRENT_BINARY_DIR}/ocean.obj
  DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/scripts/make_ocean_mesh.py
  COMMENT "Lager vannflaten ocean.obj")
add_custom_target(asv_ocean ALL DEPENDS ${CMAKE_CURRENT_BINARY_DIR}/ocean.obj)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/ocean.obj DESTINATION share/${PROJECT_NAME}/models/ocean/meshes)

# asv_gazebo.scenario: scenarier og startsteder, brukt av launch-filene.
ament_python_install_package(${PROJECT_NAME})

# xacro-filene installeres også, fordi asv.launch.py lager modellen og open_water med valgene som
# gis ved oppstart (sensorstøy, vind). De genererte filene under er standardversjonene.
install(DIRECTORY models launch scenarios DESTINATION share/${PROJECT_NAME})
install(FILES ${WORLD_XACRO} DESTINATION share/${PROJECT_NAME}/worlds)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/model.sdf DESTINATION share/${PROJECT_NAME}/models/asv)
install(FILES ${WORLDS} DESTINATION share/${PROJECT_NAME}/worlds)

ament_package()
