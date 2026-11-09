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

ros2 run plotjuggler plotjuggler --nosplash --layout "$LAYOUT" --start_streamer "ROS2 Topic Subscriber" &
PJ=$!

# Dialogen oppdaterer topic-lista hvert sekund. Prøver igjen til den er borte.
# Enter sendes bare når dialogen er det aktive vinduet. Havner Enter i hovedvinduet, trykker den
# Stop, og da stopper plottingen rett etter at den startet (f.eks. hvis noen trykket OK selv først).
xdotool search --sync --name "$TITLE" >/dev/null
for _ in $(seq 20); do
  sleep 4
  w=$(xdotool search --name "$TITLE" | head -1)
  [[ -z "$w" ]] && break
  xdotool windowactivate --sync "$w" 2>/dev/null
  [[ "$(xdotool getactivewindow)" == "$w" ]] && xdotool key Return
done
wait $PJ
