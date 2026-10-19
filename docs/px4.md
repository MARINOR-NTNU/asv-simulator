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
- Per 2026-10-19 er `transit_controller`, `switch_wrench` og `thrust_allocator` skjeletter fra PX4 sin modulmal. `transit_controller` sender testtall (1 + n, 2 + n, 3 + n) og leser ingen sensorer, `switch_wrench` sender dem videre, og `thrust_allocator` skriver dem bare til loggen og publiserer ingen MotorOutput. Kjeden er altså ikke koblet sammen.
- Control sier (2026-10-19) at alt skal samles på `main`, men vet at koden er spredt nå. Feature-grener kan testes med `PX4_BRANCH=<gren> scripts/sync_px4_msgs.sh` (se px4_msgs under).
- Control starter PX4 i en container med `make px4_sitl_sih sihsim_quadx` eller `make px4_sitl_default sihsim_quadx` (2026-10-19). Det er SITL med PX4 sin innebygde simulator (SIH) som simulerer et quadkopter, uten Gazebo. Begge går i sanntid.
- Per 2026-10-19 er ingen av de to SITL-byggene komplette: `sih.px4board` har `switch_wrench`, `thrust_allocator` og `transit_controller` (grenen `thrust_allocator`), og `default.px4board` har `seapath` (grenen `seapathDriver`). `switch_motor_output` og `motor_writer` er bare slått på i `boards/px4/fmu-v6c`, og `switch_motor_output start` står bare i `rc.board_defaults` der. I SITL sender PX4 derfor ingen MotorOutput.
- I SITL kobler PX4 seg til agenten på 127.0.0.1:8888 (`UXRCE_DDS_AG_IP` i `init.d-posix/rcS`). Agenten kjører i vår container, så control sin container må kjøre med `--net=host`, eller så må `UXRCE_DDS_AG_IP` settes til IP-en vår (`param set`, ingen kodeendring).
- Motor-committen deres endrer `boards/px4/fmu-v6c`, så kortet er trolig en Pixhawk 6C (ikke bekreftet).

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
- Når control har oppdatert grenene sine: `git -C ~/Flightcontroller-px4 fetch`, deretter `scripts/sync_px4_msgs.sh` og bygg imaget på nytt. Grenene som brukes, står øverst i skriptet.
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

## CCommand (kommer)
Control sin kjede starter med `CCommand`, som på båten kommer over MAVLink fra companion-maskinen. Når autonomy-noden og mottakeren hos control finnes, trengs en bro fra `/autonomy/desired/{heading,speed}` til `CCommand`. Da kan autonomy-noden kjøre uendret mot både `control:=stub` og `control:=px4`. Om broen skal gå over MAVLink eller XRCE-DDS, er ikke avklart.

## Klokka
Control vil helst at PX4 følger simulatorens klokke (2026-10-19). Ved liten forskjell betyr det lite, men skal simulatoren gå fortere enn sanntid, må PX4 sin klokke også gå fortere.
- Gazebo med vår båt går på 0,99 av sanntid, så sanntid holder der.
- For å kjøre fortere er det enkleste trolig `sim:=fast` på N ganger sanntid og PX4 med `PX4_SIM_SPEED_FACTOR=N`. Da går de like fort, men er ikke låst sammen, så det glir hvis en av dem henger etter. Ikke testet med SIH.
- Ekte lockstep krever at PX4 tar tiden sin fra simulatoren. Det må gjøres i koden til control.

## Svar fra control 2026-10-19
- Gren: skal være `main`, men koden er spredt nå.
- MotorOutput: thrust -100..100 = 0–100 % forover og bakover. `forward_propeller_thrust` er baugthrusteren, positiv skyver baugen mot styrbord.
- `seapath` og `motor_writer`: kan slås av med egen sim-config, men de spør om det er et problem. I SITL er det trolig ikke det: `seapath` finner ingen serieport og publiserer ingenting, og `motor_writer` skriver bare til loggen (200 Hz). Se SeapathData over om `vehicle_*`-topicene.
- SeapathData: posisjon, heading og kurs, gjerne hele meldingen.
- Klokka: se over.
- Hvordan de starter PX4: `make px4_sitl_sih sihsim_quadx` (eller `px4_sitl_default`) i en container.
- Vinklene: radianer, positiv mot babord sett bakfra, ±90°.
- Bakover: -100 % er ca. 60 % av kraften forover.
- Baugthrusteren: positiv mot styrbord (bekreftet), og like sterk begge veier.

## Venter på svar fra control
- At de legger `/fmu/out/motor_output` (publications) og `/fmu/in/seapath_data` (subscriptions) inn i `dds_topics.yaml`. Uten det kommer ingenting fram.
- At de slår på og starter `switch_motor_output` i SITL-bygget de bruker, og hvilken gren hele kjeden skal samles på for SITL.
- At containeren deres kjører med `--net=host` (eller setter `UXRCE_DDS_AG_IP`).
- Om regulatorene leser `seapath_data` eller `vehicle_*`-topicene. Med `sihsim_quadx` kommer `vehicle_*` fra et simulert quadkopter.
- CCommand: semikolonene i filen, enhetene i `desired_course` og `desired_speed`, og om den skal inn over MAVLink eller XRCE-DDS i simulatoren.
