#!/bin/bash
# Setter real-time factor i Gazebo når verdenen er startet, så simulatoren kan gå fortere (eller
# saktere) enn sanntid i samme kjøring. Bruker /world/<verden>/set_physics (UserCommands-pluginet,
# som finnes i open_water og sydney_regatta). Steglengden er den samme som i verdensfilene (4 ms),
# så fysikken er uendret. Bare farten den kjøres med endres.
# 0 virker ikke (Gazebo ignorerer det og går i sanntid). Over ca. 5 holder ikke ROS-nodene følge.
# Bruk: set_rtf.sh <verden> <rtf>
set -u
WORLD="$1"
RTF="$2"
STEP=0.004
SERVICE="/world/$WORLD/set_physics"

echo "[set_rtf] Venter på $SERVICE ..."
until gz service -l 2>/dev/null | grep -qx "$SERVICE"; do sleep 1; done

for _ in $(seq 10); do
  if gz service -s "$SERVICE" --reqtype gz.msgs.Physics --reptype gz.msgs.Boolean --timeout 2000 \
       --req "max_step_size: $STEP, real_time_factor: $RTF" 2>/dev/null | grep -q 'data: true'; then
    echo "[set_rtf] Real-time factor satt til $RTF i $WORLD."
    exit 0
  fi
  sleep 1
done
echo "[set_rtf] Fikk ikke satt real-time factor i $WORLD."
exit 1
