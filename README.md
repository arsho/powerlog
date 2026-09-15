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

A command-line tool that measures the CPU and GPU energy consumed by an
unmodified program.

</div>

## Install

```bash
pip install powerlog
```

Python 3.8 or newer, no Python dependencies.

## Supported platforms

Power sources are detected at runtime. Install only what matches your hardware;
anything unavailable is reported as `n/a` rather than failing the run.

| Domain | Read through | Needs | Gives |
| ------ | ------------ | ----- | ----- |
| NVIDIA GPU | NVML | `nvidia-smi` on `PATH` | Per-device power, one column each |
| AMD GPU | ROCm SMI | `rocm-smi` or `amd-smi` on `PATH` | Per-device power |
| AMD GPU | `amdgpu` hwmon sysfs | Readable `/sys/class/drm/card*/device/hwmon` | Per-device power, no ROCm needed |
| Intel GPU | Level Zero | `xpu-smi` on `PATH` | Per-device power |
| CPU | RAPL powercap | Readable `/sys/class/powercap` | Package energy plus a power trace |
| CPU | RAPL via `perf` | `perf`, `kernel.perf_event_paranoid <= 0` | Package energy, total only |

```bash
$ powerlog --list-backends
Detected power sources:
  GPU:
    nvidia       NVIDIA GPU (nvidia-smi / NVML)
  CPU:
    rapl-sysfs   CPU package (RAPL powercap sysfs)

The first source listed for each domain is the one that will be used.
```

CPU measurement is Linux only. Powerlog measures the node it runs on; it does
not aggregate across nodes.

## Use

```bash
powerlog ./my_program --arg value
```

```
================================================================
                    POWERLOG ENERGY SUMMARY
================================================================
Command                 ./my_program --arg value
Total time (s)          12.4180  (wall clock)
CPU                     AMD EPYC 7532 32-Core Processor
GPU                     NVIDIA A100-PCIE-40GB
----------------------------------------------------------------
Domain            Energy (J)   Share (%)   Avg Power (W)
----------------------------------------------------------------
CPU                 962.4013       31.05         77.5005
GPU                2136.7742       68.95        172.0707
----------------------------------------------------------------
TOTAL              3099.1755
EDP (J*s)         38485.5614
  avg power = energy / total time,  EDP = energy x total time
----------------------------------------------------------------
GPU power (W)           min 61.20 / max 249.80
CPU power (W)           min 74.90 / max 79.30
----------------------------------------------------------------
Samples                 124
CPU source              CPU package (RAPL powercap sysfs), 2 package domain(s)
GPU source              NVIDIA GPU (nvidia-smi / NVML), 1 device(s)
================================================================
```

Powerlog runs unmodified binaries and samples CPU and GPU power in lockstep, so
the measurement covers the whole application — I/O, transfers, kernel launches,
synchronization — not just the kernels. It writes a summary CSV and a power
trace, and exits with the program's own status.

## Documentation

**[powerlog.readthedocs.io](https://powerlog.readthedocs.io/)**

This repository additionally carries two things the wheel does not: example GPU
programs in [`apps/`](apps/), and
[`datalog-engine-comparison/`](datalog-engine-comparison/), a study comparing
the energy behaviour of five GPU-accelerated Datalog engines.

## Contributing

Bug reports and patches are welcome on the
[issue tracker](https://github.com/arsho/powerlog/issues). Open an issue first
for anything substantial, then send a pull request against `main`. Release
history is in [Changelog.md](Changelog.md).

## License

MIT. See [LICENSE](LICENSE).

## Citation

```bibtex
@inproceedings{shovon2026heterogeneous,
  title={Heterogeneous Energy Characterization of GPU-Powered Datalog Engines},
  author={Shovon, Ahmedur Rahman and Sun, Yihao and Lan, Zhiling and Perarnau, Swann and Gilray, Thomas and Micinski, Kristopher and Papka, Michael E and Kumar, Sidharth},
  booktitle={2026 IEEE/ACM Workshop on Energy Efficiency with Sustainable Performance: Techniques, Tools, and Best Practices (EESP)},
  year={2026},
  organization={IEEE}
}
```
