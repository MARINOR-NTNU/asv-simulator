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
| `px4_hil_bridge` | Er simulatoren PX4 venter på i SITL: IMU og GPS → `HIL_SENSOR` og `HIL_GPS` over MAVLink (TCP 4560), med simuleringstiden som klokke. Kan også late som den er en RC-sender (`rc_channels`). |

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
colcon build --merge-install --packages-select asv_hydrodynamics asv_gazebo sim_interface
source install/setup.bash

ros2 launch sim_interface sim.launch.py                                   # vår båt, bare grensesnittet (f.eks. for autonomy)
ros2 launch sim_interface sim.launch.py sim:=vrx                          # WAM-V, med lidar og kamera
ros2 launch sim_interface sim.launch.py control:=stub autonomy:=fake heading:=2.5 speed:=0.5
ros2 launch sim_interface sim.launch.py control:=stub autonomy:=path path:=path_slalom
ros2 launch sim_interface sim.launch.py control:=px4                      # control sin PX4, se under
```
| Valg | Verdier |
|---|---|
| `sim` | `vrx_asv` (vår båt, standard) eller `vrx` (WAM-V) |
| `control` | `none` (standard), `stub` (`stub_controller`) eller `px4` (broene og agenten) |
| `autonomy` | `none` (standard), `fake` (`fake_heading`, med `heading`, `speed` og `sweep_rate`) eller `path` (`waypoint_follower`, med `path`) |
| `world` | bare `sim:=vrx_asv`: `open_water` (åpent hav uten land, standard) eller `sydney_regatta` (VRX sin verden med land og bøyer) |
| `scenario` | bare `sim:=vrx_asv`: ting som settes inn i verdenen, f.eks. `slalom` (se «Scenarier») |
| `headless` | `true` = uten Gazebo-vindu |

`control` er ett valg, så `stub_controller` og PX4 kan ikke styre motorene samtidig. Ikke start `demo.launch.py` eller `path.launch.py` ved siden av `control:=px4`, for de starter også `stub_controller`, og da kjemper to om motorene uten noen feilmelding.

### Vår egen båt i VRX
Pakken `src/asv_gazebo` inneholder en Gazebo-modell av vår egen båt (`models/asv`), bygget rundt skroget `skrog10-1.stl`. Start den i stedet for WAM-V slik:
```bash
colcon build --merge-install --packages-select asv_hydrodynamics asv_gazebo sim_interface
source install/setup.bash
ros2 launch asv_gazebo asv.launch.py                 # headless:=true for å kjøre uten vindu
ros2 launch sim_interface demo.launch.py sim:=vrx_asv heading:=1.0 speed:=1.0
```
Båten har to thrustere akter (`left`, `right`) som kan dreies, og en fast baugthruster (`bow`) som skyver sidelengs, så `/control/thruster/bow/thrust` finnes i tillegg. Den har IMU og GPS, og lidar og kamera kan legges til i `components.yaml` (se under). Leddvinklene, blant annet hvor thrusterne peker, publiseres på `/asv/joint_states`.

Skrogfilen `skrog10-1.stl` er delt i skrog, thrusterhus og propeller (`models/asv/meshes/`), så thrusterne dreier og propellene snurrer synlig. Meshene brukes bare til visning. Modellen er skrevet i xacro, og `model.sdf` lages når pakken bygges:
- `models/asv/model.sdf.xacro`: setter båten sammen.
- `models/asv/xacro/parameters.xacro`: **alle tallene** (masse, tyngdepunkt, motstand, thrusterposisjoner, maks thrust, dreiegrenser, sensorfrekvenser). Her endres båten.
- `models/asv/xacro/thrusters.xacro`: én makro for dreibar thruster (brukt for venstre og høyre) og én for baugthrusteren.
- `models/asv/xacro/sensors.xacro`: IMU og GPS. Nye sensorer legges til her.
- `models/asv/components.yaml`: **komponentene om bord** (batteri, elektronikk osv.), én linje per komponent med masse, plassering og størrelse.

**Totalvekten er fast på 45 kg** (`total_mass`), med skrog, thrustere og alle komponentene. Skroget får massen som er igjen, så dypgangen er den samme uansett hva som legges inn. Komponentene flytter tyngdepunktet etter hvor de står: et batteri på 8 kg ved x = −0,6 m gir ca. 3,7° akterlig trim. Veier komponentene mer enn totalvekten, stopper bygget med en feilmelding. Komponentene vises som oransje bokser i Gazebo.

**Sensorer (lidar og kamera)** legges i samme fil under `sensors:`, med type og vinkel i tillegg. Vekten regnes inn i de 45 kg, og broene til ROS lages automatisk:
```yaml
components:
  - {name: battery, mass: 8.0, x: -0.25, y: 0.0, z: -0.15, size: [0.30, 0.15, 0.10]}
sensors:
  - {name: lidar, type: lidar, mass: 0.8, x: 0.3, y: 0.0, z: 0.35, size: [0.1, 0.1, 0.07]}
  - {name: front, type: camera, mass: 0.2, x: 0.65, y: 0.0, z: 0.25, pitch: 10, size: [0.05, 0.08, 0.04]}
```
| Type | ROS-topics | Valgfrie felt (standard) |
|---|---|---|
| `lidar` | `/autonomy/lidar/<name>/points`, `/autonomy/lidar/<name>/scan` | `rate` (10 Hz), `samples` (360), `vertical_samples` (16), `fov_horizontal` (360°), `fov_vertical` (30°), `range_min` (0,3 m), `range_max` (50 m) |
| `camera` | `/autonomy/camera/<name>/image_raw`, `/autonomy/camera/<name>/camera_info` | `rate` (15 Hz), `width` (640), `height` (480), `fov_horizontal` (80°), `near` (0,1 m), `far` (100 m) |

Vinklene `roll`, `pitch` og `yaw` er i grader. Kameraet ser forover langs x, og positiv `pitch` heller det nedover. Lista er tom som standard, fordi kamera og lidar krever mye av grafikkortet. Med eksemplet over går simulatoren fortsatt på 0,99 av sanntid uten vindu.

Bygg `asv_gazebo` på nytt etter en endring. Tallene i dag:

| Størrelse | Verdi | Kilde |
|---|---|---|
| Lengde, bredde | 1,50 m, 0,53 m | målt fra STL-filen |
| Masse | 45 kg totalt, med thrustere og komponenter | anslått totalvekt |
| Dypgang | 10,5 cm | følger av massen og skrogformen |
| Maks thrust | 50 N per thruster akter, 25 N i baugen | anslag |
| Dreiing av thrustere | ±90°, 2 rad/s | anslag |
| Motstand i vannet | se kommentaren i `xacro/parameters.xacro` | regnet ut fra skrogformen, ikke målt |

Målt i simulatoren med disse tallene: 0,77 m/s ved 10 N, 1,39 m/s ved 30 N og 2,63 m/s ved full kraft (100 N). Baugthrusteren alene dreier båten ca. 70 grader per sekund. Båten ligger høyt i vannet og har lite retningsstabilitet, så den er avhengig av at regulatoren styrer aktivt.

### Følge en bane
`waypoint_follower` erstatter `fake_heading` og styrer båten gjennom en liste med punkter:
```bash
ros2 launch sim_interface path.launch.py sim:=vrx_asv path:=path_demo
```
Punktene står i `config/<path>.yaml` som x, y i meter (øst, nord) fra der båten er når noden starter. `radius` er hvor nær båten må komme et punkt, og `loop: true` kjører banen om igjen. Noden publiserer også båtens posisjon i meter på `/autonomy/position`. Banen tar ikke hensyn til land eller hindringer.

### Åpent hav
Standardverdenen for vår båt er `open_water` (`asv_gazebo/worlds/open_water.sdf.xacro`): bare en vannflate (6 × 6 km), bølger, sol og himmel, uten land. Båten starter i origo, og GPS-origo er stedet båten startet i `sydney_regatta`, så GPS-posisjonene er de samme i begge verdenene. Bølgene velges ved oppstart med `wave_height` (største utslag i meter, standard 0,11), `wave_period` (sekunder, standard 5) og `wave_direction` (radianer). Korte bølger (2–3 s) gir tydelig stamping og rulling for en så liten båt, mens lange bølger mest løfter den opp og ned. `world:=sydney_regatta` gir VRX sin verden med land og bøyer.

### Støy, vind, strøm og motortreghet
Som standard er simulatoren «snill»: perfekte sensorer, ingen vind eller strøm, og motorer som reagerer øyeblikkelig. For å teste regulatorer under mer realistiske forhold kan hver av disse slås på:
```bash
ros2 launch sim_interface sim.launch.py control:=px4 sensor_noise:=true wind_speed:=5 wind_direction:=90 current_speed:=0.5 current_direction:=0 thrust_time_constant:=0.3
SENSOR_NOISE=true WIND_SPEED=5 WIND_DIRECTION=90 CURRENT_SPEED=0.5 THRUST_TIME_CONSTANT=0.3 docker compose up
```
| Valg | Standard | Betyr |
|---|---|---|
| `sensor_noise` | `false` | støy og fast skjevhet på gyro og akselerometer, og støy på GPS-posisjonen. Tallene står i `asv_gazebo/models/asv/xacro/parameters.xacro`. Heading fra IMU-en er fortsatt eksakt, fordi Gazebo ikke har støy på orienteringen |
| `wave_height` | `0.11` | største bølgeutslag i meter, bare i `open_water` |
| `wave_period` | `5` | bølgeperiode i sekunder (3 s gir ca. 14 m bølgelengde, 5 s ca. 39 m) |
| `wave_direction` | `0` | retningen bølgene går mot, i radianer |
| `wind_speed` | `0` | middelvind i m/s (VRX sin vindplugin), bare i `open_water` |
| `wind_direction` | `0` | retningen vinden blåser **mot**, i grader: 0 = mot øst, 90 = mot nord |
| `wind_gust` | `0` | hvor mye vinden varierer (0 = jevn) |
| `current_speed` | `0` | strøm i m/s, i alle verdenene |
| `current_direction` | `0` | retningen strømmen går **mot**, i grader: 0 = mot øst, 90 = mot nord |
| `thrust_time_constant` | `0` | sekunder til motoren har nådd ca. 63 % av en ny kraft. Kan endres mens den kjører: `ros2 param set /thruster_adapter thrust_time_constant 0.3` |

Målt 2026-10-26: med støy får farten fra GPS standardavvik 0,04 m/s (mot 0,001 uten), og `stub_controller` holder fortsatt 1,0 m/s. Med 5 m/s vind mot nord driver båten uten motorer 0,4 m/s nordover. Med tidskonstant 0,5 s er kraften 61 % av et sprang etter 0,5 s og 85 % etter 1 s. Med 0,5 m/s strøm mot nord driver båten uten motorer 0,48 m/s nordover etter 30 s. Vindkoeffisientene og støytallene er anslag.

Strømmen ligger i vannmotstanden. `src/asv_hydrodynamics` er en kopi av VRX sin `SimpleHydrodynamics` (Apache 2.0) der motstanden regnes ut fra farten gjennom vannet (båtens fart minus strømmen) i stedet for over grunnen. Uten strøm er den lik VRX sin: 2 × 20 N gir 1,622 m/s med begge.

### Teste regulatoren (`control_test`)
`control_test` kjører en standardtest og måler hvordan regulatoren svarer. Den sender ønsket kurs og fart på `/autonomy/desired/...`, som autonomy ellers gjør, så den virker med alle regulatorer som følger kontrakten (`stub_controller` nå, control sin senere). Start simulatoren **uten** `autonomy`, så ingen andre sender ønskede verdier:
```bash
ros2 launch sim_interface sim.launch.py control:=stub wind_speed:=6 current_speed:=0.3
ros2 run sim_interface control_test --ros-args -p test:=heading_step -p step:=90.0 -p label:=vind
ros2 run sim_interface control_test --ros-args -p test:=speed_step -p start_speed:=0.5 -p speed:=1.0
```
| Test | Hva den gjør |
|---|---|
| `heading_step` | holder kursen båten har i `settle` sekunder (standard 15), så sprang på `step` grader, med fart `speed` |
| `speed_step` | fart `start_speed`, så sprang til `speed`, med fast kurs |

Etter spranget regnes stigetid (10–90 %), oversving, tid til stabil (innenfor 2° eller 5 % av spranget), stasjonært avvik (snitt de siste `tail` sekundene) og motorbruk (snitt av |thrust|). Resultatene lagres som `.csv` (alle målingene), `.json` (nøkkeltallene) og `.png` (graf) i `results/` i repoet (montert som `/root/results` i compose, og ignorert av git).

Målt med `stub_controller` 2026-10-26, kurssprang 90°: i stille vann 17 % oversving, stabil etter 29,5 s og 0,05° stasjonært avvik. I vind 6 m/s og strøm 0,3 m/s stabil etter 39,3 s og 1,9° stasjonært avvik, fordi kursregulatoren i `stub_controller` ikke har integralledd. Fartssprang 0,5 → 1,0 m/s: 4 % oversving, stabil etter 2,1 s.

Uten compose, legg til `-v $(pwd)/results:/root/results` på `docker run` for å få resultatene ut av containeren.

### Scenarier: bøyer og andre ting
Et scenario er en kort yaml-fil i `asv_gazebo/scenarios/` med tingene som skal stå i verdenen. Posisjonene er meter øst og nord fra båtens startsted, så samme scenario virker i alle verdenene:
```yaml
objects:
  - {type: buoy, name: slalom1_red, color: red, x: 0.0, y: 4.0}
  - {type: buoy, name: slalom2_green, color: green, x: 0.0, y: 11.0}
```
Start det sammen med simulatoren, eller i en verden som allerede kjører:
```bash
ros2 launch sim_interface sim.launch.py scenario:=slalom control:=stub autonomy:=path path:=path_slalom
ros2 launch asv_gazebo scenario.launch.py scenario:=slalom          # world:=sydney_regatta hvis simulatoren kjører der
SCENARIO=slalom docker compose up
```
`scenario` kan også være en sti til en egen yaml-fil. I `sydney_regatta` fjernes først bøyerekka som følger med verdenen.

- **Nytt scenario:** lag en ny fil i `scenarios/` og bygg `asv_gazebo` på nytt.
- **Ny type ting:** lag en funksjon i `asv_gazebo/asv_gazebo/scenario.py` som returnerer SDF-en, og legg den i `TYPES`. I dag finnes `buoy` (markørbøye, farge `red`, `green`, `yellow`, `white` eller `black`).
- Startstedet til båten i hver verden står også i `scenario.py` (`WORLDS`).

`scenarios/slalom.yaml` er fire bøyer på linje nordover fra startstedet, 7 m fra hverandre. `config/path_slalom.yaml` er en bane som kjører sikksakk mellom dem (3 m på hver side), og så tilbake sørover øst for løypa. Banen har et fast nullpunkt (`origin`, breddegrad og lengdegrad for startstedet), så den treffer løypa selv om båten har drevet før start. Uten `origin` regnes punktene fra der båten er når noden starter.

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
Ikke bruk `--recursive`. PX4 henter selv de av sine egne submoduler bygget trenger. Submodulen peker på én commit på `main` hos control, der SITL-bygget for simulering (`px4_sitl_proteus`) ligger fra 2026-10-26. Nyeste commit på grenen hentes med `git submodule update --remote px4/Flightcontroller-px4`, men vi flytter bare pekeren til en commit som har bestått `px4_check`. Etter at pekeren er flyttet, bygger PX4 på nytt ved neste start.

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
HEADLESS=true docker compose up              # uten Gazebo-vindu
```
`vrx` bygger pakkene våre og kjører `sim.launch.py control:=px4`, som også starter `px4_hil_bridge`. PX4 kobler seg til den på TCP 4560 og får IMU, kompass, barometer og GPS derfra, med simuleringstiden som klokke (lockstep). Motorkommandoene går fortsatt som `MotorOutput` via agenten. `px4` bygger PX4 (første gang 30–60 min med ett løp om gangen, siden bare det som er endret) og starter den. Filene i `px4/Flightcontroller-px4/build/` eies av brukeren din, ikke root.

| Variabel | Standard | Betyr |
|---|---|---|
| `SIM` | `vrx_asv` | `vrx_asv`, `vrx` eller `fast`, som i `sim.launch.py` |
| `WORLD` | `open_water` | `open_water` (åpent hav) eller `sydney_regatta` (VRX med land), bare med `SIM=vrx_asv` |
| `SCENARIO` | ingen | scenario fra `asv_gazebo/scenarios/`, f.eks. `slalom` |
| `SENSOR_NOISE`, `WIND_SPEED`, `WIND_DIRECTION`, `WIND_GUST`, `CURRENT_SPEED`, `CURRENT_DIRECTION`, `WAVE_HEIGHT`, `WAVE_PERIOD`, `WAVE_DIRECTION`, `THRUST_TIME_CONSTANT` | av | se «Støy, vind, strøm og motortreghet» |
| `HEADLESS` | `false` | `true` = uten Gazebo-vindu |
| `FORWARD_THRUSTER` | `bow` | motoren `forward_propeller_thrust` sendes til |
| `PX4_TARGET` | `px4_sitl_proteus` | byggemålet i PX4 (control sitt SITL-bygg med modulene deres) |
| `PX4_SRC` | submodulen | mappe med en egen kopi av PX4-koden. PX4 bygges og kjøres derfra, med den grenen og de endringene som er der, også ucommittede |
| `UID`, `GID` | `1000` | brukeren PX4 kjører som. Sett `UID=$(id -u) GID=$(id -g)` hvis brukeren din har en annen id |
| `PX4_AIRFRAME` | `10016` | `none_iris`: PX4 får sensordata og klokke fra simulatoren. `10040` = `sihsim_quadx` (PX4 simulerer et quadkopter selv) |

**For control:** test egne endringer uten å pushe med `PX4_SRC=~/Flightcontroller-px4 docker compose up` (stien til deres egen kopi). Submodulen i repoet endres ikke, så alle andre tester fortsatt den faste versjonen.

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
- Vinklene er også -100..100 fra control (100 = 90° mot babord sett bakfra). Broen gjør dem om til radianer (`angle_scale` 0,0157), så `/control/thruster/*/angle` er fortsatt radianer.
- Positiv vinkel dreier thrusterne mot babord, og båten svinger da mot styrbord. Er fortegnet motsatt hos control, settes `angle_scale: -1.0`.
- Positiv baugthrust skyver baugen mot babord på `/control/thruster/bow/thrust`. Hos control skyver positiv `forward_propeller_thrust` den mot styrbord, så broen snur fortegnet.

**Kjent om SeapathData fra simulatoren:** posisjon, heading, roll, pitch og vinkelhastigheter er nøyaktige. Farten er regnet ut fra GPS (litt forsinket), heave er en tilnærming, og forsinket heave finnes ikke (merket ugyldig i `status`). `timestamp` er 0, så PX4 setter sin egen tid. Med vår båt går simulatoren nesten i sanntid (0,99), mens WAM-V går på ca. 0,7.

## Dokumentasjon
- [docs/status.md](docs/status.md): status, hva som er testet, og neste steg.
- [docs/px4.md](docs/px4.md): PX4-koblingen, hva vi vet om koden til control, og hva vi venter på fra dem.
- [docs/fallgruver.md](docs/fallgruver.md): ting som er lette å gå i.
