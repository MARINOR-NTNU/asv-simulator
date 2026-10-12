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

## sim_interface
Pakken `src/sim_interface` er grensesnittet mellom autonomy/control og simulatoren. Autonomy og control bruker bare de faste topicene under, så de vet ikke hvilken simulator som kjører. Alt som er spesifikt for én simulator ligger i `config/<sim>.yaml`.

| Node | Oppgave |
|---|---|
| `thruster_adapter` | Sender `/control/thruster/...` videre til simulatorens motorer. Begrenser verdiene og setter thrust til 0 når kommandoene stopper (0,5 s). |
| `sensor_relay` | Sender simulatorens sensor-topics videre til `/autonomy/...`. |
| `heading_node` | Regner ut heading fra IMU-en. |
| `fake_heading` | Midlertidig erstatning for autonomy: sender ønsket heading og fart. |
| `stub_controller` | Midlertidig erstatning for control: P-regulator fra heading-feil til thrust. |

### Faste topics
| Topic | Type | Enhet |
|---|---|---|
| `/control/thruster/{left,right}/thrust` | `std_msgs/Float64` | newton |
| `/control/thruster/{left,right}/angle` | `std_msgs/Float64` | radianer |
| `/autonomy/heading` | `std_msgs/Float64` | radianer, ENU (0 = øst, positiv mot klokka) |
| `/autonomy/desired/heading` | `std_msgs/Float64` | radianer, ENU |
| `/autonomy/desired/speed` | `std_msgs/Float64` | m/s |
| `/autonomy/imu` | `sensor_msgs/Imu` | |
| `/autonomy/gps/fix` | `sensor_msgs/NavSatFix` | |
| `/autonomy/lidar/points` | `sensor_msgs/PointCloud2` | |
| `/autonomy/camera/front_left/image_raw` | `sensor_msgs/Image` | |

### Bygg og kjør
Start containeren som over, og kjør simulatoren i den. Åpne så et nytt skall i samme container med `docker exec -it <navn> bash`:
```bash
source /opt/ros/humble/setup.bash
cd /root/vrx_ws
colcon build --merge-install --packages-select sim_interface
source install/setup.bash

# bare grensesnittet
ros2 launch sim_interface sim_interface.launch.py sim:=vrx
# hele kjeden med midlertidig autonomy og control
ros2 launch sim_interface demo.launch.py sim:=vrx heading:=2.0 speed:=1.0
```
Pakken må bygges på nytt hver gang containeren startes med `--rm`, og etter endringer i koden.

### Bytte simulator
`sim:=unity` laster `config/unity.yaml` i stedet for `config/vrx.yaml`. Unity-filen er en mal med plassholdere og er ikke testet. En ny simulator trenger bare en ny yaml-fil, så lenge den publiserer `/clock` og standard ROS-meldinger i ROS-konvensjon (ENU, x frem, z opp).

## Status
- Docker-imaget `vrx-sim:humble-garden` er bygget og testet. Simulatoren starter både med Gazebo-vindu og headless, og sensorene og motorene virker.
- `sim_interface` er testet mot VRX med WAM-V. Vår egen båtmodell er ikke laget ennå.
- Unity-backenden er ikke testet.
- PX4-koblingen via uXRCE-DDS er ikke startet, fordi vi venter på svar fra control.
