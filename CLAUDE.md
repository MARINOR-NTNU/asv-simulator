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
- Vår egen båt (`asv_gazebo`) er testet i VRX 2026-10-12: den flyter på riktig høyde, holder kursen rett frem ved alle hastigheter, er symmetrisk mot babord og styrbord, og følger en bane via `sim_interface` med `sim:=vrx_asv`. Masse 45 kg (totalvekt med last er bekreftet til 40–50 kg). Motstanden er regnet ut fra skrogformen. Thrusterne (50 N akter, 25 N baug, dreiing ±90°) er anslag.
- Grensesnittet mot control er avtalt med control-gruppen (2026-10-12): én `std_msgs/Float64` per tall på `/control/thruster/{left,right,bow}/thrust` (newton) og `/control/thruster/{left,right}/angle` (radianer), fortegn som i README, og timeout på 0,5 s per motor. Ikke endre dette uten å avtale det med control.
- Control sin kode kjører inne i PX4 (uORB). Kommandoene må derfor ut gjennom uXRCE-DDS og oversettes til `/control/thruster/...`, og heading ref og heading true må inn samme vei. Ikke startet. Ukjent: PX4-versjon, hvilke uORB-meldinger som brukes, og om PX4 kjøres som SITL eller på et kort.
- Autonomy skriver en ROS 2-node i C++ (radianer, bøyer i breddegrad og lengdegrad) som gir heading ref og heading true. Den skal erstatte `heading_node` og `waypoint_follower`. Simulatoren publiserer ikke bøyeposisjoner ennå.

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

1. Publiser bøyeposisjoner fra simulatoren (breddegrad og lengdegrad), når autonomy har sagt hvilket topic og hvilken meldingstype noden deres leser.
2. Sett inn ekte tall for thrusterne når motorene er valgt.
3. Reguler farten (i dag er den en fast thrust), og la `waypoint_follower` følge linjen mellom punktene.
4. Legg lidar og kamera på vår egen båt.
5. Koble til PX4 via uXRCE-DDS når control har svart på versjon og meldinger.

## Ting som er lette å gå i
- Motstanden i vannet angriper i `hydro_link`. Flyttes det punktet foran tyngdepunktet, blir båten retningsustabil og spinner rundt i høy fart.
- `linear_drag` og `angular_drag` i oppdriftsmodulen er lik i alle retninger og skal stå på 0. All motstand ligger i `SimpleHydrodynamics`.
- Et ledd som kjøres helt i endestopp, låser seg. Derfor er leddgrensen for thrusterne (±1,75) videre enn det `thruster_adapter` tillater (±1,5708).
- Ved omregning fra GPS til meter må cos(breddegrad) regnes med en fast referansebredde. Ellers gir bevegelse nord/sør flere meter falsk forflytning øst/vest.
- En modell som er fjernet fra en kjørende simulator, lar seg ikke sette inn igjen med samme navn. Start simulatoren på nytt.

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
