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

Powerlog wraps any command and reports the CPU and GPU energy it consumed,
sampling NVML and RAPL in lockstep on a shared timeline.

## Features

- **Heterogeneous** -- CPU package and GPU energy on one timeline, not GPU alone
- **Portable** -- NVIDIA (NVML), AMD (ROCm SMI), Intel/SYCL (Level Zero), RAPL
- **Non-intrusive** -- unmodified binaries, no source or kernel instrumentation
- **Whole-application** -- covers I/O, transfers, launches and synchronization
- **Low overhead** -- out-of-process sampling, buffered, flushed at exit
- **Multi-GPU** -- per-device power columns, MPI-friendly
- **Simple** -- one command, no root on most systems
- **Robust** -- unmeasurable domains report `n/a` instead of failing
- **Scriptable** -- CSV summary and full power trace, program exit status preserved

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

### Common options

```bash
powerlog --output run.csv ./my_program     # name the output (default: powerlog_output.csv)
powerlog --no-csv ./my_program             # print only, write nothing
powerlog --gpu 4 mpiexec -n 4 ./my_program # sum the first 4 GPUs
powerlog --interval 0.05 ./my_program      # sample every 50 ms
powerlog --no-cpu ./my_program             # GPU only
powerlog --gpu-backend amd ./my_program    # pin the vendor backend
powerlog --list-backends                   # show detected power sources
```

Powerlog exits with the profiled program's exit status. See the
[command line reference](https://powerlog.readthedocs.io/en/latest/cli.html) for
the full list.

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
