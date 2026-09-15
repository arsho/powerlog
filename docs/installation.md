# Installation

```bash
pip install powerlog
```

Python 3.8 or newer. No Python dependencies — Powerlog uses only the standard
library.

Verify what the machine exposes:

```bash
powerlog --list-backends
```

```text
Detected power sources:
  GPU:
    nvidia       NVIDIA GPU (nvidia-smi / NVML)
  CPU:
    rapl-sysfs   CPU package (RAPL powercap sysfs)

The first source listed for each domain is the one that will be used.
```

If a domain is missing, see {doc}`backends`.

## Hardware requirements

Everything is optional and detected at runtime; install only what matches your
hardware.

| Domain | Needs |
| ------ | ----- |
| NVIDIA GPU | `nvidia-smi` on `PATH` (NVIDIA driver) |
| AMD GPU | `rocm-smi`/`amd-smi` on `PATH`, else readable `amdgpu` hwmon sysfs |
| Intel GPU | `xpu-smi` on `PATH` (Intel XPU Manager / oneAPI) |
| CPU | Linux RAPL: readable `/sys/class/powercap`, or `perf` |

CPU measurement is Linux only. Powerlog measures the node it runs on; it does
not aggregate across nodes.

## From source

```bash
git clone https://github.com/arsho/powerlog.git
cd powerlog
pip install -e .
```

The repository also carries the example GPU programs described in {doc}`apps`
and a Datalog energy case study, neither of which is part of the wheel.
