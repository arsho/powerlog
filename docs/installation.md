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

## What you need

Nothing beyond the vendor tool you already have: `nvidia-smi`,
`rocm-smi`/`amd-smi` or `xpu-smi` on `PATH` for the GPU, and a readable
`/sys/class/powercap` or `perf` for the CPU. Every backend and its requirement
is listed in {doc}`backends`.

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
