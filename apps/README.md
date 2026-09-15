# Powerlog Example Applications

A set of small, self-contained GPU programs used to exercise and demonstrate
Powerlog. They span the usual performance regimes (bandwidth bound, compute
bound, latency bound, iterative) so that the resulting energy profiles differ in
interesting ways.

The same content is on Read the Docs:
**[Example Applications](https://powerlog.readthedocs.io/en/latest/apps.html)**.

- [Getting these applications](#getting-these-applications)
- [Building](#building)
- [The applications and their parameters](#the-applications-and-their-parameters)
- [Running under Powerlog](#running-under-powerlog)
- [Exact commands, app by app](#exact-commands-app-by-app)
- [Common variations](#common-variations)
- [Output files](#output-files)
- [Troubleshooting](#troubleshooting)

## Getting these applications

> **These programs are not installed by `pip install powerlog`.** The wheel
> contains the measurement tool only. The examples are C++/CUDA sources that
> have to be compiled for your GPU, so they live in this directory of the
> repository and you need a clone to build them.

```bash
pip install powerlog                              # the measurement tool
git clone https://github.com/arsho/powerlog.git   # the example applications
cd powerlog/apps
```

Installing Powerlog from the checkout gives you both at once:

```bash
git clone https://github.com/arsho/powerlog.git
cd powerlog
pip install -e .
cd apps
```

## Building

The Makefile picks a backend automatically (`nvcc`, else `hipcc`):

```bash
cd apps
make                  # build the CUDA/HIP apps
make BACKEND=cuda     # force NVIDIA
make BACKEND=hip      # force AMD
make sycl             # build the SYCL apps (icpx, else clang++ -fsycl)
make all              # everything
make help             # show the detected toolchain
make clean
```

Binaries are written to `apps/bin/`. Requirements:

* NVIDIA: CUDA toolkit (`nvcc`); `gemm` also needs cuBLAS.
* AMD: ROCm (`hipcc`); `gemm` also needs hipBLAS.
* SYCL: Intel oneAPI (`icpx`) or an `-fsycl` capable `clang++`.

On a module-based cluster, load the toolchain first, e.g. `module load cuda`.

The `cuda/` sources build unchanged for both NVIDIA and AMD: `cuda/gpu_common.h`
maps the CUDA runtime names onto HIP when compiled with `hipcc`.

## The applications and their parameters

Every program takes the same two **positional, optional** arguments:

```
./<app> [size] [iterations]
```

| Argument | Meaning |
| -------- | ------- |
| `size` | What is computed over: a matrix dimension, a grid dimension, an element count or a body count. See the table below. |
| `iterations` | How many times the kernel is launched. Changes only the amount of work, not the result. This is the knob to turn for a run long enough to sample well. |

Both are parsed with `strtol`; anything missing, non-numeric or `<= 0` falls
back to the default, so `./matmul abc` runs the default 2048 case rather than
failing.

| App | Source | `size` means | Default size | Default iterations | Regime |
| --- | ------ | ------------ | ------------ | ------------------ | ------ |
| `vecadd` | [`cuda/vecadd.cu`](cuda/vecadd.cu) | float elements per vector | `67108864` (2^26) | `200` | Memory bandwidth |
| `matmul` | [`cuda/matmul.cu`](cuda/matmul.cu) | dimension `n` of an `n x n` product | `2048` | `50` | Compute |
| `gemm` | [`cuda/gemm.cu`](cuda/gemm.cu) | dimension `n` of an `n x n` product | `4096` | `50` | Compute (vendor tuned) |
| `reduction` | [`cuda/reduction.cu`](cuda/reduction.cu) | float elements summed | `67108864` (2^26) | `300` | Latency / synchronization |
| `stencil` | [`cuda/stencil.cu`](cuda/stencil.cu) | dimension `n` of an `n x n` grid | `4096` | `500` | Memory, iterative |
| `nbody` | [`cuda/nbody.cu`](cuda/nbody.cu) | number of bodies | `65536` | `100` | Compute (FMA heavy) |
| `vecadd_sycl` | [`sycl/vecadd_sycl.cpp`](sycl/vecadd_sycl.cpp) | float elements per vector | `67108864` (2^26) | `200` | Memory bandwidth |
| `matmul_sycl` | [`sycl/matmul_sycl.cpp`](sycl/matmul_sycl.cpp) | dimension `n` of an `n x n` product | `2048` | `50` | Compute |

What each one does, and the device memory the defaults need:

| App | Kernel | Device memory | Notes |
| --- | ------ | ------------- | ----- |
| `vecadd` | Element-wise `c = a + b`, grid-stride loop | `12 x size` B (768 MiB) | Lowest arithmetic intensity in the set. |
| `matmul` | Tiled dense matrix multiply, 16x16 shared-memory tiles | `12 x size^2` B (48 MiB) | High intensity; holds the GPU near its power ceiling. |
| `gemm` | Vendor-library SGEMM (cuBLAS / hipBLAS) | `12 x size^2` B (192 MiB) | Tuned counterpart of `matmul`. |
| `reduction` | Shared-memory tree sum, sequential addressing | `4 x size` B (256 MiB) | Synchronization heavy. |
| `stencil` | 2D five-point Jacobi diffusion, ping-pong buffers | `8 x size^2` B (128 MiB) | Many short kernels; steady power. |
| `nbody` | Direct O(N^2) gravitation, tiled through shared memory | `24 x size` B (1.5 MiB) | Highest sustained power of the set. |
| `vecadd_sycl` | SYCL port of `vecadd` | `12 x size` B (768 MiB) | One binary for Intel, NVIDIA and AMD. |
| `matmul_sycl` | SYCL port of `matmul`, local-memory tiles | `12 x size^2` B (48 MiB) | One binary for Intel, NVIDIA and AMD. |

Each program prints a banner, the work it did and a checksum, and exits non-zero
if verification fails:

```
[matmul] size=2048 iterations=50
[matmul] total work=858.99 GFLOP
[matmul] checksum=2048.000000 verification=PASS
```

## Running under Powerlog

Powerlog measures CPU and GPU energy by default, so no flags are needed. The
generic form is:

```bash
powerlog ./bin/<app> [size] [iterations]
```

```
================================================================
                    POWERLOG ENERGY SUMMARY
================================================================
Command                 ./bin/matmul 2048 50
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
GPU power (W)           min 61.20 / max 249.80
CPU power (W)           min 74.90 / max 79.30
----------------------------------------------------------------
Samples                 124
CPU source              CPU package (RAPL powercap sysfs), 2 package domain(s)
GPU source              NVIDIA GPU (nvidia-smi / NVML), 1 device(s)
================================================================
Summary written to: powerlog_output.csv
Samples written to: powerlog_output_samples.csv
```

## Exact commands, app by app

Run these from `apps/` after `make`. The `./bin/` prefix is required: `bin` is
not on `PATH`, and neither is the current directory.

The sizes are chosen to run for roughly ten seconds on an A100-class GPU, which
is comfortably longer than the 100 ms sampling interval. Scale `iterations` up
or down for slower or faster hardware.

```bash
cd apps
make
mkdir -p results

# Memory bandwidth bound
powerlog --output results/vecadd.csv     ./bin/vecadd     67108864 2000

# Compute bound, hand-written kernel
powerlog --output results/matmul.csv     ./bin/matmul     2048 200

# Compute bound, vendor library
powerlog --output results/gemm.csv       ./bin/gemm       4096 200

# Latency / synchronization bound
powerlog --output results/reduction.csv  ./bin/reduction  67108864 2000

# Memory bound, iterative
powerlog --output results/stencil.csv    ./bin/stencil    4096 2000

# Compute bound, FMA heavy
powerlog --output results/nbody.csv      ./bin/nbody      65536 500

# SYCL builds (after `make sycl`)
powerlog --output results/vecadd_sycl.csv ./bin/vecadd_sycl 67108864 2000
powerlog --output results/matmul_sycl.csv ./bin/matmul_sycl 2048 200
```

To use the built-in defaults instead, drop the arguments entirely. They are
sized for a short run, which is useful as a smoke test:

```bash
powerlog ./bin/matmul
```

Profile every app at once:

```bash
make run        # writes results/<app>.csv and results/<app>_samples.csv
```

## Common variations

Sweep a problem size:

```bash
for n in 1024 2048 4096 8192; do
  powerlog --output results/matmul_$n.csv ./bin/matmul $n 200
done
```

Compare a hand-written kernel against the vendor library at the same size:

```bash
powerlog --output results/hand.csv   ./bin/matmul 4096 50
powerlog --output results/vendor.csv ./bin/gemm   4096 50
```

Measure one domain only, or sample faster on a short run:

```bash
powerlog -m gpu ./bin/nbody 65536 500        # GPU energy only
powerlog -m cpu ./bin/nbody 65536 500        # CPU energy only
powerlog --interval 0.02 ./bin/matmul 1024 20
```

### Multi-GPU

The example apps use a single GPU, but Powerlog sums every device it sees. On a
shared node, `--gpu N` limits how many are summed:

```bash
powerlog --gpu 1 ./bin/nbody 131072 500
```

### Cross-vendor runs

The power source is detected automatically, so the same command works on NVIDIA,
AMD and Intel hardware:

```bash
powerlog ./bin/matmul 2048 200        # NVML, ROCm SMI or amdgpu sysfs
powerlog ./bin/matmul_sycl 2048 200   # same, for the SYCL build
```

Check what is visible on the current machine:

```bash
powerlog --list-backends
```

## Output files

Each run writes two CSVs:

* `<name>.csv` -- one summary row with the CPU/GPU/total energy breakdown.
* `<name>_samples.csv` -- the power trace, one row per sampling interval, with a
  column per GPU device.

The sample trace is convenient for plotting power over time:

```python
import pandas as pd

df = pd.read_csv("results/matmul_samples.csv")
df.plot(x="Elapsed (s)", y=["CPU Power (W)", "GPU Power (W)"])
```

Full column list:
[Output files](https://powerlog.readthedocs.io/en/latest/output.html).

## Troubleshooting

**`powerlog: error: 'matmul' is not on PATH`**

The current directory is not on `PATH` on Linux, so a built binary has to be
named with a path: run `powerlog ./bin/matmul` from `apps/`, or
`powerlog ./matmul` from `apps/bin/`. Powerlog exits with `127` and measures
nothing in this case.

**`make` reports *no GPU compiler found***

Neither `nvcc` nor `hipcc` is on `PATH`. Load the toolchain (`module load cuda`,
`module load rocm`, ...) and check with `make help`.

**CPU energy shows `n/a`**

CPU energy comes from RAPL, which is restricted by default on many systems.
Grant unprivileged access with either:

```bash
sudo chmod -R a+r /sys/class/powercap      # enables the rapl-sysfs backend
sudo sysctl kernel.perf_event_paranoid=-1  # enables the perf backend
```

Powerlog still reports GPU energy and runtime when RAPL is unavailable.

**The CPU source is `perf` but CPU energy is still `n/a`**

`perf` reports counters only for a workload that actually ran, so a program that
fails takes the whole CPU domain down with it. Check the `Exit code` line in the
summary, fix the program, and re-run. To confirm the backend itself works:

```bash
perf stat -e power/energy-pkg/ sleep 1     # must print Joules
```

The `perf` backend also reports a single total with no CPU power trace, so the
`CPU Power (W)` column of the samples CSV stays empty. Make
`/sys/class/powercap` readable to get the `rapl-sysfs` backend and a full trace.

**Energy looks implausibly low**

The run was too short for the 100 ms sampling interval. Raise `iterations` or
pass `--interval 0.02`.
