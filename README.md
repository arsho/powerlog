<div align="center">

# Powerlog

<p align="center">
  <a href="https://pypi.org/project/powerlog/">
  <img src="https://img.shields.io/pypi/v/powerlog?color=blue" alt="PyPI version">
  </a>
  <a href="https://pypi.org/project/powerlog/">
  <img src="https://img.shields.io/pypi/pyversions/powerlog" alt="Python versions">
  </a>
  <a href="https://powerlog.readthedocs.io/">
  <img src="https://img.shields.io/readthedocs/powerlog" alt="Documentation">
  </a>
  <a href="https://opensource.org/licenses/MIT">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
  </a>
</p>

<p>
A lightweight harness that measures the CPU and GPU energy consumed by an
unmodified program.
</p>

[Overview](#overview) -
[Features](#features) -
[Installation](#installation) -
[Quick Start](#quick-start) -
[Documentation](#documentation) -
[Examples](#examples) -
[Get Help](#get-help) -
[Contribute](#contribute) -
[License](#license) -
[Citation](#citation)

</div>

## Overview

Powerlog captures **whole-application** energy for an unmodified program, with no
source instrumentation. Rather than adding a new sensor, it composes the standard
counters the platform already exposes: it launches the target as a subprocess and
samples two sources in lockstep -- per-GPU power from NVML and CPU-package power
from RAPL -- time-stamping each pair against the same wall clock on a 100 ms
interval.

Because it profiles end to end, the trace spans I/O, host-device transfers,
kernel launches, synchronization and fixed-point iterations, capturing the energy
that per-kernel tools miss. Conventional GPU-only accounting can misrank
implementations and understate total energy by up to 2x, because the CPU package
is frequently a large and workload-dependent share of the total.

Powerlog reports GPU energy, CPU-package energy, their sum, mean and peak power,
and the energy-delay product, plus a per-sample trace, and it scales to all GPUs
in a job. Overhead is negligible by design: sampling is an out-of-process read
with no in-kernel instrumentation, and samples are buffered in memory and flushed
to CSV only at exit.

Two caveats are systematic. NVML reports a duty-cycled sensor that can bias
absolute energy, and RAPL reports package energy (cores and uncore). Runs on the
same hardware share identical sampling, so neither bias affects relative
comparison.

## Features

- Whole-application energy: wrap any command, no code changes
- CPU and GPU sampled in lockstep on a shared timeline
- GPU backends: NVIDIA (NVML), AMD (ROCm SMI) and Intel/SYCL (Level Zero)
- CPU backend: RAPL, via powercap sysfs or `perf`
- Per-domain breakdown: CPU, GPU, total, share, mean/peak power and EDP
- Multi-GPU aware, with per-device power columns
- Graceful degradation: unavailable domains are reported as `n/a`, never fatal
- CSV summary plus a full power trace for plotting
- Command line tool and Python API
- Negligible overhead: out-of-process sampling, no root needed on most systems

## Installation

```bash
pip install powerlog
```

Requires Python 3.8+. Vendor tooling is optional and detected at runtime:

| Domain | Requirement |
| ------ | ----------- |
| NVIDIA GPU | `nvidia-smi` on `PATH` |
| AMD GPU | `rocm-smi` or `amd-smi` on `PATH` |
| Intel GPU | `xpu-smi` on `PATH` |
| CPU | Linux RAPL via `/sys/class/powercap` or `perf` |

Check what is visible on your machine:

```bash
powerlog --list-backends
```

## Quick Start

Measure a program. CPU and GPU are both measured by default:

```bash
powerlog ./my_program --arg value
```

```
================================================================
                    POWERLOG ENERGY SUMMARY
================================================================
Command                 ./my_program --arg value
Exit code               0
Runtime (s)             12.4180
Samples                 124
----------------------------------------------------------------
Domain            Energy (J)   Share (%)   Avg Power (W)
----------------------------------------------------------------
CPU                 962.4013       31.06         77.5013
GPU                2136.7742       68.94        172.0700
----------------------------------------------------------------
TOTAL              3099.1755
EDP (J*s)         38485.5262
================================================================
```

Two CSVs are written: a one-row summary and the full power trace.

The Python API is useful when you want to compare configurations rather than
profile a single run:

```python
from powerlog import measure_power

for size in (1024, 2048, 4096):
    r = measure_power(["./matmul", str(size)])
    print(f"{size:>5}  {r.total_time_s:6.2f} s  {r.total_energy_j:8.1f} J  "
          f"cpu {r.cpu_fraction:.0%}")
```

```text
 1024    1.91 s     287.4 J  cpu 46%
 2048   12.42 s    3099.2 J  cpu 31%
 4096   98.03 s   26933.6 J  cpu 24%
```

The fastest configuration is often not the most energy-efficient, which is the
reason to measure rather than infer.

## Documentation

Full documentation is at **[powerlog.readthedocs.io](https://powerlog.readthedocs.io/)**:

- [Installation](https://powerlog.readthedocs.io/en/latest/installation.html)
- [Quick Start](https://powerlog.readthedocs.io/en/latest/quickstart.html)
- [Command Line Reference](https://powerlog.readthedocs.io/en/latest/cli.html)
- [Python API Reference](https://powerlog.readthedocs.io/en/latest/api.html)
- [Backends](https://powerlog.readthedocs.io/en/latest/backends.html)
- [Methodology](https://powerlog.readthedocs.io/en/latest/methodology.html)

## Examples

[`apps/`](apps/) contains ready-to-run GPU programs spanning several performance
regimes -- `vecadd`, `matmul`, `gemm`, `reduction`, `stencil`, `nbody`, plus SYCL
ports. See [apps/README.md](apps/README.md) for building and profiling them.

```bash
cd apps && make
powerlog ./bin/matmul 2048
```

[`datalog-engine-comparison/`](datalog-engine-comparison/) is a larger case study
that uses Powerlog to compare the energy behaviour of five GPU-accelerated
Datalog engines -- [MNMGDatalog](https://github.com/harp-lab/MNMGDatalog),
[GPULog](https://github.com/harp-lab/gdlog),
[BJoin](https://github.com/harp-lab/batch_joins), INLJoin and
[cuDF](https://github.com/rapidsai/cudf) -- across two recursive queries and
seven graphs. It ships the harness, the analysis scripts and the collected
results; the engines themselves are cloned from their own repositories.

## Get Help

Ask a question or report a bug on the
[issue tracker](https://github.com/arsho/powerlog/issues).

## Contribute

Contributions are welcome. Please open an issue to discuss substantial changes,
then submit a pull request against `main`. See [Changelog.md](Changelog.md) for
release history.

## License

Powerlog is released under the MIT License. See [LICENSE](LICENSE).

## Citation

If you use Powerlog in your work, please cite:

```bibtex
@inproceedings{shovon2026heterogeneous,
  title={Heterogeneous Energy Characterization of GPU-Powered Datalog Engines},
  author={Shovon, Ahmedur Rahman and Sun, Yihao and Lan, Zhiling and Perarnau, Swann and Gilray, Thomas and Micinski, Kristopher and Papka, Michael E and Kumar, Sidharth},
  booktitle={2026 IEEE/ACM Workshop on Energy Efficiency with Sustainable Performance: Techniques, Tools, and Best Practices (EESP)},
  year={2026},
  organization={IEEE}
}
```
