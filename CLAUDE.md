# CLAUDE.md

Felles VRX-simulator i Docker for ASV-prosjektet. Brukes av control (PX4) og autonomy.

- Bruk og oppsett: [README.md](README.md)
- Status og neste steg: [docs/status.md](docs/status.md)
- PX4-koblingen og spørsmål til control: [docs/px4.md](docs/px4.md)
- Fallgruver: [docs/fallgruver.md](docs/fallgruver.md)

Hold `docs/status.md` og `docs/px4.md` oppdatert når noe endres eller testes.

## Bygg
- Bygg med ett løp om gangen: `MAKEFLAGS="-j1" colcon build --merge-install --executor sequential --parallel-workers 1`. Maskinen har lite minne og har frosset ved parallelle bygg.
- Bruk alltid `--merge-install`.
- Bygg PX4 med `make px4_sitl_proteus j=1` i PX4-containeren (`docker compose up` gjør det).
- Bygg egne pakker i containeren: `colcon build --merge-install --packages-select asv_hydrodynamics asv_gazebo sim_interface`. Bygget forsvinner når containeren stoppes (`--rm`).
- Filer som lages i containeren, eies av root. Gi dem tilbake til brukeren på verten.

## Regler
- Dokumentasjon, kommentarer og commit-meldinger skrives på norsk.
- Ikke endre kontrakten mot control (`/control/thruster/...`, enheter, fortegn og timeout) uten at det er avtalt med control.
- Ikke endre koden i control sin PX4-fork (submodulen `px4/Flightcontroller-px4`). Det som må endres der, blir en forespørsel til control. Å sjekke ut en annen commit lokalt for å teste er greit, men submodulen skal peke på grenen deres når det committes.
- Ikke bruk `/wamv/...`-topics direkte i nodene. Alt som er spesifikt for én simulator, ligger i `src/sim_interface/config/<sim>.yaml`.
- Alle noder kjører med `use_sim_time:=true`. ROS-siden bruker ENU/FLU, PX4-siden NED/FRD.
- Båtmodellen redigeres i `asv_gazebo/models/asv/model.sdf.xacro` og `xacro/` (tallene i `xacro/parameters.xacro`, komponentene om bord i `components.yaml`). Totalvekten er fast (`total_mass`, 45 kg), og skroget får det som er igjen. `model.sdf` lages når `asv_gazebo` bygges, og Gazebo leser den installerte fila.
- Regulering er control sin oppgave. `stub_controller` og `waypoint_follower` er bare testverktøy.
