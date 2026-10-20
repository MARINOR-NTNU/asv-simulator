# Status

Sist oppdatert 2026-10-19. PX4-koblingen har sin egen side: [px4.md](px4.md).

## Simulatoren
- Gruppen har valgt å fortsette i VRX (2026-10-12). `config/unity.yaml` er en mal med plassholdere og er ikke testet.
- Imaget `vrx-sim:humble-garden` er bygget, og alle colcon-pakkene fullførte. Det inneholder også Micro XRCE-DDS Agent og `px4_msgs`.
- Testet headless og med Gazebo-vindu via X11. Alle sensorer publiserer, og båten beveger seg når den får thrust.
- `sim_interface` er testet mot VRX med WAM-V (2026-10-12): regulatoren i `stub_controller` holder ønsket heading, timeout setter thrust til 0, og thrust begrenses til 2353 N.
- `sim.launch.py` er testet headless 2026-10-19 med `control:=px4`, `control:=stub autonomy:=fake` (holder heading og fart) og `sim:=vrx` (lidar, kamera, IMU og heading kommer fram).
- Real-time factor (headless, med `--device /dev/dri`): 0,99 med vår båt og 0,71 med WAM-V.

## Rask 2D-simulator (`asv_fastsim`)
- Laget 2026-10-19 for tusenvis av tester for autonomy, der 3D og grafikk ikke er viktig. Startes med `sim:=fast`.
- Sammenlignet med Gazebo (vår båt) med samme testsekvens: fart ved 2 × 10, 30 og 50 N, akselerasjon, oppbremsing, dreiehastighet, svingradius, thrustervinkel og baugthruster er innen 1 %, oppbremsing etter 15 s innen 3 %.
- Trygg hastighet med hele ROS-kjeden er 20 ganger sanntid. Ved 46 ganger henger nodene etter, og regulatoren blir ustabil.
- Ikke laget ennå: scenariokjører (situasjoner fra fil eller tilfeldig, resultater til CSV). Venter på hva autonomy vil teste.

## Vår egen båt (`asv_gazebo`)
- Testet i VRX 2026-10-12: den flyter på riktig høyde, holder kursen rett frem ved alle hastigheter, er symmetrisk mot babord og styrbord, og følger en bane med `sim:=vrx_asv`.
- Bekreftet 2026-10-19: lengde ca. 150 cm, bredde ca. 53 cm (L/B ≈ 2,8), vekt ca. 45 kg, lavt tyngdepunkt, baugthruster i tunnel for sideveis manøvrering i lav fart, og to akterthrustere som kan dreies. Modellen stemmer med dette.
- Bekreftet av control 2026-10-19: akterthrusterne dreier ±90°, og bakover gir de ca. 60 % av kraften forover (i modellen: -30 N).
- Anslag som må erstattes med ekte tall: tyngdepunkt, treghetsmoment (regnet som en massiv boks), maks thrust (50 N akter, 25 N baug), hvor fort akterthrusterne dreier (2 rad/s), og motstanden i vannet (regnet ut fra skrogformen, ikke målt).
- Medsvingende vannmasse (`xDotU`, `yDotV`, `nDotR`) er satt til 0, så båten reagerer raskere sidelengs og i dreiing enn den virkelige vil gjøre. Det betyr mest for DP.
- Det finnes ingen CAD-modell ennå. Stabilitets- og hydrodynamikkanalyse er planlagt, og tallene derfra skal inn i modellen.

## Grensesnittet mot control og autonomy
- Avtalt med control 2026-10-12: én `std_msgs/Float64` per tall på `/control/thruster/{left,right,bow}/thrust` (newton) og `/control/thruster/{left,right}/angle` (radianer), fortegn som i README, og timeout på 0,5 s per motor. Ikke endre dette uten å avtale det med control.
- Control sin kode kjører i PX4, så den kobles til via uXRCE-DDS. Det er klart på vår side, men ikke testet mot ekte PX4. Se [px4.md](px4.md).
- Svar fra control 2026-10-19: MotorOutput-thrust er -100..100 %, og positiv baugthrust skyver baugen mot styrbord. Broen regner om til newton og snur fortegnet på baugen, så kontrakten er uendret. Vinklene (radianer, positiv mot babord, ±90°) er de samme som i kontrakten.
- Control vil kjøre PX4 som `px4_sitl_proteus none_iris` i en container (2026-10-20), men det bygget er ikke pushet ennå. Før det virker mot simulatoren, må `switch_motor_output` slås på i SITL, topicene legges i `dds_topics.yaml`, og containeren deres kjøre med `--net=host` (se [px4.md](px4.md)). Det de ikke har svart på ennå, står i [px4.md](px4.md).
- Autonomy skriver en ROS 2-node i C++ (radianer, bøyer i breddegrad og lengdegrad) som gir ønsket heading og fart. Den skal erstatte `fake_heading` og `waypoint_follower`. Simulatoren publiserer ikke bøyeposisjoner ennå.
- Regulering er control sin oppgave, ikke simulatoren sin. `stub_controller` (med fartsregulering fra `speed_node`) og `waypoint_follower` er bare testverktøy til control og autonomy er koblet på, så de skal ikke videreutvikles mer enn testene trenger.

## Neste steg
1. Test mot ekte PX4 når control har svart (se «Venter på svar fra control» i [px4.md](px4.md)).
2. Bro fra autonomy til `CCommand`, når autonomy-noden og mottakeren hos control finnes (se [px4.md](px4.md)).
3. Publiser bøyeposisjoner fra simulatoren (breddegrad og lengdegrad), når autonomy har sagt hvilket topic og hvilken meldingstype noden deres leser.
4. Sett inn ekte tall for båten når CAD-modell, motorvalg og analyse finnes.
5. Legg lidar og kamera på vår egen båt.
6. Scenariokjører for den raske 2D-simulatoren, når autonomy har sagt hva de vil teste, hva en situasjon er, og hva de vil måle.
