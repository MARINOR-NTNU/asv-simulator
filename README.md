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
| `waypoint_follower` | Midlertidig erstatning for autonomy: følger en bane av punkter. |
| `stub_controller` | Midlertidig erstatning for control: P-regulator fra heading-feil til thrust. |

### Faste topics
| Topic | Type | Enhet |
|---|---|---|
| `/control/thruster/{left,right,bow}/thrust` | `std_msgs/Float64` | newton |
| `/control/thruster/{left,right}/angle` | `std_msgs/Float64` | radianer |
| `/autonomy/heading` | `std_msgs/Float64` | radianer, ENU (0 = øst, positiv mot klokka) |
| `/autonomy/desired/heading` | `std_msgs/Float64` | radianer, ENU |
| `/autonomy/desired/speed` | `std_msgs/Float64` | m/s |
| `/autonomy/imu` | `sensor_msgs/Imu` | |
| `/autonomy/gps/fix` | `sensor_msgs/NavSatFix` | |
| `/autonomy/lidar/points` | `sensor_msgs/PointCloud2` | |
| `/autonomy/camera/front_left/image_raw` | `sensor_msgs/Image` | |

Kommandoene fra control er avtalt med control-gruppen (2026-10-12):
- Én melding per tall, på topicene over. `bow` finnes bare på vår egen båt.
- Positiv thrust skyver båten forover. Positiv baugthrust skyver baugen mot babord.
- Vinkel 0 er rett frem, og positiv vinkel dreier thrusteren mot babord.
- Control må sende oftere enn hvert 0,5 sekund. Uten ny kommando innen den tiden settes thrusten for den motoren til 0.

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

### Vår egen båt i VRX
Pakken `src/asv_gazebo` inneholder en Gazebo-modell av vår egen båt (`models/asv`), bygget rundt skroget `skrog10-1.stl`. Start den i stedet for WAM-V slik:
```bash
colcon build --merge-install --packages-select asv_gazebo sim_interface
source install/setup.bash
ros2 launch asv_gazebo asv.launch.py                 # headless:=true for å kjøre uten vindu
ros2 launch sim_interface demo.launch.py sim:=vrx_asv heading:=1.0 speed:=1.0
```
Båten har to gondoler akter (`left`, `right`) og en baugthruster (`bow`), så `/control/thruster/bow/thrust` finnes i tillegg. Positiv baugthrust skyver baugen mot babord. Foreløpig har den bare IMU og GPS.

Skroget brukes bare til visning. Fysikken står som tall i `models/asv/model.sdf`, og disse er anslag som må erstattes med ekte verdier: masse (45 kg, midt i spennet 40–50 kg), tyngdepunkt, treghetsmoment, maks thrust (50 N per gondol, 25 N i baugen), motstandskoeffisienter, og at gondolene kan dreies.

### Følge en bane
`waypoint_follower` erstatter `fake_heading` og styrer båten gjennom en liste med punkter:
```bash
ros2 launch sim_interface path.launch.py sim:=vrx_asv path:=path_demo
```
Punktene står i `config/<path>.yaml` som x, y i meter (øst, nord) fra der båten er når noden starter. `radius` er hvor nær båten må komme et punkt, og `loop: true` kjører banen om igjen. Noden publiserer også båtens posisjon i meter på `/autonomy/position`. Banen tar ikke hensyn til land eller hindringer.

### Bytte simulator
`sim:=` velger hvilken fil i `config/` som lastes: `vrx` (WAM-V), `vrx_asv` (vår båt) eller `unity`. Unity-filen er en mal med plassholdere og er ikke testet. En ny simulator trenger bare en ny yaml-fil, så lenge den publiserer `/clock` og standard ROS-meldinger i ROS-konvensjon (ENU, x frem, z opp).

## Status
- Docker-imaget `vrx-sim:humble-garden` er bygget og testet. Simulatoren starter både med Gazebo-vindu og headless, og sensorene og motorene virker.
- `sim_interface` er testet mot VRX, både med WAM-V og med vår egen båt.
- Modellen av vår egen båt flyter og lar seg styre, men fysikken er anslag og er ikke tunet.
- Unity-backenden er ikke testet.
- Grensesnittet mot control (topics, enheter, fortegn og timeout) er avtalt, se «Faste topics».
- PX4-koblingen via uXRCE-DDS er ikke startet. Det er ikke avklart om PX4 skal stå mellom control og simulatoren.
