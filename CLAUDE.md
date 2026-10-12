# VRX i Docker

Mål: alle på gruppen kjører samme VRX-miljø lokalt i Docker (Ubuntu 22.04, ROS 2 Humble, Gazebo Garden, VRX `humble`-grenen). Det finnes ingen delt simulator som kjører. Vi deler Dockerfile og kode via git.

## Filer
- `Dockerfile` bygger på `osrf/ros:humble-desktop`. Den installerer `gz-garden`, kloner `vrx` og `ros_gz` (begge `-b humble`) til `/root/vrx_ws/src` og bygger med colcon.
- `entrypoint.sh` sourcer `/opt/ros/humble` og `/root/vrx_ws/install`.
- `src/` inneholder våre egne ROS 2-pakker. Den monteres inn som `/root/vrx_ws/src/mysrc`. Der ligger `sim_interface` og `asv_gazebo` (modellen av vår egen båt).

## Status
- Imaget `vrx-sim:humble-garden` er bygget, og alle 18 colcon-pakkene fullførte.
- Testet headless: alle sensorer publiserer, og båten beveger seg når den får thrust.
- Testet med Gazebo-vindu via X11: containeren starter med vinduet oppe.
- Ufarlige advarsler i loggen: `Unable to deserialize sdf::Model` og `GzCard: Cannot anchor item to self`.
- `sim_interface` er testet headless mot VRX med WAM-V (2026-10-12): montering og bygg av `src/` virker, regulatoren holder ønsket heading, timeout setter thrust til 0, og thrust begrenses til 2353 N.
- Unity-backenden (`config/unity.yaml`) er en mal med plassholdere og er ikke testet. 
- Vår egen båt (`asv_gazebo`, skrog `skrog10-1.stl`) er testet i VRX 2026-10-12: den flyter stabilt og holder ønsket heading via `sim_interface` med `sim:=vrx_asv`. Fysikken er anslag (masse 45 kg, midt i spennet 40–50 kg, 50 N per gondol, 25 N baugthruster, motstandskoeffisienter) og er ikke tunet.
- PX4-koblingen via uXRCE-DDS er ikke startet, fordi vi venter på svar fra control.

## Byggeregler
- Bygg med ett løp om gangen: `MAKEFLAGS="-j1" colcon build --merge-install --executor sequential --parallel-workers 1`. Parallell kompilering kan bruke opp minnet og fryse maskinen.
- Bruk alltid `--merge-install`.
- `ros_gz_bridge` er tung og kan stå i over 10 min uten output. Det er normalt, så ikke avbryt.
- `ros_gz` må bygges fra kilde mot Garden (`GZ_VERSION=garden`). apt-pakken `ros-humble-ros-gz` er for Fortress og gir feil, så den skal ikke installeres.

## Bygg og kjør
```bash
nohup docker build -t vrx-sim:humble-garden . > build.log 2>&1 &

xhost +local:docker
docker run -it --rm --net=host \
  -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix \
  --device /dev/dri \
  -v $(pwd)/src:/root/vrx_ws/src/mysrc \
  vrx-sim:humble-garden
# i containeren:
ros2 launch vrx_gz competition.launch.py world:=sydney_regatta   # headless:=true for å kjøre uten vindu
```
- Sjekk at ingen gamle simulatorer kjører før du starter: `docker ps` og `pgrep -af "gz sim"`.
- Bygg egne pakker i containeren: `colcon build --merge-install --packages-select sim_interface`. Bygget ligger i containeren og forsvinner med `--rm`.
- Hvis `ros2 topic echo` feiler med `!rclpy.ok()`, har ros2-daemonen hengt seg. Bruk `--no-daemon`.

## Neste steg
Gruppen har valgt å fortsette i VRX (2026-10-12). `config/unity.yaml` blir liggende som en utestet mal.

1. Erstatt anslagene i `src/asv_gazebo/models/asv/model.sdf` med ekte tall for båten. Massen er viktigst.
2. Rett motstanden i vannet: båten svinger for lett og vrir seg når den går sideveis.
3. Reguler farten (i dag er den en fast thrust), og la `waypoint_follower` følge linjen mellom punktene.
4. Legg lidar og kamera på vår egen båt.
5. Avklar med control om PX4 lager thruster-kommandoene, og koble til via uXRCE-DDS.
6. Bytt ut `waypoint_follower` og `stub_controller` med ekte autonomy og control.

## Arkitektur
autonomy (ønsket kurs og fart) → control (thrust og vinkel) → `sim_interface` → båten i sim.

Autonomy og control bruker bare de faste topicene `/control/...` og `/autonomy/...` (se README). Alt som er spesifikt for én simulator ligger i `src/sim_interface/config/<sim>.yaml`, og velges med `sim:=vrx` (WAM-V), `sim:=vrx_asv` (vår båt) eller `sim:=unity`. Ikke bruk `/wamv/...`-topics direkte i nodene.

Noder i `sim_interface`:
- `thruster_adapter`: `/control/thruster/{left,right}/{thrust,angle}` (Float64, N / rad) → simulatorens motorer, med begrensning (clamp) og timeout.
- `sensor_relay`: sim-topics → `/autonomy/...`.
- `heading_node`: `/autonomy/imu` → `/autonomy/heading` (yaw i radianer, ENU).
- `fake_heading`, `waypoint_follower` og `stub_controller`: midlertidige erstatninger for autonomy og control. `waypoint_follower` følger en bane av punkter (`config/path_demo.yaml`, startes med `path.launch.py`).

Alle noder kjører med `use_sim_time:=true`.

Sim-topics (bekreftet i containeren):
- `/wamv/pose` (ingen ferdig odometri) og `/clock`
- `/wamv/sensors/gps/gps/fix` og `/wamv/sensors/imu/imu/data`
- `/wamv/sensors/lidars/lidar_wamv_sensor/{points,scan}`
- `/wamv/sensors/cameras/{front_left,front_right,middle_right}_camera_sensor/image_raw`
- Motorene: `/wamv/thrusters/{left,right}/{thrust,pos}` (std_msgs/Float64)
