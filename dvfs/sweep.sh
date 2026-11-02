#!/usr/bin/env bash
# Sweep one power-management knob and run every benchmark at each setting.
#
#   ./sweep.sh clock    # lock the SM clock: nvidia-smi -lgc f,f
#   ./sweep.sh power    # GPU power limit:   nvidia-smi -pl W
#   ./sweep.sh module   # module power limit (GPU+CPU+mem): nvidia-smi -pl W -sc 1
#   ./sweep.sh none     # no control; just run the benchmarks once (baseline)
#
# Knobs (environment):
#   BENCHES   "bin:intensity ..."  (default below; intensity 1 => memory bound)
#   CLOCKS    explicit SM clocks in MHz      (clock mode; default: every
#             CLOCK_STRIDE-th entry of the supported-clock table)
#   CLOCK_STRIDE  default 8
#   LIMITS    explicit watts                 (power/module; default: min..max
#             in LIMIT_STEP W steps)
#   LIMIT_STEP    default 100
#   DURATION  measured seconds per run       (default 15)
#   WARMUP    warm-up seconds per run        (default 3)
#   COOLDOWN  idle seconds between runs      (default 3)
#   TRACE=1   also keep the per-sample NVML trace of every run
#   GPU       nvidia-smi / CUDA index        (default 0)
#
# Output: results/<mode>_<host>_<timestamp>.csv (+ traces/ if TRACE=1).
# Every setting is restored on exit, including on Ctrl-C.

set -euo pipefail
MODE=${1:-clock}
HERE=$(cd "$(dirname "$0")" && pwd)
GPU=${GPU:-0}
DURATION=${DURATION:-15}
WARMUP=${WARMUP:-3}
COOLDOWN=${COOLDOWN:-3}
CLOCK_STRIDE=${CLOCK_STRIDE:-8}
LIMIT_STEP=${LIMIT_STEP:-100}
BENCHES=${BENCHES:-"vecadd_mem:1 vecadd_fp32:2 vecadd_fp32:16 vecadd_fp32:512 vecadd_fp16:512 vecadd_int32:512 vecadd_fp64:64"}

if [[ $EUID -eq 0 ]]; then SUDO=""; else SUDO="sudo -n"; fi
smi()  { nvidia-smi -i "$GPU" "$@"; }
ssmi() { $SUDO nvidia-smi -i "$GPU" "$@"; }
q()    { smi --query-gpu="$1" --format=csv,noheader,nounits | head -1 | tr -d ' '; }

for b in $BENCHES; do
  [[ -x $HERE/bin/${b%%:*} ]] || { echo "missing $HERE/bin/${b%%:*}; run 'make' first" >&2; exit 1; }
done

mkdir -p "$HERE/results"
STAMP=$(date +%Y%m%d_%H%M%S)
OUT="$HERE/results/${MODE}_$(hostname -s)_${STAMP}.csv"
TRACEDIR="$HERE/results/traces_${MODE}_${STAMP}"
[[ ${TRACE:-0} == 1 ]] && mkdir -p "$TRACEDIR"

PL_DEFAULT=$(q power.default_limit); PL_DEFAULT=${PL_DEFAULT%.*}
PL_MIN=$(q power.min_limit);         PL_MIN=${PL_MIN%.*}
PL_MAX=$(q power.max_limit);         PL_MAX=${PL_MAX%.*}

# Module-scope limits come from the "Module Power Readings" block, if any.
module_field() {
  smi -q -d POWER | awk -v key="$1" '/Module Power Readings/{m=1}
    m && index($0, key) {sub(/.*: */,""); gsub(/[^0-9.]/,""); print int($0); exit}'
}

restore() {
  echo "== restoring defaults"
  case $MODE in
    clock)  ssmi -rgc >/dev/null 2>&1 || true ;;
    power)  ssmi -pl "$PL_DEFAULT" >/dev/null 2>&1 || true ;;
    module) [[ -n ${MOD_DEFAULT:-} ]] && ssmi -pl "$MOD_DEFAULT" -sc 1 >/dev/null 2>&1 || true ;;
  esac
}
trap restore EXIT
trap 'exit 130' INT TERM

case $MODE in
  clock)
    if [[ -z ${CLOCKS:-} ]]; then
      mapfile -t ALL < <(smi --query-supported-clocks=gr --format=csv,noheader,nounits | tr -d ' ' | sort -rn | uniq)
      CLOCKS=""
      for i in "${!ALL[@]}"; do (( i % CLOCK_STRIDE == 0 )) && CLOCKS+="${ALL[$i]} "; done
      # Always include the lowest clock.
      [[ " $CLOCKS " == *" ${ALL[-1]} "* ]] || CLOCKS+="${ALL[-1]}"
    fi
    SETPOINTS="default $CLOCKS"
    ;;
  power)
    if [[ -z ${LIMITS:-} ]]; then
      LIMITS=$(seq "$PL_MAX" "-$LIMIT_STEP" "$PL_MIN" | tr '\n' ' ')
      [[ " $LIMITS " == *" $PL_MIN "* ]] || LIMITS+="$PL_MIN"
    fi
    SETPOINTS="$LIMITS"
    ;;
  module)
    MOD_DEFAULT=$(module_field "Default Power Limit")
    MOD_MIN=$(module_field "Min Power Limit")
    MOD_MAX=$(module_field "Max Power Limit")
    [[ -n $MOD_DEFAULT && -n $MOD_MIN && -n $MOD_MAX ]] || {
      echo "no module power limits reported by 'nvidia-smi -q -d POWER'" >&2; exit 1; }
    if [[ -z ${LIMITS:-} ]]; then
      LIMITS=$(seq "$MOD_MAX" "-$LIMIT_STEP" "$MOD_MIN" | tr '\n' ' ')
      [[ " $LIMITS " == *" $MOD_MIN "* ]] || LIMITS+="$MOD_MIN"
    fi
    SETPOINTS="$LIMITS"
    ;;
  none) SETPOINTS="default" ;;
  *) echo "usage: $0 clock|power|module|none" >&2; exit 2 ;;
esac

apply() {   # apply <setpoint>
  local s=$1
  case $MODE in
    clock)
      if [[ $s == default ]]; then ssmi -rgc >/dev/null
      else ssmi -lgc "$s,$s" >/dev/null; fi ;;
    power)  ssmi -pl "$s" >/dev/null ;;
    module) ssmi -pl "$s" -sc 1 >/dev/null ;;
    none) : ;;
  esac
}

echo "== mode=$MODE  setpoints: $SETPOINTS"
echo "== benches: $BENCHES"
echo "== output: $OUT"
smi --query-gpu=name,clocks.max.sm,power.default_limit,power.min_limit,power.max_limit --format=csv

header_done=0
for s in $SETPOINTS; do
  if ! apply "$s"; then
    echo "!! could not apply $MODE=$s (need root / passwordless sudo?)" >&2
    exit 1
  fi
  sleep 1
  for b in $BENCHES; do
    bin=${b%%:*}; inten=${b##*:}
    echo "-- $MODE=$s  $bin intensity=$inten"
    trace=""
    [[ ${TRACE:-0} == 1 ]] && trace="$TRACEDIR/${bin}_${inten}_${s}.csv"
    log=$(DVFS_TAG="$MODE=$s" DVFS_WARMUP="$WARMUP" DVFS_TRACE="$trace" DVFS_DEVICE=0 \
          CUDA_VISIBLE_DEVICES="$GPU" "$HERE/bin/$bin" "$DURATION" "$inten" 2>&1) || true
    grep -vE '^CSV(HDR)?,' <<<"$log" | sed 's/^/   /' || true
    if ! grep -q '^CSV,' <<<"$log"; then
      echo "!! $bin produced no result row (see output above)" >&2
      sleep "$COOLDOWN"; continue
    fi
    if (( header_done == 0 )); then
      grep '^CSVHDR,' <<<"$log" | head -1 | sed 's/^CSVHDR,/mode,setpoint,/' > "$OUT"
      header_done=1
    fi
    grep '^CSV,' <<<"$log" | sed "s/^CSV,/$MODE,$s,/" >> "$OUT"
    sleep "$COOLDOWN"
  done
done

echo "== wrote $OUT"
echo "== plot: python3 $HERE/plot.py $OUT"
