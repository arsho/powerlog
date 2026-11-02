# DVFS / power-control micro-benchmarks

Vecadd-shaped CUDA kernels used to see what frequency and power control a GPU
node (written for the GB300 / Grace Blackwell node) offers, and what each knob
does to performance and power. They are kept separate from `apps/` and from
the `powerlog` package.

Each binary runs its kernel for a **fixed wall time** and samples NVML itself
(GPU power, module power if exposed, SM/mem clock, temperature, and
clock-event reasons). It prints a summary and one `CSV,` row.

| Binary | Pipe exercised | Default intensity | Regime |
| ------ | -------------- | ----------------- | ------ |
| `vecadd_mem`   | LD/ST, float4 | n/a | HBM bandwidth bound (3 GiB working set) |
| `vecadd_fp32`  | FFMA   | 512 | compute bound; use intensity 1–16 to walk down the roofline |
| `vecadd_fp16`  | HFMA2  | 512 | compute bound, highest CUDA-core power density |
| `vecadd_int32` | IMAD   | 512 | compute bound, integer pipe |
| `vecadd_fp64`  | DFMA   | 64  | compute bound (GB300 has a small FP64 rate) |

```
./bin/<bench> [seconds=20] [intensity] [n_elements]
env: DVFS_WARMUP=3  DVFS_SAMPLE_MS=20  DVFS_TRACE=trace.csv  DVFS_TAG=label
```

## Build (on the GB300 node)

```bash
module load cuda                 # needs CUDA >= 12.9 for sm_103
cd powerlog/dvfs
make                             # ARCH=native; or: make ARCH=sm_103
make sass                        # confirm FFMA/HFMA2/IMAD/DFMA in the loops
./bin/vecadd_fp32 10             # smoke test
```

The `__conda_exe: exec format error` at login means `~/miniconda3` is an
x86_64 install and the node is aarch64. None of this needs conda: the
benchmarks are plain CUDA, and `plot.py` only needs a Python 3 with
matplotlib.

## 1. What control do we have? (run these first)

```bash
./check_power_control.sh                 # read-only report
./check_power_control.sh --try-set       # try each setter, then restore
```

Or by hand:

```bash
# Who am I allowed to be
sudo -n true && echo "passwordless sudo" || echo "no sudo"

# DVFS table: SM clocks the driver will accept (HBM has a single mem clock)
nvidia-smi -q -d SUPPORTED_CLOCKS | head -40
nvidia-smi --query-supported-clocks=mem,gr --format=csv | wc -l

# Current clocks, power limits (GPU and Module), throttle reasons
nvidia-smi -q -d CLOCK,POWER,PERFORMANCE
nvidia-smi --query-gpu=clocks.sm,clocks.max.sm,clocks.mem,power.draw,power.limit,power.min_limit,power.max_limit,power.default_limit,enforced.power.limit,clocks_event_reasons.active --format=csv

# Which control flags this driver has
nvidia-smi -h | grep -iE -- '-lgc|-lmc|-pl|-sc|scope|power-smoothing|profile'
nvidia-smi power-smoothing -h ; nvidia-smi power-profiles -h   # if present

# Live monitoring while something runs (100 ms)
nvidia-smi --query-gpu=timestamp,power.draw.instant,clocks.sm,clocks.mem,temperature.gpu,clocks_event_reasons.active --format=csv -lms 100
nvidia-smi dmon -s pucv -d 1

# Grace CPU side: cpufreq, plus hwmon power meters (module / Grace / CPU / SysIO)
cpupower frequency-info
grep . /sys/devices/system/cpu/cpu0/cpufreq/{scaling_driver,scaling_governor,cpuinfo_min_freq,cpuinfo_max_freq,scaling_max_freq}
grep . /sys/class/hwmon/hwmon*/name /sys/class/hwmon/hwmon*/device/power1_oem_info 2>/dev/null
grep . /sys/class/hwmon/hwmon*/device/power1_average 2>/dev/null   # microwatts

# Node / BMC
sudo ipmitool dcmi power reading
sudo ipmitool dcmi power get_limit
```

## 2. Setters (need root, or a site wrapper/allowlist)

```bash
sudo nvidia-smi -pm 1                       # persistence, so settings stick
sudo nvidia-smi -lgc 1200,1200              # lock SM clock (min,max MHz)
sudo nvidia-smi -lgc 0,1500                 # cap SM clock, let it float below
sudo nvidia-smi -rgc                        # reset SM clock
sudo nvidia-smi -lmc <mhz>,<mhz> ; sudo nvidia-smi -rmc     # memory clock
sudo nvidia-smi -pl 700                     # GPU power limit (W)
sudo nvidia-smi -pl 900 -sc 1               # module power limit (scope 1)
sudo nvidia-smi -pl <default W>             # restore
# Grace CPU frequency cap
sudo cpupower frequency-set -u 2.0GHz ; sudo cpupower frequency-set -u <max>
# Node cap via BMC (if the site allows it)
sudo ipmitool dcmi power set_limit limit 2000 && sudo ipmitool dcmi power activate
sudo ipmitool dcmi power deactivate
```

If `-lgc`/`-pl` come back with "Insufficient Permissions", ask the admins
whether there is a supported route: a sudo rule for `nvidia-smi -lgc/-rgc/-pl`,
DCGM (`dcgmi config --set -P <W>`), or a scheduler flag for GPU power/clocks.

## 3. Sweeps

```bash
./sweep.sh none                  # baseline, default DVFS (firmware picks clocks)
./sweep.sh clock                 # lock SM clock over the supported table
./sweep.sh power                 # GPU power limit max -> min in 100 W steps
./sweep.sh module                # module power limit (if exposed)

# Narrower / faster variants
CLOCKS="2100 1800 1500 1200 900 600" DURATION=10 ./sweep.sh clock
LIMITS="1300 1100 900 700 500 300"  ./sweep.sh power
BENCHES="vecadd_fp32:1 vecadd_fp32:4 vecadd_fp32:16 vecadd_fp32:64 vecadd_fp32:512" ./sweep.sh clock
TRACE=1 ./sweep.sh power         # keep per-sample NVML traces too

python3 plot.py results/clock_*.csv
```

Each CSV row records the set point, achieved throughput (`gops`, `gbps`),
average and max GPU power, GPU energy from the NVML counter, module power,
`gops_per_w`, energy per pass, measured SM clock (avg/min/max), the enforced
power limit, and the fraction of samples spent in each clock-event reason
(`frac_pwr_cap`, `frac_thermal`, `frac_hw_slowdown`, `frac_clk_setting`).

What to look for:

- **Default DVFS** (`none`): which clock the firmware actually holds under each
  kernel, and whether `sw_pwr_cap` is active. Dense FP16/FP32 may hit the
  power cap below the max clock; `vecadd_mem` should not.
- **Clock sweep**: compute-bound throughput should scale with the clock, while
  `vecadd_mem` stays nearly flat. That flat region is where lowering the clock
  saves energy without losing performance. Find the clock with the lowest
  energy per pass (and the lowest EDP) for each kernel.
- **Power sweep**: the clock the firmware settles at under each cap
  (`sm_mhz_avg`), the throughput lost per watt removed, and whether the cap is
  respected (`gpu_power_w` vs `power_limit_w`).
- **Module sweep**: whether the module cap takes power from the GPU or from the
  Grace CPU first.
