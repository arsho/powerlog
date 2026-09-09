<div align="center">

# Powerlog

<p align="center">
  <a href="https://pypi.org/project/powerlog/">
  <img src="https://badge.fury.io/py/powerlog.svg" alt="PyPI version">
  </a>
  <a href="https://pypi.org/project/powerlog/">
  <img src="https://img.shields.io/pypi/pyversions/powerlog.svg" alt="Python versions">
  </a>
  <a href="https://powerlog.readthedocs.io/">
  <img src="https://readthedocs.org/projects/powerlog/badge/?version=latest" alt="Documentation Status">
  </a>
  <a href="https://opensource.org/licenses/MIT">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
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

Powerlog runs your program as a subprocess and samples CPU and GPU power in
lockstep until it exits, then reports a per-domain energy breakdown. It requires
no source instrumentation, no profiler integration and no root access on most
systems.

Because it profiles the whole application, the measurement covers everything the
program does -- I/O, host-device transfers, kernel launches, synchronization and
iterative solves -- including the energy that per-kernel profilers miss.

## Features

- Whole-application energy: wrap any command, no code changes
- CPU and GPU measured together on a shared timeline
- GPU backends: NVIDIA (NVML), AMD (ROCm SMI) and Intel/SYCL (Level Zero)
- CPU backend: RAPL, via powercap sysfs or `perf`
- Per-domain breakdown: CPU, GPU, total, share, average power and EDP
- Multi-GPU aware, with per-device power columns
- Graceful degradation: unavailable domains are reported as `n/a`, never fatal
- CSV summary plus a full power trace for plotting
- Command line tool and Python API
- Negligible overhead: out-of-process sampling on a configurable interval

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

Two CSVs are written: a one-row summary and the full power trace. From Python:

```python
from powerlog import measure_power

result = measure_power(["./my_program", "--arg", "value"])
print(result.total_energy_j, result.cpu_energy_j, result.gpu_energy_j)
```

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
Datalog engines.

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
@inproceedings{powerlog2026,
  author    = {Shovon, Ahmedur Rahman and
               Sun, Yihao and
               Lan, Zhiling and
               Perarnau, Swann and
               Gilray, Thomas and
               Micinski, Kristopher and
               Papka, Michael E. and
               Kumar, Sidharth},
  title     = {Heterogeneous Energy Characterization of {GPU}-Powered {D}atalog Engines},
  booktitle = {SC26-W: Workshops of the International Conference for High
               Performance Computing, Networking, Storage and Analysis},
  address   = {Chicago, IL, USA},
  year      = {2026}
}
```
