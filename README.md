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
[Dependencies](#dependencies) -
[Installation](#installation) -
[Usage](#usage) -
[Documentation](#documentation) -
[Examples](#examples) -
[Contributing](#contributing) -
[References](#references) -
[License](#license) -
[Citation](#citation)

</div>

## Overview

Powerlog runs a command and reports how much energy it used, reading CPU power
and GPU power at the same instants so the two can be compared and added up.

## Features

- **Heterogeneous** -- reports CPU and GPU energy separately and combined
- **Portable** -- NVIDIA (NVML), AMD (ROCm SMI), Intel/SYCL (Level Zero), CPU RAPL
- **Non-intrusive** -- runs unmodified binaries, no recompilation
- **Whole-application** -- covers I/O, transfers, kernel launches, synchronization
- **Low overhead** -- samples from a separate process, writes results at exit
- **Multi-GPU** -- one power column per device on a node
- **Simple** -- a single command, no root on most systems
- **Robust** -- domains it cannot read are marked `n/a` instead of failing
- **Scriptable** -- CSV output, and the program's exit status is preserved

## Dependencies

Python 3.8 or newer. No Python packages are required -- Powerlog uses only the
standard library.

Everything else is optional and detected at runtime. Install only what matches
your hardware; whatever is missing is reported as `n/a`.

| Domain | Provided by | Requirement |
| ------ | ----------- | ----------- |
| NVIDIA GPU | NVIDIA driver | `nvidia-smi` on `PATH` |
| AMD GPU | ROCm, or the `amdgpu` kernel driver | `rocm-smi`/`amd-smi` on `PATH`, else readable `/sys/class/drm/card*/device/hwmon` |
| Intel GPU | Intel XPU Manager / oneAPI | `xpu-smi` on `PATH` |
| CPU | Linux RAPL | readable `/sys/class/powercap`, or `perf` |

CPU measurement is Linux only. If it is unavailable, enable one of:

```bash
sudo chmod -R a+r /sys/class/powercap      # powercap sysfs
sudo sysctl kernel.perf_event_paranoid=-1  # perf
```

Powerlog measures the node it runs on. It does not aggregate across nodes.

## Installation

```bash
pip install powerlog
```

### From this repository

```bash
git clone https://github.com/arsho/powerlog.git
pip install -e powerlog
```

`-e` installs in editable mode, so the `powerlog` command tracks your working
copy. To run it without installing at all, use
`PYTHONPATH=powerlog/src python -m powerlog ...`.

Check which power sources are visible on your machine:

```bash
powerlog --list-backends
```

### What `pip install` includes

The wheel on PyPI carries the measurement tool only. The example GPU
applications are C++/CUDA sources that must be compiled for your hardware, so
they are not installed; clone the repository to build them.

| Content | `pip install powerlog` | `git clone` |
| ------- | ---------------------- | ----------- |
| `powerlog` command and Python API | yes | yes |
| [`apps/`](apps/) example GPU programs | no | yes |
| [`datalog-engine-comparison/`](datalog-engine-comparison/) case study | no | yes |

A typical first session therefore uses both:

```bash
pip install powerlog
git clone https://github.com/arsho/powerlog.git
cd powerlog/apps && make
powerlog ./bin/matmul 2048 200
```

## Usage

Measure a program. CPU and GPU are both measured by default:

```bash
powerlog ./my_program --arg value
```

```
================================================================
                    POWERLOG ENERGY SUMMARY
================================================================
Command                 ./my_program --arg value
Runtime (s)             12.4180
CPU                     AMD EPYC 7532 32-Core Processor
GPU                     NVIDIA A100-PCIE-40GB
----------------------------------------------------------------
Domain            Energy (J)   Share (%)   Avg Power (W)
----------------------------------------------------------------
CPU                 962.4013       31.06         77.5013
GPU                2136.7742       68.94        172.0700
----------------------------------------------------------------
TOTAL              3099.1755
EDP (J*s)         38485.5262
----------------------------------------------------------------
Samples                 124
CPU source              CPU package (RAPL powercap sysfs), 2 package domain(s)
GPU source              NVIDIA GPU (nvidia-smi / NVML), 1 device(s)
================================================================
```

Two CSVs are written: a one-row summary and the full power trace.

### Choosing what to measure

```bash
powerlog ./my_program                    # CPU and GPU (default)
powerlog -m gpu ./my_program             # GPU only
powerlog -m cpu ./my_program             # CPU only
```

### Other options

```bash
powerlog -o run.csv ./my_program         # name the output (default: powerlog_output.csv)
powerlog --no-csv ./my_program           # print only, write nothing
powerlog --gpu 4 ./my_program            # sum only the first 4 GPUs
powerlog --interval 0.05 ./my_program    # sample every 50 ms
powerlog --list-backends                 # show detected power sources
```

Powerlog exits with the profiled program's exit status, or `2` for a usage
error, `127` when the program is not found and `126` when it is not executable.
The program is resolved before measurement starts, so a typo is reported by
Powerlog rather than by a wrapper:

```
$ powerlog matmul 1024 10
powerlog: error: 'matmul' is not on PATH. It exists in the current directory,
so run it as './matmul'
```

See the
[command line reference](https://powerlog.readthedocs.io/en/latest/cli.html) for
the full list of options.

Power sources are detected automatically. On a machine with GPUs from more than
one vendor, NVIDIA is preferred.

## Documentation

Full documentation is at **[powerlog.readthedocs.io](https://powerlog.readthedocs.io/)**:

- [Installation](https://powerlog.readthedocs.io/en/latest/installation.html)
- [Quick Start](https://powerlog.readthedocs.io/en/latest/quickstart.html)
- [Example Applications](https://powerlog.readthedocs.io/en/latest/apps.html)
- [Command Line Reference](https://powerlog.readthedocs.io/en/latest/cli.html)
- [Backends](https://powerlog.readthedocs.io/en/latest/backends.html)
- [Methodology](https://powerlog.readthedocs.io/en/latest/methodology.html)
- [Output Files](https://powerlog.readthedocs.io/en/latest/output.html)
- [Python API Reference](https://powerlog.readthedocs.io/en/latest/api.html)
- [Examples](https://powerlog.readthedocs.io/en/latest/examples.html)
- [Changelog](https://powerlog.readthedocs.io/en/latest/changelog.html)

## Examples

[`apps/`](apps/) contains ready-to-run GPU programs spanning several performance
regimes. They are part of this repository, not of the installed package, so
clone it and build them with `make`:

```bash
git clone https://github.com/arsho/powerlog.git
cd powerlog/apps && make
powerlog ./bin/matmul 2048 200
```

Every app takes the same two optional positional arguments,
`./<app> [size] [iterations]`:

| App | `size` means | Default size | Default iterations | Regime |
| --- | ------------ | ------------ | ------------------ | ------ |
| `vecadd` | float elements per vector | `67108864` (2^26) | `200` | Memory bandwidth |
| `matmul` | dimension `n` of an `n x n` product | `2048` | `50` | Compute |
| `gemm` | dimension `n` of an `n x n` product | `4096` | `50` | Compute (vendor tuned) |
| `reduction` | float elements summed | `67108864` (2^26) | `300` | Latency / synchronization |
| `stencil` | dimension `n` of an `n x n` grid | `4096` | `500` | Memory, iterative |
| `nbody` | number of bodies | `65536` | `100` | Compute (FMA heavy) |
| `vecadd_sycl` | float elements per vector | `67108864` (2^26) | `200` | Memory bandwidth |
| `matmul_sycl` | dimension `n` of an `n x n` product | `2048` | `50` | Compute |

Run them from `apps/`, with the `./bin/` prefix — neither `bin` nor the current
directory is on `PATH`:

```bash
powerlog --output results/matmul.csv ./bin/matmul 2048 200
powerlog --output results/gemm.csv   ./bin/gemm   4096 200
make run        # profile every app into results/
```

Details, per-app commands and troubleshooting:
[apps/README.md](apps/README.md) or
[Example Applications](https://powerlog.readthedocs.io/en/latest/apps.html) on
Read the Docs.

[`datalog-engine-comparison/`](datalog-engine-comparison/) is a larger case study
that uses Powerlog to compare the energy behaviour of five GPU-accelerated
Datalog engines -- [MNMGDatalog](https://github.com/harp-lab/MNMGDatalog),
[GPULog](https://github.com/harp-lab/gdlog),
[BJoin](https://github.com/harp-lab/batch_joins) (release pending), INLJoin and
[cuDF](https://github.com/NVIDIA/cudf) -- across two recursive queries and
seven graphs. It ships the harness, the analysis scripts and the collected
results; the engines themselves are cloned from their own repositories.

## Contributing

Questions, bug reports and patches are all welcome on the
[issue tracker](https://github.com/arsho/powerlog/issues).

For code changes, open an issue first to discuss anything substantial, then send
a pull request against `main`. Adding support for another power source means
subclassing `PowerSampler` or `EnergyCounter` in `src/powerlog/backends.py`; see
[Backends](https://powerlog.readthedocs.io/en/latest/backends.html).

Release history is in [Changelog.md](Changelog.md).

## References

The power and energy interfaces Powerlog reads from:

- [NVIDIA Management Library (NVML)](https://developer.nvidia.com/management-library-nvml)
- [ROCm SMI](https://github.com/ROCm/rocm_smi_lib)
- [Intel XPU Manager](https://github.com/intel/xpumanager)
- [Linux powercap / RAPL](https://docs.kernel.org/power/powercap/powercap.html)
- [perf-stat](https://man7.org/linux/man-pages/man1/perf-stat.1.html)

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
