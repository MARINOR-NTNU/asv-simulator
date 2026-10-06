# asv-simulator

Felles VRX-simulator for gruppen, kjørt lokalt i Docker: Ubuntu 22.04, ROS 2 Humble, Gazebo Garden og VRX (`humble`-grenen). Hver person kjører sin egen simulator, og vi deler Dockerfile og kode via git.

## Bygg
```bash
docker build -t vrx-sim:humble-garden .
```
Bygget tar ca. 15–20 min. `ros_gz_bridge` kan stå i over 10 min uten ny output, og det er normalt.

Har maskinen lite RAM, kan du kjøre bygget i bakgrunnen og følge med i loggen:
```bash
nohup docker build -t vrx-sim:humble-garden . > build.log 2>&1 &
tail -n 5 build.log
```

## Kjør (med Gazebo-vindu)
Kjør fra roten av repoet:
```bash
xhost +local:docker
docker run -it --rm --net=host \
  -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix \
  --device /dev/dri \
  -v $(pwd)/src:/root/vrx_ws/src/mysrc \
  vrx-sim:humble-garden
# i containeren:
ros2 launch vrx_gz competition.launch.py world:=sydney_regatta
```
Uten vindu: legg til `headless:=true` på launch-kommandoen.

- `--device /dev/dri` gir tilgang til GPU-en, som kamerasensorene trenger.
- `src/` fra repoet monteres inn som `/root/vrx_ws/src/mysrc`. Pakker der må bygges i containeren med `colcon build --merge-install`.

## Topics (utkast)
Fra control til simulatoren:

| Topic | Type | Enhet |
|---|---|---|
| `/control/thruster/{left,right}/thrust` | `std_msgs/Float64` | newton |
| `/control/thruster/{left,right}/angle` | `std_msgs/Float64` | radianer |

`thruster_adapter` skal sende disse videre til VRX sine `/wamv/thrusters/{left,right}/{thrust,pos}`.

## Status
- Docker-imaget `vrx-sim:humble-garden` er bygget og testet. Simulatoren starter både med Gazebo-vindu og headless, og sensorene og motorene virker.
- `sim_interface` (`thruster_adapter`) er under arbeid.
- PX4-koblingen via uXRCE-DDS er ikke startet, fordi vi venter på svar fra control.
