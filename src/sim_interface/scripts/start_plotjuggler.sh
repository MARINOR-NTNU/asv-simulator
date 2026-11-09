#!/bin/bash
# Starter PlotJuggler med layouten og trykker OK i topic-dialogen, så plottene går uten at noen må klikke.
# ROS 2-abonnementet i PlotJuggler viser alltid dialogen, og det finnes ikke noe valg for å hoppe over den.
# Topicene fra layouten krysses av bare hvis de finnes når dialogen er åpen, så vi venter på simulatoren først.
# Bruk: start_plotjuggler.sh <layout.xml>
set -u
LAYOUT="$1"
TITLE="Select ROS messages"

echo "Venter på /autonomy/position før PlotJuggler startes ..."
until ros2 topic list --no-daemon --spin-time 2 2>/dev/null | grep -qx /autonomy/position; do sleep 2; done

# PlotJuggler laster layouten og overskriver så bufferet med sin egen innstilling (standard 5 s).
# Skriver derfor streaming_buffer_size fra layouten inn i innstillingene først.
BUF=$(grep -oP 'streaming_buffer_size value="\K[0-9]+' "$LAYOUT")
if [[ -n "$BUF" ]]; then
  INI="$HOME/.config/PlotJuggler/io.plotjuggler.PlotJuggler.ini"
  mkdir -p "$(dirname "$INI")"
  if grep -q '^MainWindow.streamingBufferValue=' "$INI" 2>/dev/null; then
    sed -i "s/^MainWindow.streamingBufferValue=.*/MainWindow.streamingBufferValue=$BUF/" "$INI"
  elif grep -q '^\[General\]' "$INI" 2>/dev/null; then
    sed -i "/^\[General\]/a MainWindow.streamingBufferValue=$BUF" "$INI"
  else
    printf '[General]\nMainWindow.streamingBufferValue=%s\n' "$BUF" >> "$INI"
  fi
fi

# Layouten husker strømmen (previouslyLoaded_Streamer), og da spør PlotJuggler «Start Streaming?» og
# starter ROS 2-abonnementet selv. Ikke bruk --start_streamer i tillegg: det virker som et trykk på
# Start/Stop for pluginen som er valgt, så strømmen stopper rett etter at den har startet.
grep -q 'previouslyLoaded_Streamer' "$LAYOUT" || \
  echo "ADVARSEL: $LAYOUT mangler previouslyLoaded_Streamer, så plottene starter ikke. Lagre layouten mens strømmen går."

ros2 run plotjuggler plotjuggler --nosplash --layout "$LAYOUT" &
PJ=$!

# Finner et synlig vindu fra PlotJuggler med nøyaktig denne tittelen. Sjekker tittelen her fordi
# xdotool i imaget ikke finner noe når --class og --name kombineres med --all. --onlyvisible fordi
# lukkede dialoger kan finnes skjult, og windowactivate --sync bruker ca. 15 s på å gi opp på dem.
find_window() {
  local w
  for w in $(xdotool search --onlyvisible --class plotjuggler 2>/dev/null); do
    if [[ "$(xdotool getwindowname "$w" 2>/dev/null)" == "$1" ]]; then
      echo "$w"
      return
    fi
  done
}

# Enter sendes bare når vinduet er det aktive. Havner Enter i hovedvinduet, trykker den Stop.
press_enter() {
  xdotool windowactivate --sync "$1" 2>/dev/null
  [[ "$(xdotool getactivewindow 2>/dev/null)" == "$1" ]] && xdotool key Return
}

# Først kommer «Start Streaming?», så topic-dialogen. Dialogen oppdaterer topic-lista hvert sekund,
# så den får stå i noen sekunder før OK. Prøver igjen til den er borte.
open=0
for _ in $(seq 120); do
  sleep 1
  w=$(find_window "Start Streaming?")
  [[ -n "$w" ]] && press_enter "$w"
  w=$(find_window "$TITLE")
  if [[ -n "$w" ]]; then
    open=$((open + 1))
    (( open >= 3 )) && press_enter "$w"
  elif (( open > 0 )); then
    break
  fi
done
wait $PJ
