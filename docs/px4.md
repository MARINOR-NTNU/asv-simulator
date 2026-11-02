# PX4-koblingen

Hvordan control sin PX4 kobles til simulatoren, og hva vi vet om koden deres. Oppskriften for å kjøre det står i README under «Kjøre control sin PX4 mot simulatoren».

```
VRX-sensorer → px4_seapath_bridge → SeapathData → PX4 (control) → MotorOutput → px4_motor_bridge → VRX-motorer
```

Simulatoren erstatter `seapath`-driveren og `motor_writer` i PX4, så regulatorene til control kjører uendret.

## Control sin PX4-fork
- `MARINOR-NTNU/Flightcontroller-px4`. `git describe` gir `v1.18.0-beta1-828`, altså PX4 sin utviklingsgren. Vi endrer ikke koden deres. Siden 2026-10-20 ligger den som submodule i `px4/Flightcontroller-px4` (se «PX4 i vår egen container» under).
- Control bruker egne uORB-meldinger og noder, ikke PX4 sine vanlige actuator-topics. Kjeden er CCommand → regulatorene → `switch_wrench` → `thrust_allocator` → `switch_motor_output` → MotorOutput → `motor_writer`, med SeapathData fra `seapath` inn til regulatorene.
- Per 2026-10-19 er kjeden spredt på flere grener, og ingen gren har alt:

| Gren | Meldinger | Noder |
|---|---|---|
| `feature/control/mavlinkcommunicationwithcompanioncomputer` | `CCommand.msg` | – |
| `thrust_allocator` | `DesiredThrustVector.msg`, `TransitDesiredThrustVector.msg` | `switch_wrench`, `thrust_allocator`, `transit_controller` |
| `feature/control/motor_output_and_switch` | `MotorOutput.msg` | `switch_motor_output`, `motor_writer` |
| `feature/control/seapathDriver` | `SeapathData.msg` | `seapath` |
| `main` | `RcControlMode.msg` | `rcpublisher` |

- `dp_controller` og `switch_vel_heading` finnes ikke på GitHub.
- Per 2026-10-19 er `transit_controller`, `switch_wrench` og `thrust_allocator` skjeletter fra PX4 sin modulmal. `transit_controller` sender testtall (1 + n, 2 + n, 3 + n) og leser ingen sensorer, `switch_wrench` sender dem videre, og `thrust_allocator` skriver dem bare til loggen og publiserer ingen MotorOutput. Kjeden er altså ikke koblet sammen.
- Control sier (2026-10-19) at alt skal samles på `main`, men vet at koden er spredt nå. Feature-grener kan testes med `PX4_BRANCH=<gren> scripts/sync_px4_msgs.sh` (se px4_msgs under).
- Control startet først PX4 med `make px4_sitl_sih sihsim_quadx` (2026-10-19), altså SITL med PX4 sin innebygde simulator (SIH) som simulerer et quadkopter.
- Nå sier de `make px4_sitl_proteus none_iris` (2026-10-20): PX4 uten mikrokontroller og uten fysikkmotor. Det passer med at VRX er fysikken, og det fjerner quadkopteret fra SIH. Per 2026-10-20 finnes ikke `px4_sitl_proteus` på GitHub. Grenen `feature/control/proteus_board` har bare `boards/px4/fmu-v6c/proteus.px4board`, som er et bygg for Pixhawk-kortet (`make px4_fmu-v6c_proteus upload`). Det har ingen av modulene til control (`switch_motor_output`, `seapath`, `thrust_allocator`, `transit_controller`), men PX4 sine quadkopter-regulatorer og EKF2.
- `none_iris` er airframe-fila `10016_none_iris`. Da starter `px4-rc.simulator` modulen `simulator_mavlink`, som venter på en simulator over MAVLink på TCP 4560. Uten en simulator der stopper oppstartsskriptet («Waiting for simulator to accept connection on TCP port 4560»), og verken `uxrce_dds_client` eller noen andre moduler etter den linja startes (testet 2026-10-20). Control fant det samme. Løst 2026-10-26 med `px4_hil_bridge` (se under).
- Per 2026-10-19 er ingen av de to SITL-byggene komplette: `sih.px4board` har `switch_wrench`, `thrust_allocator` og `transit_controller` (grenen `thrust_allocator`), og `default.px4board` har `seapath` (grenen `seapathDriver`). `switch_motor_output` og `motor_writer` er bare slått på i `boards/px4/fmu-v6c`, og `switch_motor_output start` står bare i `rc.board_defaults` der. I SITL sender PX4 derfor ingen MotorOutput.
- I SITL kobler PX4 seg til agenten på 127.0.0.1:8888 (`UXRCE_DDS_AG_IP` i `init.d-posix/rcS`). Agenten kjører i vår container, så control sin container må kjøre med `--net=host`, eller så må `UXRCE_DDS_AG_IP` settes til IP-en vår (`param set`, ingen kodeendring).
- Motor-committen deres endrer `boards/px4/fmu-v6c`, så kortet er trolig en Pixhawk 6C (ikke bekreftet).

## PX4 i vår egen container (fra 2026-10-20)
Bestemt 2026-10-20: control sin PX4-kode kjøres som SITL fra vårt repo, i en egen container ved siden av VRX-containeren. Agenten blir i VRX-containeren. Oppskriften står i README under «Kjøre control sin PX4 mot simulatoren».
- Koden ligger som submodule i `px4/Flightcontroller-px4`, låst til én commit på `feature/control/sitl_proteus` (fra 2026-10-26, før det `proteus_board`). Vi endrer ikke koden der, men kan sjekke ut andre commits lokalt for å teste. Med `PX4_SRC` kan control bygge fra sin egen kopi i stedet.
- `Dockerfile.px4` gir imaget `px4-sitl:proteus` med bare verktøykjeden. Koden monteres inn og bygges i containeren. Hele repoet monteres, fordi submodulens `.git` peker til `../../.git/modules/`.
- `docker-compose.yml` starter `vrx` og `px4` med host-nettverk, så PX4 finner agenten på 127.0.0.1:8888. PX4 kjører som brukeren på verten, så byggefilene ikke eies av root.
- `.dockerignore` holder submodulen (flere GB) utenfor byggekonteksten til begge imagene.

Testet 2026-10-20 med `sim:=fast`:
- `proteus_board` (`363af02f1b`) kompilerer ikke: `uORB/ucdr/motor_output.h: No such file or directory`. `dds_topics.yaml` har `motor_output`, men `MotorOutput.msg` er ikke merget inn.
- Commiten `7b3517e1f5` på samme gren feiler i cmake fordi `LICENSE` var slettet (CPack krever den). Den er tilbake i nyere commits.
- `seapathDriver` (`5df9df6e63`) kompilerer. Med `sihsim_quadx` (`PX4_SYS_AUTOSTART=10040`) kobler PX4 seg til agenten med en gang, og 69 `/fmu`-topics fra PX4 vises i ROS 2. `motor_output` og `seapath_data` mangler, fordi den grenen ikke har dem i `dds_topics.yaml`. Samme resultat med `docker compose up`.
- Med `none_iris` henger PX4 ved oppstart (se over).
- Agenten (v2.4.2, Humble) gir PX4 sine forbindelser nodenavnet `_CREATED_BY_BARE_DDS_APP_`. `px4_check` så etter `_NODE_NAME_UNKNOWN_` og sa feilaktig at PX4 ikke var koblet til. Rettet.

## `sitl_proteus` (testet 2026-10-26)
Control har laget `feature/control/sitl_proteus` med `boards/px4/sitl/proteus.px4board` («headless og fysikkløs sitl simulering»), basert på `main`, der `proteus_board` og `motor_output_and_switch` er merget inn (21. oktober). README-en deres anbefaler `make px4_sitl_proteus none_iris` til egen simulering. Submodulen peker nå dit (`70b86d3e68`), og `px4_sitl_proteus` er standard i compose.
- Den har `MotorOutput.msg`, `SeapathData.msg` og `RcControlMode.msg`, riktig `dds_topics.yaml`, og modulene `switch_motor_output`, `rcPublisher`, `motor_writer` og `seapath` bygget inn. Meldingene er like vår `px4_msgs`.
- Den kompilerer. Med `none_iris` og `px4_hil_bridge` starter PX4, kobler seg til agenten (71 topics), og `px4_check` viser at PX4 sender `motor_output` og tar imot `seapath_data`. Inne i PX4 viser `listener seapath_data` riktig posisjon og heading (0,5708 rad, som båten i simulatoren).
- Det kommer ingen data på `motor_output`. Ingenting starter `switch_motor_output`, `rcPublisher` eller `motor_writer` i SITL (ingen endringer i oppstartsfilene). Startet for hånd kjører `switch_motor_output`, men den sender bare når den får `rc_control_mode`, som `rcPublisher` bare lager når det finnes `input_rc` fra en RC-mottaker. Det finnes ikke i SITL: `input_rc`, `rc_control_mode` og `motor_output` er alle «never published».
- Byggefeilen `mavgen.py ... missing` (control fikk den 2026-11-02) betyr at `pymavlink`, en submodule inni MAVLink-submodulen, ikke er hentet. Løsning: `git submodule update --init --recursive` i PX4-repoet. Compose gjør det selv.
- `CMakeLists.txt` (linje 113) kopierer `custom.xml` inn i `src/modules/mavlink/mavlink/` når cmake kjører. På en ny kopi skjer det før PX4 henter MAVLink-submodulen, så hentingen feiler («already exists and is not an empty directory»). Compose henter derfor MAVLink-submodulen før `make`. Samme kopiering gjør at submodulen ser endret ut etter bygget, så `.gitmodules` har `ignore = untracked`.
- Mulig løsning på RC-problemet uten å endre koden deres: `px4_hil_bridge` kan sende RC-verdier over MAVLink (som en RC-sender). Ikke sjekket om `simulator_mavlink` gjør dem om til `input_rc`.

## `feature/control/start_modules_init` (testet 2026-11-01)
Control sa at punkt 1–3 fra meldingen 26. oktober var gjort på denne grenen (`0b07ba25b6`). Samme resultat med `scripts/test_control.sh feature/control/start_modules_init`: alt ✓ unntatt sikkerhetstesten. Testet lokalt i submodulen (ikke committet, submodulen peker fortsatt på `main`):
- ✅ Modulene starter av seg selv i SITL (`init.d-posix/rcS`): `rcPublisher`, `motor_writer`, `switch_motor_output`, `switch_wrench`, `thrust_allocator`, `transit_controller`.
- ✅ Uten RC sender `switch_motor_output` 0 i `motor_output`.
- ✅ Med virtuell RC (1700 µs) kommer 40 % ut, som før.
- ❌ **Når RC forsvinner, fortsetter `motor_output` med siste RC-verdi i det uendelige** (målt 40 % i over 12 s). `rc_control_mode_sub.copy()` gir alltid siste melding, uansett alder, og alderen sjekkes ikke. På båten kjører den videre med siste kommando hvis fjernkontrollen mister kontakten. `thruster_adapter` slår ikke inn, fordi `MotorOutput` fortsetter å komme.
- ❌ Tidsgrensen er `0.5*10E6` µs, altså 5 s, ikke 0,5 s (`10E6` = 10 000 000).
- ❌ `custom.xml`-feilen i `CMakeLists.txt` og `+1` i vinkelformelen i `rcPublisher` er ikke endret på noen gren.
- Rettelse testet 2026-11-01 i en lokal kopi med `scripts/test_control.sh --src` (alt ✓, motorene stopper etter 1,0 s): i `SwitchMotorOutput.cpp`, legg `and hrt_elapsed_time(&rc_values.timestamp) < 500_ms` til i den første `if`-en, og endre `0.5*10E6` til `0.5*1E6`. Sendt som forslag til control.

## `main` hos control (testet 2026-10-26, kl. 15)
Control har slått sammen `sitl_proteus` inn i `main` (pull request #4), og `rcPublisher` regner nå om RC fra 1000–2000 µs til -100..100 for alle fire kanalene. Submodulen følger `main` (`8420d758a2`). Med virtuell RC og modulene startet for hånd, og broen med standardinnstillinger (ingen midlertidig omregning):
- 1700 µs på begge akterthrusterne gir 40 % i `motor_output`, 20 N og 1,62 m/s. Bare babord motor svinger båten med klokka. Baugen på 1700 µs gir -10 N (baugen mot styrbord). Kraft og fortegn stemmer.
- **Vinkelen kommer også som -100..100, ikke radianer som avtalt.** RC 1750 gir 50 i `port_side_angle`, som broen sender videre som 50 rad (begrenset til 90° i `thruster_adapter`). Bestemt 2026-10-26: vi godtar -100..100 også for vinkelen. `angle_scale` i `config/px4_bridge.yaml` er π/2/100 = 0,0157, så 100 blir 90° mot babord, og kontrakten på ROS-siden er fortsatt radianer.
- Fortsatt mangler: modulene startes ikke i SITL, og `custom.xml`-feilen ved ny kopi er ikke rettet.

## Hele veien fra PX4 til motorene (testet 2026-10-26)
Med `sitl_proteus` og Gazebo, uten å endre koden til control:
- `switch_motor_output` og `rcPublisher` startes for hånd (`../bin/px4-switch_motor_output start`, `../bin/px4-rcPublisher start` i `build/px4_sitl_proteus/rootfs`), fordi SITL-bygget ikke starter dem.
- `px4_hil_bridge` sender RC som `RC_CHANNELS` (parameteren `rc_channels`), og `simulator_mavlink` gjør det om til `input_rc`. Kanalene hos control: 0 baug, 1 babord, 2 styrbord, 3 vinkel (felles), 6 (SC) modus, 7 (SD) manuell. SD ≥ 1500 og SC 1550–2100 gir direkte motorstyring (modus 7).
- Resultat: `input_rc` → `rc_control_mode` (modus 7) → `motor_output` → `/fmu/out/motor_output` (50 Hz) → `px4_motor_bridge` → `/control/thruster/...`. Hele kjeden virker.
- **`switch_motor_output` sender rå RC-verdier (ca. 1000–2000 µs) som `MotorOutput`**, både for thrust og vinkel, ikke -100..100 % og radianer som avtalt. Med vår standardskala blir 1700 µs 850 N (begrenset til 50 N) og vinkelen «1500 rad» (full utslag), og båten snurrer rundt. Omregningen må gjøres hos control.
- Med en midlertidig omregning i broen (1500 µs = 0, ±500 µs = full kraft eller ±90°) oppfører båten seg riktig: 1700 µs på begge gir 20 N og stabil fart 1,62 m/s forover, og bare babord motor svinger båten med klokka (mot styrbord), som kontrakten sier.

## MAVLink-koblingen: `px4_hil_bridge`
Avtalt med control 2026-10-26: motorkommandoene kommer fortsatt som `MotorOutput` via agenten. MAVLink brukes bare til å gi PX4 sensordata og klokke, så PX4 starter med `none_iris`.
- PX4 (`simulator_mavlink`) kobler seg til simulatoren som TCP-klient (`connect()`), så `px4_hil_bridge` lytter på TCP 4560.
- For hver IMU-melding sendes `HIL_SENSOR` (akselerometer, gyro, kompass, barometer, trykkhøyde og temperatur, ikke airspeed). For hver GPS-melding sendes `HIL_GPS`. Alt regnes om fra ENU/FLU til NED/FRD.
- Kompasset regnes ut fra båtens orientering og et fast magnetfelt (`mag_ned` i `config/px4_bridge.yaml`, satt for sydney_regatta). PX4 sammenligner det med sin modell for GPS-posisjonen, så det må endres hvis verdenen flyttes.
- Barometeret er standardatmosfæren ved GPS-høyden.
- Tidsstempelet er simuleringstiden. I lockstep går PX4 sin klokke bare når det kommer `HIL_SENSOR`, så PX4 følger simulatorens klokke, også når den går saktere eller fortere enn sanntid.
- Det PX4 sender tilbake (`HEARTBEAT`, `HIL_ACTUATOR_CONTROLS`), leses og kastes.
- PX4 forventer IMU på ca. 250 Hz (`IMU_INTEG_RATE`). Vår IMU i Gazebo går på 100 Hz, og det går fint.

Testet 2026-10-26 med `seapathDriver` og `none_iris`, både med `sim:=fast` og med Gazebo uten vindu: PX4 starter helt, kobler seg til agenten (69 topics), PX4 sin tid følger `/clock` (56,96 s mot 56 s), `sensor_combined` viser -9,81 i z, GPS har fix 3 og riktig posisjon, kompasset stemmer med heading, og EKF2 lager `vehicle_global_position`. Med Gazebo skriver PX4 `poll timeout` mens verdenen lastes (før det kommer IMU), og det stopper når Gazebo er i gang.

## Meldingene
- `MotorOutput`: `forward_propeller_thrust`, `port_side_thrust`, `port_side_angle`, `starboard_thrust`, `starboard_angle`.
  - Avtalt med control 2026-10-19: thrust er -100..100, som betyr 0–100 % kraft forover og bakover.
  - `forward_propeller_thrust` er baugthrusteren. Positiv verdi skyver baugen mot styrbord (NED/FRD), altså motsatt av kontrakten på `/control/thruster/bow/thrust`. Broen snur fortegnet, og kontrakten er uendret.
  - Vinklene er i radianer, positiv mot babord sett bakfra, 0 rett bakover og ±90° (±π/2) som ytterpunkter, likt for begge (2026-10-19). Det er det samme som kontrakten.
  - Bakover gir akterthrusterne bare ca. 60 % av kraften forover (2026-10-19). Det ligger både i modellen (`min_thrust_cmd` -30 N) og i broen (`stern_reverse_ratio`). Baugthrusteren skal være like sterk begge veier (2026-10-19).
  - I dag sender RC-veien rå RC-verdier (ca. 1000–2000 µs) og regulatorveien faste plassholdere (±1). Begge vinklene kommer fra samme RC-spak.
- `SeapathData`: posisjon (grader), fart i NED, roll, pitch og heading (radianer, heading 0 til 2π), vinkelhastigheter, heave og status. Fortegn som Seapath, som er NED/FRD. Ingen kode leser den ennå.
  - Control sier (2026-10-19) at regulatorene skal bruke posisjon, heading og kurs, og at vi gjerne fyller ut hele meldingen (det gjør vi). Meldingen har ikke noe kursfelt, men kurs over grunn er `atan2(vel_e, vel_n)`.
  - `seapath`-driveren publiserer også `vehicle_attitude`, `vehicle_local_position` og `vehicle_global_position` ut fra serieporten. Det gjør ikke broen vår. Leser regulatorene de topicene i stedet for `seapath_data`, får de data fra SIH, ikke fra båten vår.
- `CCommand`: ønsket fart, kurs, posisjon, krefter eller motorverdier, og `control_mode` (VELOCITYHEADING, WRENCH eller MOTOR_OUTPUT). Ingen kode bruker den ennå. Filen har semikolon etter feltene (`uint64 timestamp;`), som ikke er gyldig i en `.msg`-fil.

## px4_msgs
- `px4_msgs/` har bare meldingene som går mellom PX4 og simulatoren: `MotorOutput.msg` og `SeapathData.msg` (bestemt 2026-10-19). De kopieres med `scripts/sync_px4_msgs.sh` fra feature-grenene til control, og `px4_msgs/SOURCE.txt` viser hvilke commits de kom fra. Meldingene må være helt like hos control og hos oss, ellers kommer de ikke fram.
- Trengs en melding til (for eksempel `CCommand`), legges den til i lista øverst i skriptet. De andre PX4-meldingene er tatt ut, så `/fmu/out/...`-topics med andre typer kan ikke leses fra ROS 2 før typen er lagt til.
- Pakken bygges inn i imaget og ligger derfor ikke i `src/`, for da ville colcon funnet to pakker med samme navn.
- Når control har oppdatert grenene sine: `git -C px4/Flightcontroller-px4 fetch`, deretter `scripts/sync_px4_msgs.sh` og bygg imaget på nytt. Grenene som brukes, står øverst i skriptet.
- Andre grener: `PX4_BRANCH=main scripts/sync_px4_msgs.sh` henter alle meldingene fra én gren. Mangler grenen en av meldingene, stopper skriptet uten å endre noe.

## uXRCE-DDS og agenten
- PX4 slipper bare ut topics som står i `src/modules/uxrce_dds_client/dds_topics.yaml`. Ingen gren har `motor_output` eller `seapath_data` der ennå.
- PX4 bruker v2-klienten (`UXRCE_DDS_CLIENT_USE_DDS_V3` er ikke satt). Dokumentasjonen deres sier Agent v2.4.2 for Humble.
- Bestemt 2026-10-19: VRX og control kjører i hver sin container, og agenten kjører i vår. Bare XRCE (UDP port 8888) går mellom containerne, og all DDS-trafikk blir i vår container. Ikke flytt agenten til control sin container: DDS mellom to containere på samme PC prøver shared memory i Fast-DDS, og da kommer det ikke data uten `--ipc=host` på begge.
- Mot SITL: `MicroXRCEAgent udp4 -p 8888` (startes av `sim.launch.py control:=px4`). Mot et kort på USB: `MicroXRCEAgent serial --dev /dev/ttyACM0 -b 921600`, og containeren må startes med `--device /dev/ttyACM0` (port og baudrate er ikke sjekket).
- `ROS_DOMAIN_ID` må være lik `UXRCE_DDS_DOM_ID` i PX4 (begge er 0 som standard).

## Broene
- `px4_motor_bridge`: `/fmu/out/motor_output` → `/control/thruster/{left,right}/{thrust,angle}`. Babord = left, styrbord = right. Verdien som sendes er `(verdi - offset) * scale`. Thrust er -100..100 %, så `stern_thrust_scale` er 0,5 (50 N) og `forward_thrust_scale` er -0,25 (25 N, med snudd fortegn). Negative verdier ganges i tillegg med `stern_reverse_ratio` (0,6) eller `forward_reverse_ratio` (1,0), så -100 % akter blir -30 N. Maks thrust er anslag for vår båt; med WAM-V må `stern_thrust_scale` være ca. 23,5. Vinklene sendes rett gjennom. `forward_propeller_thrust` ignoreres til `forward_thruster` settes.
- Prosentskaleringen er testet 2026-10-19 med `ros2 topic pub`: 100 → 50 N, 80 → 40 N, -100 → -30 N, baug 60 → -15 N og -60 → 15 N, vinkel -1,5708 rett gjennom.
- `px4_seapath_bridge`: `/autonomy/imu` og `/autonomy/gps/fix` → `/fmu/in/seapath_data` (NED/FRD, 50 Hz). Omregningen fra ENU/FLU ligger i `frames.py`. Fart er GPS-posisjon derivert og glattet (`tau`), heave er høyden under en glattet middelhøyde (`heave_tau`, 20 s), og forsinket heave er merket ugyldig. Dette er tilnærminger.
- Innstillingene ligger i `config/px4_bridge.yaml`. Bare broene, til en simulator som allerede kjører: `ros2 launch sim_interface px4_bridge.launch.py`.
- Testet 2026-10-19 med `ros2 topic pub` på `/fmu/out/motor_output`, både med WAM-V og med vår båt (`forward_thruster:=bow`). Hvert felt når riktig motor, timeouten setter thrust til 0, og i SeapathData stemmer heading med `heading_node` og fartsretningen med baugen (innen 0,3°). Heave svinger rundt 0 (±0,10 m i bølgene). Ikke testet mot ekte PX4.
- Målt med kontraktens fortegn: positiv vinkel på akterthrusterne snur båten med klokka (mot styrbord), og positiv baugthrust snur den mot klokka (baugen mot babord).

## Diagnose: `px4_check`
`ros2 run sim_interface px4_check` sjekker koblingen ledd for ledd og sier hvor den stopper: simulatoren og broene, agenten (prosess og UDP-port), om PX4 er koblet til, om PX4 sender MotorOutput og tar imot SeapathData, og om tallene i MotorOutput er plassholdere (0 og ±1), rå RC-verdier (ca. 1000–2000) eller NaN.

- PX4 sine forbindelser lages av agenten, som ikke er en ROS-node, så de vises som `_NODE_NAME_UNKNOWN_`. Det er slik verktøyet ser at PX4 er koblet til. Testet 2026-10-19 uten PX4 og med `ros2 topic pub`, ikke mot ekte PX4.
- Feil som bare følger av en feil lenger opp i kjeden, vises som «følger av …», så det er den første ✗ som skal rettes.

## CCOMMAND: ønsket kurs og fart til PX4 (`ccommand_bridge`)
Laget 2026-11-01. På båten sender jetson ønskede verdier til PX4 som MAVLink-meldingen `CCOMMAND` (id 50000, definert av control i `src/modules/mavlink/custom_messages/custom.xml`). `ccommand_bridge` gjør det samme i simulatoren, så autonomy-noden kan kjøre uendret mot både `control:=stub` og `control:=px4`.
- Starter med `control:=px4 ccommand:=true` (compose: `CCOMMAND=true`, f.eks. `AUTONOMY=fake CCOMMAND=true docker compose up`).
- Leser `/autonomy/desired/heading` (rad, ENU) og `/autonomy/desired/speed` (m/s). Sender `desired_speed` i m/s og `desired_course` som kompasskurs i radianer (0 = nord, med klokka, 0 til 2π), `control_mode` 0 (VELOCITYHEADING), `is_ground_controlled` 0. De andre feltene er 0.
- 10 Hz til UDP 14580, som er PX4 sin MAVLink-instans for onboard-datamaskinen i SITL (`px4-rc.mavlink`). System 1, komponent 191 (`MAV_COMP_ID_ONBOARD_COMPUTER`). Alt kan endres i `px4_bridge.yaml`.
- Sender ingenting når de ønskede verdiene er eldre enn 0,5 s, så PX4 kan merke at autonomy er borte.
- Meldingskoden lages fra `src/sim_interface/mavlink/custom.xml` når noden starter. Fila er en kopi av control sin `custom.xml` uten `<include>`, og `scripts/sync_px4_msgs.sh` oppdaterer den.
- Testet 2026-11-01 med control sin `main` (`8420d758a2`): `mavlink status` i PX4 viser `msgid:50000, Rate: 10.0 Hz` fra system 1, komponent 191 på instansen for port 14580, uten tapte meldinger. PX4 er bygget med dialekten `custom`, så sjekksummen stemmer og meldingen tas imot. Ingen modul i PX4 bruker den ennå, så regulatorene får ikke verdiene.
- `scripts/test_control.sh` sjekker CCOMMAND til slutt (`px4_ccommand_test`): at PX4 tar imot (msgid 50000 i `mavlink status`), at PX4 gir motorkraft fra den med RC av, at båten snur 90° til ønsket kurs innen 40 s og holder 1 m/s, og at motorene stopper innen 1,5 s når de ønskede verdiene forsvinner (forslag, ikke avtalt). Med control sin `main` 2026-11-01: ✓ PX4 tar imot (10 Hz), ✗ resten, fordi ingen modul leser meldingen. Uten RC sender `main` heller ingen MotorOutput.
- Svar fra control 2026-11-02: kompasskurs i radianer er riktig (det er slik autonomy skal sende den), og port 14580 er riktig. Hva som skjer når `CCOMMAND` forsvinner, skal løses som når RC forsvinner.
- Mottakeren finnes på `feature/control/mavlinkcommunicationwithcompanioncomputer` (`88e8f37798`, 2026-10-20): `handle_message_ccommand` i `mavlink_receiver.cpp` publiserer uORB `c_command`. Den er ikke merget inn i `main` eller `start_modules_init`, og grenen er eldre enn `sitl_proteus`. Ingen modul på noen gren abonnerer på `c_command` ennå, så regulatorene får ikke verdiene.
- Testet 2026-11-02 i en lokal kopi (ikke pushet): `main` + `start_modules_init` (`6b83b40fa7`) + mottakergrenen. Eneste konflikt var beskrivelsen av `CCOMMAND` i `custom.xml` (feltene er like). Bygger, og `listener c_command` i PX4 viser det `ccommand_bridge` sender (`desired_speed: 1.0`, `desired_course: 1.5708` for kurs mot øst, `control_mode: 0`). `test_control.sh --src`: alt ✓ unntatt sikkerhetstesten for RC, og CCOMMAND-testen kan ikke gå videre fordi motorene fortsatt går fra RC-testen.

## Klokka
Control vil helst at PX4 følger simulatorens klokke (2026-10-19). Løst 2026-10-26: med `none_iris` får PX4 tiden sin fra `HIL_SENSOR` som `px4_hil_bridge` sender med simuleringstiden (lockstep). PX4 følger derfor simulatoren også når den går saktere eller fortere enn sanntid. Gazebo med vår båt går på 0,99 av sanntid.

## Svar fra control 2026-10-19
- Gren: skal være `main`, men koden er spredt nå.
- MotorOutput: thrust -100..100 = 0–100 % forover og bakover. `forward_propeller_thrust` er baugthrusteren, positiv skyver baugen mot styrbord.
- `seapath` og `motor_writer`: kan slås av med egen sim-config, men de spør om det er et problem. I SITL er det trolig ikke det: `seapath` finner ingen serieport og publiserer ingenting, og `motor_writer` skriver bare til loggen (200 Hz). Se SeapathData over om `vehicle_*`-topicene.
- SeapathData: posisjon, heading og kurs, gjerne hele meldingen.
- Klokka: se over.
- Hvordan de starter PX4: `make px4_sitl_sih sihsim_quadx` (eller `px4_sitl_default`) i en container. Endret 2026-10-20 til `make px4_sitl_proteus none_iris` (se over).
- Vinklene: radianer, positiv mot babord sett bakfra, ±90°.
- Bakover: -100 % er ca. 60 % av kraften forover.
- Baugthrusteren: positiv mot styrbord (bekreftet), og like sterk begge veier.

## Venter på svar fra control
- At `switch_motor_output` sjekker at RC-meldingen er fersk, og sender 0 når RC har vært borte i 0,5 s (nå: siste verdi for alltid). Modulstart i SITL er gjort på `feature/control/start_modules_init`, ikke i `main` ennå.
- Hva `switch_motor_output` skal gjøre uten RC i simulatoren: bruke regulatorveien, sende 0, eller få RC-verdier fra simulatoren (`rc_channels` i `px4_hil_bridge` virker).
- At kopieringen av `custom.xml` i `CMakeLists.txt` skjer etter at MAVLink-submodulen er hentet, så en ny kopi bygger uten triks.
- CCOMMAND: merge mottakeren (`mavlinkcommunicationwithcompanioncomputer`) inn i `main`, en modul som leser `c_command` og gir verdiene til regulatorene, og stopp når meldingen forsvinner (som for RC). Semikolonene i `CCommand.msg` er rettet på mottakergrenen.
