# PX4-koblingen

Hvordan control sin PX4 kobles til simulatoren, og hva vi vet om koden deres. Oppskriften for å kjøre det står i README under «Kjøre control sin PX4 mot simulatoren».

```
VRX-sensorer → px4_seapath_bridge → SeapathData → PX4 (control) → MotorOutput → px4_motor_bridge → VRX-motorer
```

Simulatoren erstatter `seapath`-driveren og `motor_writer` i PX4, så regulatorene til control kjører uendret.

## Control sin PX4-fork
- `MARINOR-NTNU/Flightcontroller-px4`. `git describe` gir `v1.18.0-beta1-828`, altså PX4 sin utviklingsgren. Vi endrer ikke koden deres, vi leser den bare (`git show`, `git ls-tree`).
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
- Motor-committen deres endrer `boards/px4/fmu-v6c`, så kortet er trolig en Pixhawk 6C (ikke bekreftet).

## Meldingene
- `MotorOutput`: `forward_propeller_thrust`, `port_side_thrust`, `port_side_angle`, `starboard_thrust`, `starboard_angle`. I dag sender RC-veien rå RC-verdier (ca. 1000–2000 µs) og regulatorveien faste plassholdere (±1). Begge vinklene kommer fra samme RC-spak.
- `SeapathData`: posisjon (grader), fart i NED, roll, pitch og heading (radianer, heading 0 til 2π), vinkelhastigheter, heave og status. Fortegn som Seapath, som er NED/FRD. Ingen kode leser den ennå.
- `CCommand`: ønsket fart, kurs, posisjon, krefter eller motorverdier, og `control_mode` (VELOCITYHEADING, WRENCH eller MOTOR_OUTPUT). Ingen kode bruker den ennå. Filen har semikolon etter feltene (`uint64 timestamp;`), som ikke er gyldig i en `.msg`-fil.

## px4_msgs
- `px4_msgs/` har bare meldingene som går mellom PX4 og simulatoren: `MotorOutput.msg` og `SeapathData.msg` (bestemt 2026-10-19). De kopieres med `scripts/sync_px4_msgs.sh` fra feature-grenene til control, og `px4_msgs/SOURCE.txt` viser hvilke commits de kom fra. Meldingene må være helt like hos control og hos oss, ellers kommer de ikke fram.
- Trengs en melding til (for eksempel `CCommand`), legges den til i lista øverst i skriptet. De andre PX4-meldingene er tatt ut, så `/fmu/out/...`-topics med andre typer kan ikke leses fra ROS 2 før typen er lagt til.
- Pakken bygges inn i imaget og ligger derfor ikke i `src/`, for da ville colcon funnet to pakker med samme navn.
- Når control har oppdatert grenene sine: `git -C ~/Flightcontroller-px4 fetch`, deretter `scripts/sync_px4_msgs.sh` og bygg imaget på nytt. Grenene som brukes, står øverst i skriptet.

## uXRCE-DDS og agenten
- PX4 slipper bare ut topics som står i `src/modules/uxrce_dds_client/dds_topics.yaml`. Ingen gren har `motor_output` eller `seapath_data` der ennå.
- PX4 bruker v2-klienten (`UXRCE_DDS_CLIENT_USE_DDS_V3` er ikke satt). Dokumentasjonen deres sier Agent v2.4.2 for Humble.
- Bestemt 2026-10-19: VRX og control kjører i hver sin container, og agenten kjører i vår. Bare XRCE (UDP port 8888) går mellom containerne, og all DDS-trafikk blir i vår container. Ikke flytt agenten til control sin container: DDS mellom to containere på samme PC prøver shared memory i Fast-DDS, og da kommer det ikke data uten `--ipc=host` på begge.
- Mot SITL: `MicroXRCEAgent udp4 -p 8888` (startes av `sim.launch.py control:=px4`). Mot et kort på USB: `MicroXRCEAgent serial --dev /dev/ttyACM0 -b 921600`, og containeren må startes med `--device /dev/ttyACM0` (port og baudrate er ikke sjekket).
- `ROS_DOMAIN_ID` må være lik `UXRCE_DDS_DOM_ID` i PX4 (begge er 0 som standard).

## Broene
- `px4_motor_bridge`: `/fmu/out/motor_output` → `/control/thruster/{left,right}/{thrust,angle}`. Babord = left, styrbord = right. Enhetene er ikke avklart, så verdien som sendes er `(verdi - offset) * scale` (standard: rett gjennom). `forward_propeller_thrust` ignoreres til `forward_thruster` settes.
- `px4_seapath_bridge`: `/autonomy/imu` og `/autonomy/gps/fix` → `/fmu/in/seapath_data` (NED/FRD, 50 Hz). Omregningen fra ENU/FLU ligger i `frames.py`. Fart er GPS-posisjon derivert og glattet (`tau`), heave er høyden under en glattet middelhøyde (`heave_tau`, 20 s), og forsinket heave er merket ugyldig. Dette er tilnærminger.
- Innstillingene ligger i `config/px4_bridge.yaml`. Bare broene, til en simulator som allerede kjører: `ros2 launch sim_interface px4_bridge.launch.py`.
- Testet 2026-10-19 med `ros2 topic pub` på `/fmu/out/motor_output`, både med WAM-V og med vår båt (`forward_thruster:=bow`). Hvert felt når riktig motor, timeouten setter thrust til 0, og i SeapathData stemmer heading med `heading_node` og fartsretningen med baugen (innen 0,3°). Heave svinger rundt 0 (±0,10 m i bølgene). Ikke testet mot ekte PX4.
- Målt med kontraktens fortegn: positiv vinkel på akterthrusterne snur båten med klokka (mot styrbord), og positiv baugthrust snur den mot klokka (baugen mot babord).

## CCommand (kommer)
Control sin kjede starter med `CCommand`, som på båten kommer over MAVLink fra companion-maskinen. Når autonomy-noden og mottakeren hos control finnes, trengs en bro fra `/autonomy/desired/{heading,speed}` til `CCommand`. Da kan autonomy-noden kjøre uendret mot både `control:=stub` og `control:=px4`. Om broen skal gå over MAVLink eller XRCE-DDS, er ikke avklart.

## Venter på svar fra control
- At de legger `/fmu/out/motor_output` (publications) og `/fmu/in/seapath_data` (subscriptions) inn i `dds_topics.yaml`.
- Hvilken gren kjeden skal samles på, og når.
- Enhetene i MotorOutput (newton, -1..1 eller noe annet), grader eller radianer, fortegn på vinklene, og hvor langt akterthrusterne kan dreie.
- Om `forward_propeller_thrust` er baugthrusteren, og hvilken vei positiv verdi skyver.
- Hvordan de starter PX4 SITL i sin container, om den kjører på samme PC med `--net=host`, eller om PX4 skal kjøre på kortet.
- Om `seapath`-driveren og `motor_writer` slås av når PX4 kjører mot simulatoren.
- Hvilke felt i SeapathData regulatorene skal bruke.
- Om PX4 skal følge simulatorens klokke (lockstep) eller sanntid.
- CCommand: semikolonene i filen, enhetene i `desired_course` og `desired_speed`, og om den skal inn over MAVLink eller XRCE-DDS i simulatoren.
