#!/usr/bin/env bash
# Kopierer PX4-meldingene simulatoren bruker fra control sin fork inn i px4_msgs/.
# Leser bare fra git-historikken i forken (git show), så arbeidskopien og grenene der endres ikke.
# Leser fra submodulen px4/Flightcontroller-px4. Kjør `git -C px4/Flightcontroller-px4 fetch` først hvis du vil ha
# nyeste versjon av grenene.
# PX4_BRANCH=<gren> henter alle meldingene fra den grenen i stedet, f.eks. PX4_BRANCH=main.
set -euo pipefail

PX4_DIR="${PX4_DIR:-$(cd "$(dirname "$0")/.." && pwd)/px4/Flightcontroller-px4}"
# Bare meldingene som går mellom PX4 og simulatoren, som gren:fil. Trengs en til, legg den til her.
MSGS=(
  "origin/feature/control/motor_output_and_switch:msg/MotorOutput.msg"
  "origin/feature/control/seapathDriver:msg/SeapathData.msg"
)

OUT="$(cd "$(dirname "$0")/.." && pwd)/px4_msgs"
px4() { git -C "$PX4_DIR" "$@"; }

if [[ -n "${PX4_BRANCH:-}" ]]; then
  MSGS=("${MSGS[@]/#*:/origin/$PX4_BRANCH:}")
fi

# Sjekker at alle meldingene finnes før noe slettes.
for e in "${MSGS[@]}"; do
  px4 cat-file -e "$e" 2>/dev/null || { echo "Finner ikke $e i $PX4_DIR" >&2; exit 1; }
done

# Fjerner bare de genererte mappene, så meldinger som er tatt ut av lista også forsvinner her.
rm -rf "$OUT/msg" "$OUT/srv"
mkdir -p "$OUT/msg"

for e in "${MSGS[@]}"; do
  px4 show "$e" > "$OUT/msg/$(basename "${e#*:}")"
done

{
  echo "# Generert av scripts/sync_px4_msgs.sh. Ikke rediger meldingene for hånd."
  echo "fork: $(px4 remote get-url origin)"
  for e in "${MSGS[@]}"; do echo "${e%%:*}: $(px4 rev-parse --short "${e%%:*}") (${e#*:})"; done
} > "$OUT/SOURCE.txt"

echo "$(ls "$OUT/msg" | wc -l) meldinger kopiert til $OUT"
