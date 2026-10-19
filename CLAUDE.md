# VRX i Docker

Mål: alle på gruppen kjører samme VRX-miljø lokalt i Docker (Ubuntu 22.04, ROS 2 Humble, Gazebo Garden, VRX `humble`-grenen). Det finnes ingen delt simulator som kjører. Vi deler Dockerfile og kode via git.

## Filer
- `Dockerfile` bygger på `osrf/ros:humble-desktop`. Den installerer `gz-garden`, kloner `vrx` og `ros_gz` (begge `-b humble`) til `/root/vrx_ws/src` og bygger med colcon. Deretter bygger den Micro XRCE-DDS Agent og `px4_msgs`.
- `entrypoint.sh` sourcer `/opt/ros/humble` og `/root/vrx_ws/install`.
- `src/` inneholder våre egne ROS 2-pakker. Den monteres inn som `/root/vrx_ws/src/mysrc`. Der ligger `sim_interface` og `asv_gazebo` (modellen av vår egen båt).
- `px4_msgs/` er ROS 2-versjonen av uORB-meldingene i control sin PX4-fork. Meldingene kopieres inn med `scripts/sync_px4_msgs.sh`, og `px4_msgs/SOURCE.txt` viser hvilke commits de kom fra. Pakken bygges inn i imaget og ligger derfor ikke i `src/`, for da ville colcon funnet to pakker med samme navn.

## Status
- Imaget `vrx-sim:humble-garden` er bygget, og alle 18 colcon-pakkene fullførte.
- Testet headless: alle sensorer publiserer, og båten beveger seg når den får thrust.
- Testet med Gazebo-vindu via X11: containeren starter med vinduet oppe.
- Ufarlige advarsler i loggen: `Unable to deserialize sdf::Model` og `GzCard: Cannot anchor item to self`.
- `sim_interface` er testet headless mot VRX med WAM-V (2026-10-12): montering og bygg av `src/` virker, regulatoren holder ønsket heading, timeout setter thrust til 0, og thrust begrenses til 2353 N.
- Unity-backenden (`config/unity.yaml`) er en mal med plassholdere og er ikke testet. 
- Vår egen båt (`asv_gazebo`) er testet i VRX 2026-10-12: den flyter på riktig høyde, holder kursen rett frem ved alle hastigheter, er symmetrisk mot babord og styrbord, og følger en bane via `sim_interface` med `sim:=vrx_asv`. Masse 45 kg (totalvekt med last er bekreftet til 40–50 kg). Motstanden er regnet ut fra skrogformen. Thrusterne (50 N akter, 25 N baug, dreiing ±90°) er anslag.
- Bekreftet av brukeren 2026-10-19: lengde ca. 150 cm, bredde ca. 53 cm (L/B ≈ 2,8), vekt ca. 45 kg, lavt tyngdepunkt, baugthruster i tunnel for sideveis manøvrering i lav fart, og to akterthrustere som kan dreies. Modellen stemmer allerede med dette. Hvor langt og hvor fort akterthrusterne dreies, er ikke kjent. Stabilitets- og hydrodynamikkanalyse (Fusion 360) pågår, og tallene derfra skal inn i modellen.
- Grensesnittet mot control er avtalt med control-gruppen (2026-10-12): én `std_msgs/Float64` per tall på `/control/thruster/{left,right,bow}/thrust` (newton) og `/control/thruster/{left,right}/angle` (radianer), fortegn som i README, og timeout på 0,5 s per motor. Ikke endre dette uten å avtale det med control.
- Control sin kode kjører inne i PX4 (uORB). Kommandoene må derfor ut gjennom uXRCE-DDS og oversettes til `/control/thruster/...`, og navigasjonsdata må inn samme vei. Status 2026-10-19:
  - Forken er `MARINOR-NTNU/Flightcontroller-px4`, klonet til `~/Flightcontroller-px4`. `git describe` gir `v1.18.0-beta1-828`, altså PX4 sin utviklingsgren. Vi endrer ikke koden deres.
  - Control bruker egne uORB-meldinger og ikke PX4 sine vanlige actuator-topics. `MotorOutput` (til motorene) ligger bare på grenen `feature/control/motor_output_and_switch`, og `SeapathData` (navigasjon, NED/FRD) bare på `feature/control/seapathDriver`. Ingen gren har begge, og `dev-boat` har ingen av dem.
  - Ingen gren har `motor_output` eller `seapath_data` i `src/modules/uxrce_dds_client/dds_topics.yaml`. Til control har lagt dem inn, kommer ingen av meldingene gjennom uXRCE-DDS.
  - PX4 bruker v2-klienten (`UXRCE_DDS_CLIENT_USE_DDS_V3` er ikke satt), og dokumentasjonen deres sier Agent v2.4.2 for Humble.
  - `px4_motor_bridge` og `px4_seapath_bridge` er testet 2026-10-19 med `ros2 topic pub` på `/fmu/out/motor_output`, både med WAM-V og med vår båt (`sim:=vrx_asv`, `forward_thruster:=bow`). Hvert felt når riktig motor, timeouten setter thrust til 0, og i SeapathData stemmer heading med `heading_node` og fartsretningen med baugen (innen 0,3°). Heave svinger rundt 0 (±0,10 m i bølgene), og SeapathData kommer med 50 Hz sim-tid. Ikke testet mot ekte PX4.
  - Målt med kontraktens fortegn: positiv vinkel på akterthrusterne snur båten med klokka (mot styrbord), og positiv baugthrust snur den mot klokka (baugen mot babord).
  - Real-time factor (headless, med `--device /dev/dri`): 0,71 med WAM-V (kameraer og lidar) og 0,99 med vår båt. Uten `/dev/dri` falt WAM-V til 0,06, fordi Gazebo da tegner med CPU-en.
  - Agenten og `px4_msgs` er bygget inn i imaget og testet 2026-10-19: `MicroXRCEAgent udp4 -p 8888` starter, og `ros2 interface show` viser begge meldingene.
  - Bestemt 2026-10-19: VRX og control kjører i hver sin container, og agenten kjører i vår container. Bare XRCE (UDP port 8888) går mellom containerne, og all DDS-trafikk blir i vår container. Ikke flytt agenten til control sin container: DDS mellom to containere på samme PC prøver shared memory i Fast-DDS, og da kommer det ikke data uten `--ipc=host` på begge.
- Venter på svar fra control:
  - At de legger `motor_output` (publications) og `seapath_data` (subscriptions) inn i `dds_topics.yaml`.
  - Hvilken gren `px4_msgs` skal lages fra når de to grenene er slått sammen.
  - Enhetene i MotorOutput. I dag sender RC-veien rå RC-verdier (ca. 1000–2000 µs), og regulatorveien sender faste plassholdere (±1). Også grader eller radianer, og fortegn på vinklene.
  - Om `forward_propeller_thrust` skyver forover eller sidelengs.
  - Hvordan de starter PX4 SITL i sin container (make-target eller kommando), om den kjører på samme PC med `--net=host`, eller om PX4 skal kjøre på kortet. Motor-committen deres endrer `boards/px4/fmu-v6c`, så kortet er trolig en Pixhawk 6C (ikke bekreftet).
  - Om `seapath`-driveren og `motor_writer` slås av når PX4 kjører mot simulatoren.
  - Hvilke felt i SeapathData regulatorene skal bruke. Ingen kode leser den ennå.
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
- Koblingen mot PX4 startes i tillegg til `sim_interface.launch.py`: `ros2 launch sim_interface px4_bridge.launch.py`. Innstillingene ligger i `config/px4_bridge.yaml`.
- Agenten startes med `MicroXRCEAgent udp4 -p 8888` mot PX4 SITL. Mot et kort på USB brukes `MicroXRCEAgent serial --dev /dev/ttyACM0 -b 921600`, og containeren må startes med `--device /dev/ttyACM0` (port og baudrate er ikke sjekket). `ROS_DOMAIN_ID` må være lik `UXRCE_DDS_DOM_ID` i PX4 (begge er 0 som standard).
- Når control har oppdatert grenene sine: `git -C ~/Flightcontroller-px4 fetch`, deretter `scripts/sync_px4_msgs.sh` og bygg imaget på nytt. Grenene som brukes, står øverst i skriptet.

## Neste steg
Gruppen har valgt å fortsette i VRX (2026-10-12). `config/unity.yaml` blir liggende som en utestet mal.

1. Publiser bøyeposisjoner fra simulatoren (breddegrad og lengdegrad), når autonomy har sagt hvilket topic og hvilken meldingstype noden deres leser.
2. Sett inn ekte tall for thrusterne når motorene er valgt.
3. Regulering er control sin oppgave, ikke simulatoren sin. `stub_controller` (med fartsregulering fra `speed_node`) og `waypoint_follower` er bare testverktøy til control og autonomy er koblet på, så de skal ikke videreutvikles mer enn testene trenger.
4. Legg lidar og kamera på vår egen båt.
5. Bygg imaget med agenten og `px4_msgs`, og test `px4_motor_bridge` og `px4_seapath_bridge` med `ros2 topic pub` og VRX. Test mot ekte PX4 når control har svart (se «Venter på svar fra control»).

## Ting som er lette å gå i
- Motstanden i vannet angriper i `hydro_link`. Flyttes det punktet foran tyngdepunktet, blir båten retningsustabil og spinner rundt i høy fart.
- `linear_drag` og `angular_drag` i oppdriftsmodulen er lik i alle retninger og skal stå på 0. All motstand ligger i `SimpleHydrodynamics`.
- Et ledd som kjøres helt i endestopp, låser seg. Derfor er leddgrensen for thrusterne (±1,75) videre enn det `thruster_adapter` tillater (±1,5708).
- Ved omregning fra GPS til meter må cos(breddegrad) regnes med en fast referansebredde. Ellers gir bevegelse nord/sør flere meter falsk forflytning øst/vest.
- En modell som er fjernet fra en kjørende simulator, lar seg ikke sette inn igjen med samme navn. Start simulatoren på nytt.
- Standardbygget av Micro XRCE-DDS Agent v2.4.2 feiler, fordi det laster ned Fast-DDS-grenen `2.12.x`, som ikke finnes lenger. Derfor bygges den med `-DUAGENT_USE_SYSTEM_FASTDDS=ON -DUAGENT_USE_SYSTEM_FASTCDR=ON` mot Fast-DDS fra Humble.
- Meldinger til PX4 sendes med `timestamp = 0`. Da setter PX4 sin egen tid når meldingen kommer fram. Andre verdier regnes om med agentens klokke (ekte tid), og sim-tid ville blitt feil.
- PX4 publiserer best effort, så abonnementer på `/fmu/out/...` må bruke `qos_profile_sensor_data`.

## Arkitektur
autonomy (ønsket kurs og fart) → control (thrust og vinkel) → `sim_interface` → båten i sim.

Autonomy og control bruker bare de faste topicene `/control/...` og `/autonomy/...` (se README). Alt som er spesifikt for én simulator ligger i `src/sim_interface/config/<sim>.yaml`, og velges med `sim:=vrx` (WAM-V), `sim:=vrx_asv` (vår båt) eller `sim:=unity`. Ikke bruk `/wamv/...`-topics direkte i nodene.

Noder i `sim_interface`:
- `thruster_adapter`: `/control/thruster/{left,right}/{thrust,angle}` (Float64, N / rad) → simulatorens motorer, med begrensning (clamp) og timeout.
- `sensor_relay`: sim-topics → `/autonomy/...`.
- `heading_node`: `/autonomy/imu` → `/autonomy/heading` (yaw i radianer, ENU).
- `px4_motor_bridge`: `/fmu/out/motor_output` (MotorOutput) → `/control/thruster/{left,right}/{thrust,angle}`. Babord = left, styrbord = right. Erstatter `motor_writer` i PX4. Enhetene er ikke avklart, så verdien som sendes er `(verdi - offset) * scale` (standard: rett gjennom). `forward_propeller_thrust` ignoreres til `forward_thruster` settes.
- `px4_seapath_bridge`: `/autonomy/imu` og `/autonomy/gps/fix` → `/fmu/in/seapath_data` (SeapathData, NED/FRD). Erstatter `seapath`-driveren i PX4. Fart er GPS-posisjon derivert og glattet, heave er høyden under en glattet middelhøyde (`heave_tau`, 20 s), og forsinket heave er merket ugyldig. Dette er tilnærminger.
- `fake_heading`, `waypoint_follower` og `stub_controller`: midlertidige erstatninger for autonomy og control. `waypoint_follower` følger en bane av punkter (`config/path_demo.yaml`, startes med `path.launch.py`).

Alle noder kjører med `use_sim_time:=true`.

Sim-topics (bekreftet i containeren):
- `/wamv/pose` (ingen ferdig odometri) og `/clock`
- `/wamv/sensors/gps/gps/fix` og `/wamv/sensors/imu/imu/data`
- `/wamv/sensors/lidars/lidar_wamv_sensor/{points,scan}`
- `/wamv/sensors/cameras/{front_left,front_right,middle_right}_camera_sensor/image_raw`
- Motorene: `/wamv/thrusters/{left,right}/{thrust,pos}` (std_msgs/Float64)
