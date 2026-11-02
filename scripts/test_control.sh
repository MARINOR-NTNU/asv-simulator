#!/usr/bin/env bash
# Tester control sin PX4-kode i simulatoren hele veien til motorene, og skriver ✓ eller ✗ per test.
#
#   scripts/test_control.sh                                     # commiten submodulen står på
#   scripts/test_control.sh feature/control/start_modules_init  # en gren hos control (bare lokalt)
#   scripts/test_control.sh --src ~/Flightcontroller-px4        # en egen kopi av koden, også ucommittet
#
# Med --src testes koden i den mappa i stedet for submodulen (via PX4_SRC i docker-compose.yml), så
# control kan teste endringene sine før de pusher. Byggefilene havner i build/ i den mappa.
#
# Starter simulatoren (uten vindu) og PX4 med docker compose, sjekker at modulene til control starter
# av seg selv, og kjører px4_rc_test (virtuell RC: kraft, retning, baug, vinkel, og at motorene
# stopper når RC forsvinner). Til slutt sjekkes CCOMMAND: at PX4 tar imot ønsket kurs og fart fra
# ccommand_bridge, og at regulatoren styrer båten etter dem (px4_ccommand_test).
# Submodulen settes tilbake og containerne stoppes til slutt, også ved feil.
# Avslutter med kode 1 hvis noe feiler, så det kan brukes i skript.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SUB=px4/Flightcontroller-px4
REF=""
SRC=""
while (( $# )); do
  case "$1" in
    --src) SRC="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) REF="$1"; shift ;;
  esac
done
if [[ -n "$SRC" && -n "$REF" ]]; then
  echo "Bruk enten en gren eller --src, ikke begge."
  exit 1
fi
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

if [[ -n "$SRC" ]]; then
  abs="$(cd "$SRC" 2>/dev/null && pwd)" || { echo "Fant ikke mappa ${SRC}."; exit 1; }
  SRC="$abs"
  if [[ ! -f "$SRC/Makefile" ]]; then
    echo "$SRC ser ikke ut som PX4-koden (ingen Makefile)."
    exit 1
  fi
  export PX4_SRC="$SRC"
  dirty=$(git -C "$SRC" status --porcelain --untracked-files=no 2>/dev/null | wc -l)
  echo "Tester control sin kode i $SRC: $(git -C "$SRC" log -1 --format='%h %ci %an: %s' 2>/dev/null)"
  (( dirty )) && echo "  med $dirty fil(er) som er endret, men ikke committet"
elif [[ -n "$REF" ]]; then
  git -C "$SUB" fetch -q origin
  if ! git -C "$SUB" -c advice.detachedHead=false checkout -q "origin/$REF" 2>/dev/null &&
     ! git -C "$SUB" -c advice.detachedHead=false checkout -q "$REF" 2>/dev/null; then
    echo "Fant ikke $REF i control sitt repo."
    exit 1
  fi
fi
[[ -z "$SRC" ]] && echo "Tester control sin kode: $(git -C "$SUB" log -1 --format='%h %ci %an: %s')"
echo "Starter simulatoren og PX4 (første bygg av PX4 kan ta 30-60 min) ..."
HEADLESS=true CCOMMAND=true docker compose up -d >/dev/null 2>&1

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
# Rett etter oppstart svarer ikke konsollen alltid, og da ville en modul som mangler, sett ut som
# den kjører. Venter til uxrce_dds_client svarer.
for _ in $(seq 15); do
  px4cmd "uxrce_dds_client status" | grep -q "Running" && break
  sleep 2
done
missing=()
for m in rcPublisher switch_motor_output; do
  # En modul som kjører, kan svare med ingenting (rcPublisher), så bare «not running» teller.
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

ros() { docker compose exec -T vrx bash -c "source /root/vrx_ws/install/setup.bash && ros2 run sim_interface $1"; }
ros px4_rc_test || FAILED=1

# CCOMMAND: testen sender ønskede verdier, og imens spørres PX4 om den tar imot msgid 50000.
# mavlink status skriver til PX4-konsollen, ikke tilbake til px4cmd, så svaret leses fra loggen.
echo "CCOMMAND (ønsket kurs og fart fra ccommand_bridge, MAVLink UDP 14580)"
out="$(mktemp)"
ros px4_ccommand_test >"$out" 2>&1 &
pid=$!
rate=""
for _ in $(seq 10); do
  sleep 3
  px4cmd "mavlink status" >/dev/null
  sleep 1
  rate=$(docker compose logs px4 --since 3s 2>&1 | grep -ao "msgid:50000, Rate: [0-9.]*" | grep -o "[0-9.]*$" | tail -1)
  [[ -n "$rate" ]] && awk "BEGIN{exit !($rate >= 5)}" && break
done
if [[ -n "$rate" ]] && awk "BEGIN{exit !($rate >= 5)}"; then
  ok "PX4 tar imot CCOMMAND (${rate} Hz)"
else
  fail "PX4 tar ikke imot CCOMMAND (msgid 50000 mangler i mavlink status etter 30 s). ccommand_bridge sier:"
  docker compose logs vrx 2>&1 | grep -a "ccommand_bridge" | tail -2 | sed 's/^/      /'
fi
wait "$pid" || FAILED=1
grep -v "^$\|CCOMMAND-testene" "$out"
rm -f "$out"

echo
if (( FAILED )); then
  echo "RESULTAT: noe feiler (✗ over)."
else
  echo "RESULTAT: alt bestod."
fi
exit "$FAILED"
