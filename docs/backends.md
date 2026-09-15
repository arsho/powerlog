# Backends

Each domain has a set of backends, probed in priority order and selected
automatically. {class}`~powerlog.PowerSampler` backends poll *power* in Watts
and are integrated over time; {class}`~powerlog.EnergyCounter` backends read a
monotonic *energy* counter in Joules and are differenced. All GPU backends are
the former, RAPL the latter.

## GPU

`nvidia`
: NVML, via `nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits`.
  Summed across visible devices; a GPU without a power sensor reports `[N/A]`
  and contributes zero.

`amd`
: ROCm SMI. Prefers `amd-smi metric -p --csv`, falls back to
  `rocm-smi --showpower --csv`.

`amd-sysfs`
: `/sys/class/drm/card*/device/hwmon/hwmon*/power1_average`, in microwatts,
  straight from the `amdgpu` driver. Needs no ROCm at all, which rescues
  module-based systems where the vendor tools cannot load their libraries.

`intel`
: Level Zero / SYCL devices via `xpu-smi dump -d -1 -m 1 -n 1`. `xpumcli` is
  accepted as an alias.

## CPU

`rapl-sysfs` (preferred)
: `/sys/class/powercap/*/energy_uj` for each top-level package domain.
  Subdomains are skipped so core/uncore/DRAM are not double counted, and
  wraparound is handled via `max_energy_range_uj`. Preferred because it polls in
  lockstep with the GPU, yielding a CPU power trace as well as a total.

`perf`
: `perf stat -e power/energy-pkg/` wrapped around the command. Reports a total
  only — `perf` prints at process exit — so the `CPU Power (W)` column of the
  samples file stays empty, and the summary says
  `CPU package (RAPL via perf, total only)`.

  Availability requires `perf` to return an actual Joules value, not merely to
  accept the event: several `perf` versions echo the event name inside their
  permission-denied message, so a laxer test would advertise the backend on
  machines where every measurement comes back empty.

## Selecting

Detection is automatic and the command line does not override it: a machine has
one CPU package interface and, in practice, one GPU vendor worth measuring. With
GPUs from several vendors, probing prefers NVIDIA, then AMD, then Intel. Use
`-m/--measure` to pick *domains*, and `--list-backends` to see what was found.

The Python API can pin a backend, which is useful in tests:

```python
from powerlog import measure_power

measure_power(["./my_program"], gpu_backend="amd", cpu_backend="none")
```

A custom source is a {class}`~powerlog.PowerSampler` subclass prepended to the
probe order:

```python
import powerlog.backends as backends

class MyMeter(backends.PowerSampler):
    name = "mymeter"
    vendor = "External wall meter"

    @classmethod
    def is_available(cls):
        return True

    def read_power(self):
        return [read_watts_from_somewhere()]

backends.GPU_BACKENDS = (MyMeter,) + backends.GPU_BACKENDS
```

## Troubleshooting

CPU shows `n/a`
: RAPL is restricted by default on most systems. Enable one of
  `sudo chmod -R a+r /sys/class/powercap` (rapl-sysfs) or
  `sudo sysctl kernel.perf_event_paranoid=-1` (perf). Linux only; GPU energy and
  runtime are still reported without it.

CPU source is `perf` but CPU energy is `n/a`
: `perf` writes counters only for a workload that ran, so a program that fails
  takes the CPU domain down with it — check the `Exit code` line. Otherwise
  confirm the backend directly; it must print Joules:
  `perf stat -e power/energy-pkg/ sleep 1`.

GPU shows `n/a`
: Powerlog shells out to the vendor tool, so it must work standalone first:
  `nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits`,
  `amd-smi metric -p --csv`, `rocm-smi --showpower --csv` or
  `xpu-smi dump -d -1 -m 1 -n 1`.

  On module-based HPC systems the usual cause is a ROCm module that leaves
  `LD_LIBRARY_PATH` unset, so the tool cannot find `librocm_smi64.so` /
  `libamd_smi.so`. Both are Python wrappers loading through ctypes, so they can
  fail even when the path looks right; the `amd-sysfs` backend reads the same
  figure from the kernel instead.

`powerlog: error: ... is not on PATH`
: The current directory is not on `PATH` on Linux. Name the binary with a path,
  e.g. `powerlog ./bin/matmul`. Exit code `127` (not found) or `126` (found but
  not executable); nothing is measured either way.

`make` reports *no GPU compiler found*
: Neither `nvcc` nor `hipcc` is on `PATH`. Load the toolchain first, e.g.
  `module load cuda`, and check with `make help`.

Energy looks implausibly low, or only a handful of samples were taken
: The run was too short for the 100 ms interval. Most of a sub-second GPU run is
  CUDA context creation and allocation at idle power, so the average reflects
  the idle floor rather than the kernel. Raise the workload or pass
  `--interval 0.02`.
