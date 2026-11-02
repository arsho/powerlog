#!/usr/bin/env bash
# Probe which power / frequency knobs this node exposes, and whether we may
# turn them.
#
#   ./check_power_control.sh             # read-only report
#   ./check_power_control.sh --try-set   # also try each setter once, then
#                                        # restore the default (needs root or
#                                        # passwordless sudo for most knobs)
#
# Output goes to stdout; tee it to keep a record:
#   ./check_power_control.sh --try-set 2>&1 | tee results/power_control_$(hostname).txt

set -u
TRY_SET=0
[[ "${1:-}" == "--try-set" ]] && TRY_SET=1
GPU="${GPU:-0}"

hr()  { printf '\n==== %s ====\n' "$*"; }
run() { printf '$ %s\n' "$*"; "$@" 2>&1 | sed 's/^/    /'; return "${PIPESTATUS[0]}"; }

# Prefer running directly as root, else non-interactive sudo, else plain.
if [[ $EUID -eq 0 ]]; then SUDO=""
elif sudo -n true 2>/dev/null; then SUDO="sudo -n"
else SUDO=""
fi

hr "Node"
run hostname
run uname -m
run nvidia-smi -L
printf 'root=%s  passwordless_sudo=%s\n' "$([[ $EUID -eq 0 ]] && echo yes || echo no)" \
  "$(sudo -n true 2>/dev/null && echo yes || echo no)"

hr "GPU: clocks, power, performance (read-only)"
run nvidia-smi -i "$GPU" -q -d CLOCK,POWER,PERFORMANCE,TEMPERATURE
run nvidia-smi -i "$GPU" --query-gpu=name,persistence_mode,pstate,clocks.sm,clocks.max.sm,clocks.mem,clocks.max.mem,power.draw,power.limit,power.default_limit,power.min_limit,power.max_limit,enforced.power.limit --format=csv

hr "GPU: supported SM clocks (the DVFS table)"
# One memory clock on HBM parts; count and range of the SM clock steps.
nvidia-smi -i "$GPU" --query-supported-clocks=mem,gr --format=csv,noheader,nounits 2>/dev/null \
  | awk -F', *' '{n[$1]++; if(!($1 in mx)||$2>mx[$1])mx[$1]=$2; if(!($1 in mn)||$2<mn[$1])mn[$1]=$2}
       END{for(m in n) printf "    mem %s MHz: %d SM clocks, %s..%s MHz\n", m, n[m], mn[m], mx[m]}'
echo "    full list: nvidia-smi -i $GPU -q -d SUPPORTED_CLOCKS"

hr "GPU: module (superchip) power, if exposed"
if nvidia-smi -i "$GPU" -q -d POWER 2>/dev/null | grep -qi 'module power'; then
  nvidia-smi -i "$GPU" -q -d POWER | grep -iA12 'module power' | sed 's/^/    /'
else
  echo "    no 'Module Power' section"
fi

hr "nvidia-smi control features in this driver"
nvidia-smi -h 2>&1 | grep -iE -- '-lgc|-lmc|-rgc|-rmc|-pl|-sc|scope|-ac |-rac|-acp|power-smoothing|power-profile|workload|boost|clocks' \
  | sed 's/^/    /'
for sub in power-smoothing power-profiles; do
  if nvidia-smi "$sub" -h >/dev/null 2>&1; then
    echo "    subcommand available: nvidia-smi $sub   (see: nvidia-smi $sub -h)"
  fi
done

hr "Grace CPU: cpufreq"
if [[ -d /sys/devices/system/cpu/cpu0/cpufreq ]]; then
  for f in scaling_driver scaling_governor scaling_available_governors \
           cpuinfo_min_freq cpuinfo_max_freq scaling_min_freq scaling_max_freq \
           scaling_available_frequencies; do
    p=/sys/devices/system/cpu/cpu0/cpufreq/$f
    [[ -r $p ]] && printf '    %-30s %s\n' "$f" "$(cat "$p")"
  done
  printf '    scaling_max_freq writable by me: %s\n' \
    "$([[ -w /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq ]] && echo yes || echo no)"
else
  echo "    no cpufreq sysfs"
fi
command -v cpupower >/dev/null && run cpupower frequency-info

hr "Power telemetry in hwmon (Grace exposes module/CPU/SysIO power here)"
for h in /sys/class/hwmon/hwmon*; do
  name=$(cat "$h/name" 2>/dev/null)
  for p in "$h"/power*_input "$h"/power*_average "$h"/device/power*_average; do
    [[ -r $p ]] || continue
    base=${p%_*}
    info=$(cat "${base}_oem_info" 2>/dev/null || cat "${base}_label" 2>/dev/null)
    val=$(cat "$p" 2>/dev/null)
    [[ -n $val ]] && printf '    %-10s %-55s %10.1f W  %s\n' "$name" "$p" "$(awk -v v="$val" 'BEGIN{print v/1e6}')" "$info"
  done
  for c in "$h"/power*_cap "$h"/device/power*_cap; do
    [[ -e $c ]] && printf '    cap: %s = %s (writable: %s)\n' "$c" "$(cat "$c" 2>/dev/null)" "$([[ -w $c ]] && echo yes || echo no)"
  done
done

hr "Powercap / RAPL (usually absent on Grace)"
ls /sys/class/powercap 2>/dev/null | sed 's/^/    /' || echo "    none"

hr "Node / BMC"
if command -v ipmitool >/dev/null; then
  run $SUDO ipmitool dcmi power reading
  run $SUDO ipmitool dcmi power get_limit
else
  echo "    ipmitool not installed"
fi
command -v dcgmi >/dev/null && run dcgmi discovery -l

if (( TRY_SET == 0 )); then
  hr "Done (read-only). Re-run with --try-set to test the setters."
  exit 0
fi

# ---------------------------------------------------------------------------
# Setter probes. Each one sets a harmless value, reads it back, and restores.
# ---------------------------------------------------------------------------
declare -A RESULT
probe() {   # probe <label> <set-cmd...>; caller restores
  local label=$1; shift
  if run $SUDO "$@"; then RESULT[$label]=OK; else RESULT[$label]=DENIED; fi
}

read -r MAXSM <<<"$(nvidia-smi -i "$GPU" --query-gpu=clocks.max.sm --format=csv,noheader,nounits)"
read -r MAXMEM <<<"$(nvidia-smi -i "$GPU" --query-gpu=clocks.max.mem --format=csv,noheader,nounits)"
read -r PLDEF <<<"$(nvidia-smi -i "$GPU" --query-gpu=power.default_limit --format=csv,noheader,nounits)"
read -r PLMIN <<<"$(nvidia-smi -i "$GPU" --query-gpu=power.min_limit --format=csv,noheader,nounits)"
PLDEF=${PLDEF%.*}; PLMIN=${PLMIN%.*}
HALF=$(( MAXSM / 2 ))

hr "TRY: persistence mode"
probe persistence nvidia-smi -i "$GPU" -pm 1

hr "TRY: lock SM clock to ~half ($HALF MHz) and back"
probe lock_gpu_clock nvidia-smi -i "$GPU" -lgc "$HALF,$HALF"
run nvidia-smi -i "$GPU" --query-gpu=clocks.sm,clocks_event_reasons.active --format=csv
run $SUDO nvidia-smi -i "$GPU" -rgc

hr "TRY: lock memory clock ($MAXMEM MHz) and back"
probe lock_mem_clock nvidia-smi -i "$GPU" -lmc "$MAXMEM,$MAXMEM"
run $SUDO nvidia-smi -i "$GPU" -rmc

hr "TRY: application clocks (legacy, may be unsupported on Blackwell)"
probe app_clocks nvidia-smi -i "$GPU" -ac "$MAXMEM,$HALF"
run $SUDO nvidia-smi -i "$GPU" -rac

hr "TRY: GPU power limit -> min ($PLMIN W) and back to default ($PLDEF W)"
probe gpu_power_limit nvidia-smi -i "$GPU" -pl "$PLMIN"
run nvidia-smi -i "$GPU" --query-gpu=power.limit,enforced.power.limit --format=csv
run $SUDO nvidia-smi -i "$GPU" -pl "$PLDEF"

hr "TRY: module power limit (scope 1 = GPU+CPU+memory on Grace superchips)"
# Read the module default from the POWER section if present.
MODDEF=$(nvidia-smi -i "$GPU" -q -d POWER | awk '/Module Power Readings/{m=1} m&&/Default Power Limit/{gsub(/[^0-9.]/,"",$0); print int($0); exit}')
if [[ -n ${MODDEF:-} && $MODDEF -gt 0 ]]; then
  probe module_power_limit nvidia-smi -i "$GPU" -pl "$MODDEF" -sc 1
else
  echo "    module default limit not found; skipping"
  RESULT[module_power_limit]=N/A
fi

hr "TRY: Grace cpufreq scaling_max_freq"
CPUF=/sys/devices/system/cpu/cpu0/cpufreq
if [[ -r $CPUF/scaling_max_freq ]]; then
  cur=$(cat $CPUF/scaling_max_freq)
  if echo "$cur" | $SUDO tee $CPUF/scaling_max_freq >/dev/null 2>&1; then
    RESULT[cpu_max_freq]=OK
  else
    RESULT[cpu_max_freq]=DENIED
  fi
else
  RESULT[cpu_max_freq]=N/A
fi

hr "SUMMARY of setters (OK = this user can drive it)"
for k in persistence lock_gpu_clock lock_mem_clock app_clocks gpu_power_limit module_power_limit cpu_max_freq; do
  printf '    %-20s %s\n' "$k" "${RESULT[$k]:-?}"
done
