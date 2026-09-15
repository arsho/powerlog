# Powerlog

A lightweight harness that measures the CPU and GPU energy consumed by an
unmodified program.

Powerlog captures *whole-application* energy with no source instrumentation.
Rather than adding a new sensor, it composes the standard counters the platform
already exposes: it launches the target as a subprocess and samples two sources
in lockstep -- per-GPU power from NVML and CPU-package power from RAPL --
time-stamping each pair against the same wall clock on a 100 ms interval.

```bash
pip install powerlog
powerlog ./my_program --arg value
```

```python
from powerlog import measure_power

result = measure_power(["./my_program", "--arg", "value"])
print(result.total_energy_j, result.cpu_energy_j, result.gpu_energy_j)
```

## Why whole-application measurement

Because Powerlog profiles end to end, the trace spans I/O, host-device transfers,
kernel launches, synchronization and fixed-point iterations, capturing the energy
that per-kernel tools miss.

Measuring only the GPU is not enough either. The CPU package is frequently a
large and workload-dependent share of total energy, so GPU-only accounting can
misrank implementations and understate total energy by up to 2x.

## Supported hardware

| Domain | Source | Requirement |
| ------ | ------ | ----------- |
| NVIDIA GPU | NVML | `nvidia-smi` |
| AMD GPU | ROCm SMI, or the `amdgpu` hwmon nodes | `rocm-smi`/`amd-smi`, else readable sysfs |
| Intel GPU | Level Zero (SYCL devices) | `xpu-smi` |
| CPU | RAPL package domains | powercap sysfs or `perf` |

Any domain that is unavailable is reported as `n/a` rather than failing the run.

```{toctree}
:maxdepth: 2
:caption: User Guide

installation
quickstart
apps
cli
backends
methodology
output
```

```{toctree}
:maxdepth: 2
:caption: Reference

api
```

```{toctree}
:maxdepth: 1
:caption: Project

examples
changelog
citation
```

## Indices and tables

* {ref}`genindex`
* {ref}`modindex`
* {ref}`search`
