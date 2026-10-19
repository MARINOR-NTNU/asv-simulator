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
- Den raske 2D-simulatoren (`sim:=fast`) går fint med hele ROS-kjeden opp til `real_time_factor:=20`. Over det henger nodene etter, og regulatoren blir ustabil uten noen feilmelding. Sjekk at resultatene er like ved en lavere hastighet før du stoler på en ny, høyere.
- Ikke start `demo.launch.py` eller `path.launch.py` ved siden av `control:=px4`. Da styrer både `stub_controller` og PX4 motorene, uten noen feilmelding.

## Båtmodellen
- Motstanden i vannet angriper i `hydro_link`. Flyttes det punktet foran tyngdepunktet, blir båten retningsustabil og spinner rundt i høy fart.
- `linear_drag` og `angular_drag` i oppdriftsmodulen er lik i alle retninger og skal stå på 0. All motstand ligger i `SimpleHydrodynamics`.
- Et ledd som kjøres helt i endestopp, låser seg. Derfor er leddgrensen for thrusterne (±1,75) videre enn det `thruster_adapter` tillater (±1,5708).
- En modell som er fjernet fra en kjørende simulator, lar seg ikke sette inn igjen med samme navn. Start simulatoren på nytt.

## Koordinater og tid
- Ved omregning fra GPS til meter må cos(breddegrad) regnes med en fast referansebredde. Ellers gir bevegelse nord/sør flere meter falsk forflytning øst/vest.
- ROS og VRX bruker ENU/FLU, PX4 og Seapath bruker NED/FRD. Omregningen ligger i `sim_interface/frames.py`.
- Meldinger til PX4 sendes med `timestamp = 0`. Da setter PX4 sin egen tid når meldingen kommer fram. Andre verdier regnes om med agentens klokke (ekte tid), og sim-tid ville blitt feil.
- PX4 publiserer best effort, så abonnementer på `/fmu/out/...` må bruke `qos_profile_sensor_data`.
