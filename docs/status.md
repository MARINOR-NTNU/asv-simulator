# Status

Sist oppdatert 2026-10-19. PX4-koblingen har sin egen side: [px4.md](px4.md).

## Simulatoren
- Gruppen har valgt å fortsette i VRX (2026-10-12). `config/unity.yaml` er en mal med plassholdere og er ikke testet.
- Imaget `vrx-sim:humble-garden` er bygget, og alle colcon-pakkene fullførte. Det inneholder også Micro XRCE-DDS Agent og `px4_msgs`.
- Testet headless og med Gazebo-vindu via X11. Alle sensorer publiserer, og båten beveger seg når den får thrust.
- `sim_interface` er testet mot VRX med WAM-V (2026-10-12): regulatoren i `stub_controller` holder ønsket heading, timeout setter thrust til 0, og thrust begrenses til 2353 N.
- `sim.launch.py` er testet headless 2026-10-19 med `control:=px4`, `control:=stub autonomy:=fake` (holder heading og fart) og `sim:=vrx` (lidar, kamera, IMU og heading kommer fram).
- Real-time factor (headless, med `--device /dev/dri`): 0,99 med vår båt og 0,71 med WAM-V.

## 2D-simulator
- Partneren lager en egen 2D-simulator (ikke pushet ennå). Den første 2D-simulatoren (`asv_fastsim`) ble fjernet 2026-10-26 og finnes i git-historikken (commit `ce24d1e`).

## Verdenen
- Bølgene rettet 2026-10-26: oppdriften er delt i 8 bokser, så båten ruller og stamper med bølgene (±5° i 0,3 m bølger med 3 s periode, mot 0° før). Vannflaten i `open_water` har 1 m mellom punktene rundt båten, og bølgene i bildet og i fysikken er de samme. Før så båten ut som den gikk gjennom bølgene. Dypgangen i stille vann er uendret.
- Fra 2026-10-26 kan sensorstøy (`sensor_noise`), vind (`wind_speed`, `wind_direction`, `wind_gust`) og treghet i motorene (`thrust_time_constant`) slås på for å teste regulatorer mer realistisk. Modellen og `open_water` lages fra xacro ved oppstart med disse valgene. Testet i Gazebo. Strøm (`current_speed`, `current_direction`) kom samme dag, med egen motstandsplugin (`asv_hydrodynamics`, VRX sin SimpleHydrodynamics der motstanden regnes ut fra farten gjennom vannet). Uten strøm er den lik VRX sin.
- Fra 2026-10-26 er standard `open_water`: åpent hav (6 × 6 km) uten land, med bølger, i `asv_gazebo/worlds/open_water.sdf.xacro`. GPS-origo er startstedet fra `sydney_regatta`, så GPS, kompasset til PX4 og banene med fast origin er uendret. Testet med slalåmløypa og `path_slalom` (6 av 7 punkter på 75 s). `world:=sydney_regatta` virker fortsatt.
- Fra 2026-10-26 ligger testoppsett i scenariofiler (`asv_gazebo/scenarios/*.yaml`) med én funksjon per type ting i `asv_gazebo/scenario.py`. `slalom.launch.py` er erstattet av `scenario.launch.py` og `sim.launch.py scenario:=slalom`. Testet i begge verdenene. Neste type er dokk, når docking skal testes.

## Vår egen båt (`asv_gazebo`)
- Testet i VRX 2026-10-12: den flyter på riktig høyde, holder kursen rett frem ved alle hastigheter, er symmetrisk mot babord og styrbord, og følger en bane med `sim:=vrx_asv`.
- Bekreftet 2026-10-19: lengde ca. 150 cm, bredde ca. 53 cm (L/B ≈ 2,8), vekt ca. 45 kg, lavt tyngdepunkt, baugthruster i tunnel for sideveis manøvrering i lav fart, og to akterthrustere som kan dreies. Modellen stemmer med dette.
- Bekreftet av control 2026-10-19: akterthrusterne dreier ±90°, og bakover gir de ca. 60 % av kraften forover (i modellen: -30 N).
- Anslag som må erstattes med ekte tall: tyngdepunkt, treghetsmoment (regnet som en massiv boks), maks thrust (50 N akter, 25 N baug), hvor fort akterthrusterne dreier (2 rad/s), og motstanden i vannet (regnet ut fra skrogformen, ikke målt).
- Medsvingende vannmasse (`xDotU`, `yDotV`, `nDotR`) er satt til 0, så båten reagerer raskere sidelengs og i dreiing enn den virkelige vil gjøre. Det betyr mest for DP.
- Siden 2026-10-26 er modellen skrevet i xacro (`asv_gazebo/models/asv/model.sdf.xacro`), med alle tallene i `xacro/parameters.xacro`. Den genererte `model.sdf` er sjekket lik den gamle, og båten holder heading og fart i Gazebo som før.
- Det finnes ingen CAD-modell ennå. Stabilitets- og hydrodynamikkanalyse er planlagt, og tallene derfra skal inn i modellen.

## Grensesnittet mot control og autonomy
- Avtalt med control 2026-10-12: én `std_msgs/Float64` per tall på `/control/thruster/{left,right,bow}/thrust` (newton) og `/control/thruster/{left,right}/angle` (radianer), fortegn som i README, og timeout på 0,5 s per motor. Ikke endre dette uten å avtale det med control.
- Control sin kode kjører i PX4, så den kobles til via uXRCE-DDS. Det er klart på vår side, men ikke testet mot ekte PX4. Se [px4.md](px4.md).
- Svar fra control 2026-10-19: MotorOutput-thrust er -100..100 %, og positiv baugthrust skyver baugen mot styrbord. Broen regner om til newton og snur fortegnet på baugen, så kontrakten er uendret. Vinklene (radianer, positiv mot babord, ±90°) er de samme som i kontrakten.
- Fra 2026-10-20 kjøres control sin PX4 som SITL fra vårt repo: submodule i `px4/Flightcontroller-px4`, eget image (`Dockerfile.px4`) og `docker compose up` for begge. Testet: PX4 kobler seg til agenten og 69 `/fmu`-topics kommer fram. Fra 2026-10-26 starter PX4 med `none_iris` og får sensordata og simuleringsklokke fra `px4_hil_bridge` over MAVLink (testet med Gazebo og 2D-simulatoren). MotorOutput og SeapathData går ikke ennå, fordi grenen til control ikke kompilerer (`MotorOutput.msg` mangler). Se [px4.md](px4.md). Før det virker mot simulatoren, må `switch_motor_output` slås på i SITL, topicene legges i `dds_topics.yaml`, og containeren deres kjøre med `--net=host` (se [px4.md](px4.md)). Det de ikke har svart på ennå, står i [px4.md](px4.md).
- Autonomy skriver en ROS 2-node i C++ (radianer, bøyer i breddegrad og lengdegrad) som gir ønsket heading og fart. Den skal erstatte `fake_heading` og `waypoint_follower`. Simulatoren publiserer ikke bøyeposisjoner ennå.
- Regulering er control sin oppgave, ikke simulatoren sin. `stub_controller` (med fartsregulering fra `speed_node`) og `waypoint_follower` er bare testverktøy til control og autonomy er koblet på, så de skal ikke videreutvikles mer enn testene trenger.

## Neste steg
1. Full test med MotorOutput når control starter `switch_motor_output` i SITL og bestemmer hva den gjør uten RC (se «Venter på svar fra control» i [px4.md](px4.md)). SeapathData inn til PX4 virker, og hele veien fra PX4 til motorene i Gazebo er testet med virtuell RC (2026-10-26). Gjenstår hos control: starte modulene i SITL, og regne om RC-verdiene til -100..100 %.
2. Bro fra autonomy til `CCommand`, når autonomy-noden og mottakeren hos control finnes (se [px4.md](px4.md)).
3. Publiser bøyeposisjoner fra simulatoren (breddegrad og lengdegrad), når autonomy har sagt hvilket topic og hvilken meldingstype noden deres leser.
4. Sett inn ekte tall for båten når CAD-modell, motorvalg og analyse finnes.
5. Legg lidar og kamera på vår egen båt.
