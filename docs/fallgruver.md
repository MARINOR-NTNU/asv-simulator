# Ting som er lette å gå i

## Bygg og kjøring
- Bygg med ett løp om gangen (`MAKEFLAGS="-j1"`). Parallell kompilering kan bruke opp minnet og fryse maskinen.
- `ros_gz_bridge` er tung og kan stå i over 10 min uten output. Det er normalt, så ikke avbryt.
- `ros_gz` må bygges fra kilde mot Garden (`GZ_VERSION=garden`). apt-pakken `ros-humble-ros-gz` er for Fortress og gir feil, så den skal ikke installeres.
- Standardbygget av Micro XRCE-DDS Agent v2.4.2 feiler, fordi det laster ned Fast-DDS-grenen `2.12.x`, som ikke finnes lenger. Derfor bygges den med `-DUAGENT_USE_SYSTEM_FASTDDS=ON -DUAGENT_USE_SYSTEM_FASTCDR=ON` mot Fast-DDS fra Humble.
- Uten `--device /dev/dri` tegner Gazebo med CPU-en, og WAM-V går da på bare ca. 6 % av sanntid.
- Sjekk at ingen gamle simulatorer kjører før du starter: `docker ps` og `pgrep -af "gz sim"`.
- Ufarlige advarsler i loggen: `Unable to deserialize sdf::Model` og `GzCard: Cannot anchor item to self`.
- Hvis `ros2 topic echo` feiler med `!rclpy.ok()`, har ros2-daemonen hengt seg. Bruk `--no-daemon`.
- Når Gazebo-vinduet åpnes, kan Ubuntu si at programmet ikke svarer. Trykk «Vent», for «Tving avslutning» avslutter hele simulatoren.
- Ikke start `demo.launch.py` eller `path.launch.py` ved siden av `control:=px4`. Da styrer både `stub_controller` og PX4 motorene, uten noen feilmelding.

## Bølger og vann
- VRX regner oppdriften med flatt vann rundt hvert oppdriftselement, med høyden i midten av elementet. Med én boks går båten bare opp og ned. Derfor er oppdriften et rutenett av bokser (`buoyancy_nx`, `buoyancy_ny` i `parameters.xacro`).
- VRX sin `WaveVisual` sender bølgene til grafikkortet bare én gang, før parametrene på topicen kommer. Uten bølgeparametrene i `<wavefield><wave>` i verdensfila viser bildet VRX sine standardbølger (gain 1, periode 5 s), mens fysikken bruker de riktige.
- VRX sin vannflate (`coast_waves`) har ca. 19 m mellom punktene. For en båt på 1,5 m tegnes bølgene rundt båten helt feil, og den ser ut som den er under vann selv om fysikken er riktig. `open_water` bruker derfor `ocean.obj` med 1 m mellom punktene innenfor ±100 m (`scripts/make_ocean_mesh.py`). Utenfor det er vannet grovere tegnet.
- Vannshaderen finner teksturene sine som `materials/textures/` ved siden av fila vannet ble lest fra, så `asv.launch.py` lenker VRX sine teksturer inn ved siden av den genererte verdenen.
- `wave_gain` i VRX er ikke bølgehøyden. Bruk `wave_height`, som regnes om med VRX sin formel (`asv_gazebo/waves.py`).

## Båtmodellen
- Gazebo tolker horisontal GPS-støy (`navsat/position_sensing/horizontal`) som grader breddegrad og lengdegrad, ikke meter. 0,02 ga hopp på flere km. `sensors.xacro` regner om fra meter.
- VRX sin vindplugin (`USVWind`) regner vindkraften per akse i verden, ikke i båtens akser, så koeffisientene er like for x og y.
- Motstanden i vannet angriper i `hydro_link`. Flyttes det punktet foran tyngdepunktet, blir båten retningsustabil og spinner rundt i høy fart.
- `linear_drag` og `angular_drag` i oppdriftsmodulen er lik i alle retninger og skal stå på 0. All motstand ligger i `SimpleHydrodynamics`.
- Et ledd som kjøres helt i endestopp, låser seg. Derfor er leddgrensen for thrusterne (±1,75) videre enn det `thruster_adapter` tillater (±1,5708).
- En modell som er fjernet fra en kjørende simulator, lar seg ikke sette inn igjen med samme navn. Start simulatoren på nytt.

## Koordinater og tid
- Ved omregning fra GPS til meter må cos(breddegrad) regnes med en fast referansebredde. Ellers gir bevegelse nord/sør flere meter falsk forflytning øst/vest.
- ROS og VRX bruker ENU/FLU, PX4 og Seapath bruker NED/FRD. Omregningen ligger i `sim_interface/frames.py`.
- Meldinger til PX4 sendes med `timestamp = 0`. Da setter PX4 sin egen tid når meldingen kommer fram. Andre verdier regnes om med agentens klokke (ekte tid), og sim-tid ville blitt feil.
- PX4 publiserer best effort, så abonnementer på `/fmu/out/...` må bruke `qos_profile_sensor_data`.

## PX4 i containeren
- `none_iris` (`PX4_SYS_AUTOSTART=10016`) henger ved oppstart til noe kobler seg til TCP 4560. Det gjør `px4_hil_bridge`, som starter med `control:=px4`. Uten den startes aldri `uxrce_dds_client`.
- Med Gazebo skriver PX4 `poll timeout` hvert sekund mens verdenen lastes, fordi det ikke kommer IMU ennå. Det stopper av seg selv.
- `px4_hil_bridge` sender sensordata med simuleringstiden. Startes simulatoren på nytt mens PX4 kjører, går tiden bakover, og da må PX4 også startes på nytt.
- `git clone` henter ikke submodulen. Uten `git submodule update --init px4/Flightcontroller-px4` er `px4/Flightcontroller-px4` tom, og PX4-containeren stopper med en melding om det. En `PX4_SRC`-sti som ikke finnes, gir det samme, fordi Docker da monterer en tom mappe.
- Monter hele repoet i PX4-containeren, ikke bare submodulen. Submodulens `.git` er en fil som peker til `../../.git/modules/`, og PX4 trenger git under bygget.
- Kjør PX4-containeren som brukeren (`--user`), ellers eies `build/` og `.git/modules/` av root.
- På `sitl_proteus` kopierer cmake `custom.xml` inn i `src/modules/mavlink/mavlink/` før MAVLink-submodulen er hentet. Compose henter den før `make`, men har noen bygget uten compose og fått «already exists and is not an empty directory», må `src/modules/mavlink/mavlink/message_definitions/` slettes for hånd før neste forsøk.
- Etter at submodulen er flyttet til en ny commit, bygger PX4 på nytt ved neste `docker compose up`, så det tar lenger tid før PX4 starter.
- PX4 sine egne submoduler hentes av bygget selv. Ikke bruk `git submodule update --recursive`, det henter NuttX og mye annet vi ikke trenger.
- Agenten viser PX4 sine forbindelser som `_CREATED_BY_BARE_DDS_APP_` i ROS 2, ikke som en node.
