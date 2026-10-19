#!/usr/bin/env bash
# Kopierer PX4-meldingene fra control sin fork inn i px4_msgs/.
# Leser bare fra git-historikken i forken (git show), så arbeidskopien og grenene der endres ikke.
# Kjør `git -C ~/Flightcontroller-px4 fetch` først hvis du vil ha nyeste versjon av grenene.
set -euo pipefail

PX4_DIR="${PX4_DIR:-$HOME/Flightcontroller-px4}"
BASE="${BASE:-origin/main}"
# Egne meldinger fra control som ikke er på main ennå. Disse overstyrer filer med samme navn fra BASE.
EXTRA=(
  "origin/feature/control/motor_output_and_switch:msg/MotorOutput.msg"
  "origin/feature/control/motor_output_and_switch:msg/RcControlMode.msg"
  "origin/feature/control/seapathDriver:msg/SeapathData.msg"
)

OUT="$(cd "$(dirname "$0")/.." && pwd)/px4_msgs"
px4() { git -C "$PX4_DIR" "$@"; }

# Fjerner bare de genererte mappene, så meldinger som er slettet i forken også forsvinner her.
rm -rf "$OUT/msg" "$OUT/srv"
mkdir -p "$OUT/msg" "$OUT/srv"

# px4_msgs må ha alle meldingene i én flat mappe, også de i msg/versioned/.
for f in $(px4 ls-tree --name-only "$BASE" msg/ msg/versioned/ | grep '\.msg$'); do
  px4 show "$BASE:$f" > "$OUT/msg/$(basename "$f")"
done
for f in $(px4 ls-tree --name-only "$BASE" srv/ | grep '\.srv$'); do
  px4 show "$BASE:$f" > "$OUT/srv/$(basename "$f")"
done
for e in "${EXTRA[@]}"; do
  px4 show "$e" > "$OUT/msg/$(basename "${e#*:}")"
done

{
  echo "# Generert av scripts/sync_px4_msgs.sh. Ikke rediger meldingene for hånd."
  echo "fork: $(px4 remote get-url origin)"
  echo "$BASE: $(px4 rev-parse --short "$BASE")"
  for e in "${EXTRA[@]}"; do echo "${e%%:*}: $(px4 rev-parse --short "${e%%:*}") (${e#*:})"; done
} > "$OUT/SOURCE.txt"

echo "$(ls "$OUT/msg" | wc -l) msg og $(ls "$OUT/srv" | wc -l) srv kopiert til $OUT"
