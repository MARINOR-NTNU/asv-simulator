# GUI for simulatoren

`asv_gui.py` er en enkel GUI (Tkinter) som starter simulatoren og viser ROS 2-topics live i Foxglove.
Den kjører på verten og trenger bare Python 3 med Tkinter (`sudo apt install python3-tk`) og Docker.
Alt som har med ROS å gjøre, kjøres i simulator-containeren med `docker exec`.

```bash
python3 gui/asv_gui.py                       # bruker containeren asv_sim og imaget vrx-sim:humble-garden
python3 gui/asv_gui.py --container min_sim   # annen container
```

## Simulator
Velg `sim`, `world`, `control`, `autonomy`, `path` og `headless`, og trykk **Start**. GUI-en
- lager containeren hvis den ikke finnes (`--net=host`, X11, `/dev/dri` og `src/` montert inn, som i README), eller starter den hvis den er stoppet,
- bygger `asv_gazebo` og `sim_interface` med ett løp om gangen (kan slås av med «Bygg pakkene først»),
- kjører `ros2 launch sim_interface sim.launch.py` med valgene, og viser loggen nederst.

**Stopp** sender SIGINT til hele launch-treet og rydder opp i `gz sim` etterpå.

Har containeren ikke X11 montert (f.eks. en som er startet uten `-v /tmp/.X11-unix:...`), kan
Gazebo-vinduet ikke vises fra den. Da spør GUI-en om den skal lage containeren på nytt med X11, GPU
og `--net=host` (pakkene bygges på nytt), eller starte headless. **Lag container på nytt** gjør det
samme for hånd. Testet 2026-10-26 under Wayland (XWayland på `:0`): en container med
`/tmp/.X11-unix` og `/dev/dri` får maskinvare-OpenGL (`glxinfo -B`: radeonsi, direct rendering).

## Foxglove
1. Trykk **Oppdater** for å hente topicene (`ros2 topic list -t` i containeren).
2. Velg topicene du vil se (Ctrl/Shift-klikk, eller filter og **Velg alle**).
3. Trykk **Vis valgte i Foxglove**. Det starter `foxglove_bridge` i containeren på port 8765 med bare de valgte topicene (`topic_whitelist`). Ny utvalg starter bridgen på nytt.
4. Trykk **Åpne Foxglove**. Den åpner Foxglove-appen hvis den er installert, ellers `app.foxglove.dev` i nettleseren (krever gratis konto), koblet til `ws://localhost:8765`.

GUI-en lagrer også `gui/foxglove_layout.json` med ett panel per valgt topic: plot for `Float64` og lignende, bilde for kamera, 3D for punktsky og lidar, kart for GPS og rå meldinger for resten. Last den inn i Foxglove med *Layout → Import from file*.

GUI-en sjekker hvert 3. sekund om bridgen kjører, og viser det under Foxglove. Kjører bridgen
allerede (f.eks. etter at GUI-en er startet på nytt), settes videresendingen opp av seg selv.

Får Foxglove kontakt, men ingen panel viser noe: Foxglove starter med en tom layout. Importer
`gui/foxglove_layout.json`, eller legg til et panel og velg topicen selv. Tidene er simulatortid
(`use_sim_time`), så Foxglove viser datoer i 1970.

Kjører containeren uten `--net=host` (f.eks. vanlig bridge-nettverk), videresender GUI-en `localhost:8765` til containerens IP så lenge den er åpen. Nettleseren tillater bare `ws://` mot `localhost` fra app.foxglove.dev, så adressen er alltid `ws://localhost:8765`.

## Filer i containeren
| Fil | Innhold |
|---|---|
| `/tmp/gui_sim.log`, `/tmp/gui_sim.pid` | logg og prosessgruppe for `sim.launch.py` |
| `/tmp/gui_foxglove.log`, `/tmp/gui_foxglove.pid` | logg og prosessgruppe for `foxglove_bridge` |
| `/tmp/gui_foxglove.yaml` | parameterne til `foxglove_bridge` (port og `topic_whitelist`) |

`foxglove_bridge` er med i imaget fra Dockerfile. Mangler den, må imaget bygges på nytt.
