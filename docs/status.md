# Status

Sist oppdatert 2026-10-19. PX4-koblingen har sin egen side: [px4.md](px4.md).

## Simulatoren
- Gruppen har valgt å fortsette i VRX (2026-10-12). `config/unity.yaml` er en mal med plassholdere og er ikke testet.
- Imaget `vrx-sim:humble-garden` er bygget, og alle colcon-pakkene fullførte. Det inneholder også Micro XRCE-DDS Agent og `px4_msgs`.
- Testet headless og med Gazebo-vindu via X11. Alle sensorer publiserer, og båten beveger seg når den får thrust.
- `sim_interface` er testet mot VRX med WAM-V (2026-10-12): regulatoren i `stub_controller` holder ønsket heading, timeout setter thrust til 0, og thrust begrenses til 2353 N.
- `sim.launch.py` er testet headless 2026-10-19 med `control:=px4`, `control:=stub autonomy:=fake` (holder heading og fart) og `sim:=vrx` (lidar, kamera, IMU og heading kommer fram).
- Real-time factor (headless, med `--device /dev/dri`): 0,99 med vår båt og 0,71 med WAM-V.

## Vår egen båt (`asv_gazebo`)
- Testet i VRX 2026-10-12: den flyter på riktig høyde, holder kursen rett frem ved alle hastigheter, er symmetrisk mot babord og styrbord, og følger en bane med `sim:=vrx_asv`.
- Bekreftet 2026-10-19: lengde ca. 150 cm, bredde ca. 53 cm (L/B ≈ 2,8), vekt ca. 45 kg, lavt tyngdepunkt, baugthruster i tunnel for sideveis manøvrering i lav fart, og to akterthrustere som kan dreies. Modellen stemmer med dette.
- Anslag som må erstattes med ekte tall: tyngdepunkt, treghetsmoment (regnet som en massiv boks), maks thrust (50 N akter, 25 N baug), hvor langt og fort akterthrusterne dreier (±90°, 2 rad/s), og motstanden i vannet (regnet ut fra skrogformen, ikke målt).
- Medsvingende vannmasse (`xDotU`, `yDotV`, `nDotR`) er satt til 0, så båten reagerer raskere sidelengs og i dreiing enn den virkelige vil gjøre. Det betyr mest for DP.
- Det finnes ingen CAD-modell ennå. Stabilitets- og hydrodynamikkanalyse er planlagt, og tallene derfra skal inn i modellen.

## Grensesnittet mot control og autonomy
- Avtalt med control 2026-10-12: én `std_msgs/Float64` per tall på `/control/thruster/{left,right,bow}/thrust` (newton) og `/control/thruster/{left,right}/angle` (radianer), fortegn som i README, og timeout på 0,5 s per motor. Ikke endre dette uten å avtale det med control.
- Control sin kode kjører i PX4, så den kobles til via uXRCE-DDS. Det er klart på vår side, men ikke testet mot ekte PX4. Se [px4.md](px4.md).
- Autonomy skriver en ROS 2-node i C++ (radianer, bøyer i breddegrad og lengdegrad) som gir ønsket heading og fart. Den skal erstatte `fake_heading` og `waypoint_follower`. Simulatoren publiserer ikke bøyeposisjoner ennå.
- Regulering er control sin oppgave, ikke simulatoren sin. `stub_controller` (med fartsregulering fra `speed_node`) og `waypoint_follower` er bare testverktøy til control og autonomy er koblet på, så de skal ikke videreutvikles mer enn testene trenger.

## Neste steg
1. Test mot ekte PX4 når control har svart (se «Venter på svar fra control» i [px4.md](px4.md)).
2. Bro fra autonomy til `CCommand`, når autonomy-noden og mottakeren hos control finnes (se [px4.md](px4.md)).
3. Publiser bøyeposisjoner fra simulatoren (breddegrad og lengdegrad), når autonomy har sagt hvilket topic og hvilken meldingstype noden deres leser.
4. Sett inn ekte tall for båten når CAD-modell, motorvalg og analyse finnes.
5. Legg lidar og kamera på vår egen båt.
