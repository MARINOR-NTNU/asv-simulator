# asv-simulator

Felles VRX-simulator for gruppen, kjørt lokalt i Docker: Ubuntu 22.04, ROS 2 Humble, Gazebo Garden og VRX (`humble`-grenen). Hver person kjører sin egen simulator, og vi deler Dockerfile og kode via git.

## Bygg
```bash
docker build -t vrx-sim:humble-garden .
```
Bygget tar ca. 15–20 min, pluss ca. 2 min for Micro XRCE-DDS Agent og `px4_msgs`. `ros_gz_bridge` kan stå i over 10 min uten ny output, og det er normalt.

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
| `px4_motor_bridge` | Erstatter `motor_writer` i PX4: `MotorOutput` fra PX4 → `/control/thruster/...`. Se «Kjøre control sin PX4 mot simulatoren». |
| `px4_seapath_bridge` | Erstatter `seapath`-driveren i PX4: IMU og GPS → `SeapathData` til PX4. |

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

### Starte alt med én kommando
`sim.launch.py` starter simulatoren og grensesnittet, og velger hva som står for autonomy og control:
```bash
colcon build --merge-install --packages-select asv_gazebo asv_fastsim sim_interface
source install/setup.bash

ros2 launch sim_interface sim.launch.py                                   # vår båt, bare grensesnittet (f.eks. for autonomy)
ros2 launch sim_interface sim.launch.py sim:=vrx                          # WAM-V, med lidar og kamera
ros2 launch sim_interface sim.launch.py control:=stub autonomy:=fake heading:=2.5 speed:=0.5
ros2 launch sim_interface sim.launch.py control:=stub autonomy:=path path:=path_slalom
ros2 launch sim_interface sim.launch.py control:=px4                      # control sin PX4, se under
ros2 launch sim_interface sim.launch.py sim:=fast real_time_factor:=20 control:=stub autonomy:=fake   # rask 2D, se under
```
| Valg | Verdier |
|---|---|
| `sim` | `vrx_asv` (vår båt, standard), `vrx` (WAM-V) eller `fast` (vår båt i den raske 2D-simulatoren) |
| `real_time_factor` | bare `sim:=fast`: 1 = sanntid (standard), 20 = tjue ganger raskere, 0 = så fort det går |
| `control` | `none` (standard), `stub` (`stub_controller`) eller `px4` (broene og agenten) |
| `autonomy` | `none` (standard), `fake` (`fake_heading`, med `heading`, `speed` og `sweep_rate`) eller `path` (`waypoint_follower`, med `path`) |
| `headless` | `true` = uten Gazebo-vindu |

`control` er ett valg, så `stub_controller` og PX4 kan ikke styre motorene samtidig. Ikke start `demo.launch.py` eller `path.launch.py` ved siden av `control:=px4`, for de starter også `stub_controller`, og da kjemper to om motorene uten noen feilmelding.

### Rask 2D-simulator for mange tester
`src/asv_fastsim` er en 2D-modell av vår båt (fram, sidelengs og dreiing) uten grafikk. Den leser masse, motstand, thrustere og grenser fra `asv_gazebo/models/asv/model.sdf`, så den bruker de samme tallene som Gazebo. Den publiserer de samme `/autonomy/...`-topicene og leser de samme `/control/...`, så nodene til autonomy og control merker ikke forskjell.

- Målt mot Gazebo 2026-10-19 med samme testsekvens: fart, akselerasjon, oppbremsing, dreiehastighet, svingradius og thrustervinkel er innen 1 % (oppbremsing etter 15 s innen 3 %).
- Med hele ROS-kjeden (`control:=stub autonomy:=fake`) oppfører den seg likt som i sanntid opp til `real_time_factor:=20`. Ved full fart (ca. 46 ganger sanntid) henger ROS-nodene etter, og regulatoren blir ustabil. Modellen alene, uten ROS, går ca. 700 ganger raskere enn sanntid.
- Ikke med: bølger, rull, stamp og hiv, kamera og lidar. Til det brukes Gazebo.
- Noden er klokka (`/clock`) selv, så den kjører ikke med `use_sim_time`.

### Vår egen båt i VRX
Pakken `src/asv_gazebo` inneholder en Gazebo-modell av vår egen båt (`models/asv`), bygget rundt skroget `skrog10-1.stl`. Start den i stedet for WAM-V slik:
```bash
colcon build --merge-install --packages-select asv_gazebo asv_fastsim sim_interface
source install/setup.bash
ros2 launch asv_gazebo asv.launch.py                 # headless:=true for å kjøre uten vindu
ros2 launch sim_interface demo.launch.py sim:=vrx_asv heading:=1.0 speed:=1.0
```
Båten har to thrustere akter (`left`, `right`) som kan dreies, og en fast baugthruster (`bow`) som skyver sidelengs, så `/control/thruster/bow/thrust` finnes i tillegg. Foreløpig har den bare IMU og GPS. Leddvinklene, blant annet hvor thrusterne peker, publiseres på `/asv/joint_states`.

Skrogfilen `skrog10-1.stl` er delt i skrog, thrusterhus og propeller (`models/asv/meshes/`), så thrusterne dreier og propellene snurrer synlig. Meshene brukes bare til visning. Fysikken står som tall i `models/asv/model.sdf`:

| Størrelse | Verdi | Kilde |
|---|---|---|
| Lengde, bredde | 1,50 m, 0,53 m | målt fra STL-filen |
| Masse | 45 kg | totalvekt med last er 40–50 kg |
| Dypgang | 10,5 cm | følger av massen og skrogformen |
| Maks thrust | 50 N per thruster akter, 25 N i baugen | anslag |
| Dreiing av thrustere | ±90°, 2 rad/s | anslag |
| Motstand i vannet | se kommentaren i `model.sdf` | regnet ut fra skrogformen, ikke målt |

Målt i simulatoren med disse tallene: 0,77 m/s ved 10 N, 1,39 m/s ved 30 N og 2,63 m/s ved full kraft (100 N). Baugthrusteren alene dreier båten ca. 70 grader per sekund. Båten ligger høyt i vannet og har lite retningsstabilitet, så den er avhengig av at regulatoren styrer aktivt.

### Følge en bane
`waypoint_follower` erstatter `fake_heading` og styrer båten gjennom en liste med punkter:
```bash
ros2 launch sim_interface path.launch.py sim:=vrx_asv path:=path_demo
```
Punktene står i `config/<path>.yaml` som x, y i meter (øst, nord) fra der båten er når noden starter. `radius` er hvor nær båten må komme et punkt, og `loop: true` kjører banen om igjen. Noden publiserer også båtens posisjon i meter på `/autonomy/position`. Banen tar ikke hensyn til land eller hindringer.

### Slalåmløype
`asv_gazebo/launch/slalom.launch.py` fjerner bøyerekka som følger med verdenen og legger ut fire bøyer på linje nordover fra startstedet, 7 m fra hverandre. `config/path_slalom.yaml` er en bane som kjører sikksakk mellom dem (3 m på hver side), og så tilbake sørover øst for løypa. Start den mens simulatoren kjører:
```bash
ros2 launch asv_gazebo slalom.launch.py
ros2 launch sim_interface path.launch.py sim:=vrx_asv path:=path_slalom
```
Banen har et fast nullpunkt (`origin`, breddegrad og lengdegrad for startstedet), så den treffer løypa selv om båten har drevet før start. Uten `origin` regnes punktene fra der båten er når noden starter.

### Bytte simulator
`sim:=` velger hvilken fil i `config/` som lastes: `vrx` (WAM-V), `vrx_asv` (vår båt) eller `unity`. Unity-filen er en mal med plassholdere og er ikke testet. En ny simulator trenger bare en ny yaml-fil, så lenge den publiserer `/clock` og standard ROS-meldinger i ROS-konvensjon (ENU, x frem, z opp).

Sim-topics i VRX (bekreftet i containeren). Nodene bruker dem bare gjennom `config/<sim>.yaml`:
- WAM-V: `/wamv/pose` (ingen ferdig odometri), `/wamv/sensors/gps/gps/fix`, `/wamv/sensors/imu/imu/data`, `/wamv/sensors/lidars/lidar_wamv_sensor/{points,scan}`, `/wamv/sensors/cameras/{front_left,front_right,middle_right}_camera_sensor/image_raw` og motorene `/wamv/thrusters/{left,right}/{thrust,pos}`.
- Vår båt: `/asv/sensors/imu`, `/asv/sensors/gps`, motorene `/asv/thrusters/{left,right,bow}/thrust` og `/asv/thrusters/{left,right}/pos`, og leddvinklene på `/asv/joint_states`.
- Begge: `/clock`.

## Kjøre control sin PX4 mot simulatoren
Simulatoren later som den er Seapath og motorene, så regulatorene i PX4 kjører uendret:
```
VRX-sensorer → px4_seapath_bridge → SeapathData → PX4 (control) → MotorOutput → px4_motor_bridge → VRX-motorer
```
PX4 og simulatoren kjører i hver sin container, begge startet fra dette repoet. Koden til control ligger som git-submodule i `px4/Flightcontroller-px4` og bygges i PX4-containeren. Vi endrer den ikke. Micro XRCE-DDS Agent kjører i simulator-containeren, så bare XRCE (UDP port 8888) går mellom dem. PX4-containeren trenger ikke ROS 2.

**1. Hent koden til control** (én gang, og når submodulen er oppdatert):
```bash
git submodule update --init px4/Flightcontroller-px4
```
Ikke bruk `--recursive`. PX4 henter selv de av sine egne submoduler bygget trenger. Submodulen peker på én commit på grenen `feature/control/proteus_board`. Nyeste commit på grenen hentes med `git submodule update --remote px4/Flightcontroller-px4`.

**2. Bygg imagene** (VRX-imaget som under «Bygg», PX4-imaget tar noen minutter):
```bash
docker build -t vrx-sim:humble-garden .
docker build -f Dockerfile.px4 -t px4-sitl:proteus .
```
PX4-imaget har bare verktøykjeden (samme pakker som PX4 sitt `Tools/setup/ubuntu.sh --no-nuttx --no-sim-tools`). Python-pakkene leses fra `requirements.txt` i submodulen.

**3. Start begge**, fra roten av repoet:
```bash
xhost +local:docker                          # bare for Gazebo-vindu
docker compose up                            # vår båt i Gazebo, broene, agenten og PX4
SIM=fast HEADLESS=true docker compose up     # 2D-simulatoren i stedet, uten vindu
```
`vrx` bygger pakkene våre og kjører `sim.launch.py control:=px4`. `px4` bygger PX4 (første gang 30–60 min med ett løp om gangen, siden bare det som er endret) og starter den. Filene i `px4/Flightcontroller-px4/build/` eies av brukeren din, ikke root.

| Variabel | Standard | Betyr |
|---|---|---|
| `SIM` | `vrx_asv` | `vrx_asv`, `vrx` eller `fast`, som i `sim.launch.py` |
| `HEADLESS` | `false` | `true` = uten Gazebo-vindu |
| `FORWARD_THRUSTER` | `bow` | motoren `forward_propeller_thrust` sendes til |
| `PX4_TARGET` | `px4_sitl_default` | byggemålet i PX4 |
| `PX4_AIRFRAME` | `10040` | `sihsim_quadx`. `10016` (`none_iris`) henger ved oppstart, se [docs/px4.md](docs/px4.md) |

PX4-konsollen (`pxh>`) nås med `docker attach repo-klon-px4-1`. Ctrl-P Ctrl-Q går ut uten å stoppe PX4. Stopp alt med `docker compose down`.

Når Gazebo-vinduet åpnes, kan Ubuntu si at programmet ikke svarer mens verdenen lastes. Trykk «Vent», ikke «Tving avslutning», for det avslutter hele simulatoren.

Krav på PX4-siden (hos control) før data går begge veier:
- `src/modules/uxrce_dds_client/dds_topics.yaml` må ha `/fmu/out/motor_output` under `publications` og `/fmu/in/seapath_data` under `subscriptions`, og meldingene må finnes i `msg/`.
- `switch_motor_output` må være med og startes i SITL-bygget, så noe publiserer `MotorOutput`.
- `ROS_DOMAIN_ID` i simulator-containeren må være lik `UXRCE_DDS_DOM_ID` i PX4 (begge er 0 som standard).

PX4 på kortet i stedet for SITL: start agenten for hånd med `MicroXRCEAgent serial --dev /dev/ttyACM0 -b 921600` sammen med `ros2 launch sim_interface px4_bridge.launch.py`, og start simulator-containeren med `--device /dev/ttyACM0` (port og baudrate er ikke sjekket).

**4. Sjekk at det virker**, i et nytt skall på verten:
```bash
docker compose exec vrx bash -c 'source /root/vrx_ws/install/setup.bash && ros2 run sim_interface px4_check'
```
Den sjekker hvert ledd i rekkefølge (simulatoren, broene, agenten, om PX4 er koblet til, om MotorOutput og SeapathData går, og om tallene ser ekte ut), og sier hva som mest sannsynlig er galt ved første feil. For å se dataene selv:
```bash
ros2 topic echo /fmu/out/motor_output    # kommer det noe, sender PX4 til simulatoren
ros2 topic echo /fmu/in/seapath_data     # det simulatoren sender til PX4 (50 Hz)
```
Uten PX4 kan broene testes ved å late som man er PX4:
```bash
ros2 topic pub -r 20 /fmu/out/motor_output px4_msgs/msg/MotorOutput "{port_side_thrust: 60.0, starboard_thrust: 60.0}"   # 60 % = 30 N
```

**Slik tolkes MotorOutput i dag** (innstillingene ligger i `config/px4_bridge.yaml`):
- `port_side_*` → `left`, `starboard_*` → `right`, `forward_propeller_thrust` → `bow` (med `forward_thruster:=bow`).
- Thrust er -100..100 % (avtalt med control). Broen gjør det om til newton med maks thrust 50 N akter og 25 N baug (anslag). Bakover gir akterthrusterne 60 %, så -100 % blir -30 N. Med WAM-V settes `stern_thrust_scale: 23.5` og `stern_reverse_ratio: 1.0`.
- Vinklene er radianer og sendes rett gjennom: positiv mot babord sett bakfra, ±90°.
- Positiv vinkel dreier thrusterne mot babord, og båten svinger da mot styrbord. Er fortegnet motsatt hos control, settes `angle_scale: -1.0`.
- Positiv baugthrust skyver baugen mot babord på `/control/thruster/bow/thrust`. Hos control skyver positiv `forward_propeller_thrust` den mot styrbord, så broen snur fortegnet.

**Kjent om SeapathData fra simulatoren:** posisjon, heading, roll, pitch og vinkelhastigheter er nøyaktige. Farten er regnet ut fra GPS (litt forsinket), heave er en tilnærming, og forsinket heave finnes ikke (merket ugyldig i `status`). `timestamp` er 0, så PX4 setter sin egen tid. Med vår båt går simulatoren nesten i sanntid (0,99), mens WAM-V går på ca. 0,7.

## Dokumentasjon
- [docs/status.md](docs/status.md): status, hva som er testet, og neste steg.
- [docs/px4.md](docs/px4.md): PX4-koblingen, hva vi vet om koden til control, og hva vi venter på fra dem.
- [docs/fallgruver.md](docs/fallgruver.md): ting som er lette å gå i.
