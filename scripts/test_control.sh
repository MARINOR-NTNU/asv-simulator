#!/usr/bin/env bash
# Tester control sin PX4-kode i simulatoren hele veien til motorene, og skriver ✓ eller ✗ per test.
#
#   scripts/test_control.sh                                     # commiten submodulen står på
#   scripts/test_control.sh feature/control/start_modules_init  # en gren hos control (bare lokalt)
#
# Starter simulatoren (uten vindu) og PX4 med docker compose, sjekker at modulene til control starter
# av seg selv, og kjører px4_rc_test (virtuell RC: kraft, retning, baug, vinkel, og at motorene
# stopper når RC forsvinner). Submodulen settes tilbake og containerne stoppes til slutt, også ved feil.
# Avslutter med kode 1 hvis noe feiler, så det kan brukes i skript.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SUB=px4/Flightcontroller-px4
REF="${1:-}"
TARGET="${PX4_TARGET:-px4_sitl_proteus}"
ORIG="$(git -C "$SUB" rev-parse HEAD)"
FAILED=0

cleanup() {
  docker compose down >/dev/null 2>&1
  if [[ -n "$REF" ]]; then
    git -C "$SUB" checkout -q "$ORIG" && echo "Submodulen er satt tilbake til ${ORIG:0:10}."
  fi
}
trap cleanup EXIT

ok() { echo "  ✓ $*"; }
fail() { echo "  ✗ $*"; FAILED=1; }

# Maskinen tåler ikke to simulatorer samtidig.
if [[ -n "$(docker ps -q)" ]]; then
  echo "Andre containere kjører (docker ps). Stopp dem først."
  trap - EXIT
  exit 1
fi

if [[ -n "$REF" ]]; then
  git -C "$SUB" fetch -q origin
  if ! git -C "$SUB" -c advice.detachedHead=false checkout -q "origin/$REF" 2>/dev/null &&
     ! git -C "$SUB" -c advice.detachedHead=false checkout -q "$REF" 2>/dev/null; then
    echo "Fant ikke $REF i control sitt repo."
    exit 1
  fi
fi
echo "Tester control sin kode: $(git -C "$SUB" log -1 --format='%h %ci %an: %s')"
echo "Starter simulatoren og PX4 (første bygg av PX4 kan ta 30-60 min) ..."
HEADLESS=true docker compose up -d >/dev/null 2>&1

# Venter på at PX4 er bygget og koblet til agenten, eller på at bygget feiler.
echo "PX4"
deadline=$((SECONDS + 5400))
while true; do
  logs="$(docker compose logs px4 2>&1)"
  if grep -aq "synchronized with time offset" <<<"$logs"; then
    ok "PX4 bygger, starter og kobler seg til simulatoren"
    break
  fi
  if grep -aqE "FAILED:|Error [0-9]+$|FEIL:" <<<"$logs" || ! docker compose ps px4 | grep -q Up; then
    fail "PX4 bygger eller starter ikke. Siste linjer:"
    grep -aE "error|FAILED|FEIL|fatal" <<<"$logs" | sed 's/\x1b\[[0-9;]*m//g' | tail -5 | sed 's/^/      /'
    exit 1
  fi
  if (( SECONDS > deadline )); then
    fail "PX4 startet ikke innen 90 min"
    exit 1
  fi
  sleep 10
done

# Modulene skal starte av seg selv i SITL. Hvis ikke, startes de her, så resten kan testes.
px4cmd() { docker compose exec -T px4 bash -c "cd build/$TARGET/rootfs && ../bin/px4-$1" 2>&1; }
missing=()
for m in rcPublisher switch_motor_output; do
  if px4cmd "$m status" | grep -q "not running"; then
    missing+=("$m")
    px4cmd "$m start" >/dev/null
  fi
done
if (( ${#missing[@]} )); then
  fail "Modulene starter ikke av seg selv i SITL: ${missing[*]} (startet for hånd for resten av testene)"
else
  ok "rcPublisher og switch_motor_output starter av seg selv"
fi

docker compose exec -T vrx bash -c 'source /root/vrx_ws/install/setup.bash && ros2 run sim_interface px4_rc_test' \
  || FAILED=1

echo
if (( FAILED )); then
  echo "RESULTAT: noe feiler (✗ over)."
else
  echo "RESULTAT: alt bestod."
fi
exit "$FAILED"
