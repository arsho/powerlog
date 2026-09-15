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

Python 3.8 or newer, no Python dependencies. Power sources are detected at
runtime: NVIDIA (NVML), AMD (ROCm SMI or `amdgpu` sysfs), Intel (Level Zero) and
CPU RAPL on Linux. Anything unavailable is reported as `n/a` rather than failing
the run.

## Use

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

Powerlog runs unmodified binaries and samples CPU and GPU power in lockstep, so
the measurement covers the whole application — I/O, transfers, kernel launches,
synchronization — not just the kernels. It writes a summary CSV and a power
trace, and exits with the program's own status.

Check what your machine exposes with `powerlog --list-backends`.

## Documentation

Everything else is at **[powerlog.readthedocs.io](https://powerlog.readthedocs.io/)**:

[Installation](https://powerlog.readthedocs.io/en/latest/installation.html) ·
[Quick Start](https://powerlog.readthedocs.io/en/latest/quickstart.html) ·
[CLI Reference](https://powerlog.readthedocs.io/en/latest/cli.html) ·
[Example Applications](https://powerlog.readthedocs.io/en/latest/apps.html) ·
[Backends](https://powerlog.readthedocs.io/en/latest/backends.html) ·
[Methodology](https://powerlog.readthedocs.io/en/latest/methodology.html) ·
[Output Files](https://powerlog.readthedocs.io/en/latest/output.html) ·
[Python API](https://powerlog.readthedocs.io/en/latest/api.html)

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
