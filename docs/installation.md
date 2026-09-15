# Installation

## From PyPI

```bash
pip install powerlog
```

Powerlog requires Python 3.8 or newer and has no Python dependencies; it uses
only the standard library.

## From source

```bash
git clone https://github.com/arsho/powerlog.git
cd powerlog
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

`-e` installs in editable mode, so the `powerlog` command tracks your working
copy. To run straight from a checkout without installing anything:

```bash
PYTHONPATH=src python -m powerlog ./my_program
```

## What `pip install` does and does not give you

The wheel on PyPI contains the measurement tool only: the `powerlog` command and
the `powerlog` Python package. The example GPU applications and the Datalog case
study are **not** installed, because they are C++/CUDA sources that must be
compiled for your hardware.

| Content | `pip install` | `git clone` |
| ------- | ------------- | ----------- |
| `powerlog` command and Python API | yes | yes |
| `apps/` example GPU programs | no | yes |
| `datalog-engine-comparison/` | no | yes |

So a typical first session is both:

```bash
pip install powerlog
git clone https://github.com/arsho/powerlog.git
cd powerlog/apps
make
powerlog ./bin/matmul 2048 200
```

See {doc}`apps` for the applications, their parameters and the exact command to
run each one.

## Vendor requirements

The measurement backends are optional and detected at runtime. Install only what
you need for the hardware you are profiling.

### GPU

| Vendor | Tool | Ships with |
| ------ | ---- | ---------- |
| NVIDIA | `nvidia-smi` | NVIDIA driver |
| AMD | `rocm-smi` or `amd-smi` | ROCm |
| Intel | `xpu-smi` | Intel XPU Manager / oneAPI |

The tool simply has to be on `PATH`.

### CPU

CPU energy is read from RAPL on Linux, through one of two sources:

`rapl-sysfs` (preferred)
: Reads `/sys/class/powercap/*/energy_uj`. Preferred because it can be polled in
  lockstep with the GPU, which produces a CPU power trace as well as a total.

`perf`
: Wraps the command in `perf stat -e power/energy-pkg/`. Used as a fallback;
  reports a total only, with no trace.

Both are restricted by default on many distributions. Enable one of them:

```bash
# allow the perf backend
sudo sysctl kernel.perf_event_paranoid=-1

# allow the sysfs backend
sudo chmod -R a+r /sys/class/powercap
```

CPU energy measurement is Linux only. On other platforms Powerlog still reports
GPU energy and runtime.

## Verifying the installation

List the power sources detected on the current machine:

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

Then profile a trivial command:

```bash
powerlog --no-csv sleep 2
```
