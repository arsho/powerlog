# Example Applications

Powerlog ships a set of small, self-contained GPU programs that are used to
exercise and demonstrate it. They span the usual performance regimes -- memory
bandwidth bound, compute bound, latency bound and iterative -- so their energy
profiles differ in instructive ways.

(apps-getting)=

## Getting the applications

```{important}
The example applications are **not** part of the `powerlog` wheel.
`pip install powerlog` installs the measurement tool only. The programs are
C++/CUDA sources that have to be compiled for your GPU, so they live in the
[apps/](https://github.com/arsho/powerlog/tree/main/apps) directory of the
repository. Clone it to build them.
```

```bash
pip install powerlog                              # the measurement tool
git clone https://github.com/arsho/powerlog.git   # the example applications
cd powerlog/apps
```

Installing Powerlog from a checkout gives you both at once:

```bash
git clone https://github.com/arsho/powerlog.git
cd powerlog
pip install -e .
cd apps
```

The sources are also browsable online:

* [apps/cuda/](https://github.com/arsho/powerlog/tree/main/apps/cuda) --
  CUDA/HIP sources
* [apps/sycl/](https://github.com/arsho/powerlog/tree/main/apps/sycl) --
  SYCL sources
* [apps/Makefile](https://github.com/arsho/powerlog/blob/main/apps/Makefile)
* [apps/README.md](https://github.com/arsho/powerlog/blob/main/apps/README.md)

## Building

The Makefile picks a backend automatically: `nvcc` if present, otherwise
`hipcc`.

```bash
cd apps
make                  # build the CUDA/HIP apps into apps/bin/
make BACKEND=cuda     # force NVIDIA (nvcc)
make BACKEND=hip      # force AMD (hipcc)
make sycl             # build the SYCL apps (icpx, else clang++ -fsycl)
make all              # CUDA/HIP apps + SYCL apps
make help             # show the detected toolchain
make clean
```

Binaries are written to `apps/bin/`. Requirements:

| Target | Needs |
| ------ | ----- |
| NVIDIA | CUDA toolkit (`nvcc`); `gemm` also needs cuBLAS |
| AMD | ROCm (`hipcc`); `gemm` also needs hipBLAS |
| SYCL | Intel oneAPI (`icpx`) or an `-fsycl` capable `clang++` |

On a module-based cluster, load the toolchain first, e.g. `module load cuda`.

The `cuda/` sources build unchanged for both NVIDIA and AMD:
`cuda/gpu_common.h` maps the CUDA runtime names onto HIP when compiled with
`hipcc`.

(apps-table)=

## The applications and their parameters

Every program takes the same two **positional, optional** arguments:

```text
./<app> [size] [iterations]
```

`size`
: What is being computed over. Its meaning is per application -- a matrix
  dimension, a grid dimension, an element count or a body count -- see the table
  below.

`iterations`
: How many times the kernel is launched. Only the amount of work changes; the
  result is unaffected. This is the knob to turn for a run long enough to sample
  well.

Both arguments are parsed with `strtol`. Anything missing, non-numeric or `<= 0`
silently falls back to the default, so `./matmul abc` runs the default 2048 case
rather than failing.

| App | Source | `size` means | Default size | Default iterations | Regime |
| --- | ------ | ------------ | ------------ | ------------------ | ------ |
| `vecadd` | `cuda/vecadd.cu` | float elements per vector | `67108864` (2^26) | `200` | Memory bandwidth |
| `matmul` | `cuda/matmul.cu` | dimension `n` of an `n x n` product | `2048` | `50` | Compute |
| `gemm` | `cuda/gemm.cu` | dimension `n` of an `n x n` product | `4096` | `50` | Compute (vendor tuned) |
| `reduction` | `cuda/reduction.cu` | float elements summed | `67108864` (2^26) | `300` | Latency / synchronization |
| `stencil` | `cuda/stencil.cu` | dimension `n` of an `n x n` grid | `4096` | `500` | Memory, iterative |
| `nbody` | `cuda/nbody.cu` | number of bodies | `65536` | `100` | Compute (FMA heavy) |
| `vecadd_sycl` | `sycl/vecadd_sycl.cpp` | float elements per vector | `67108864` (2^26) | `200` | Memory bandwidth |
| `matmul_sycl` | `sycl/matmul_sycl.cpp` | dimension `n` of an `n x n` product | `2048` | `50` | Compute |

What each one does, and how much device memory the defaults need:

| App | Kernel | Device memory | Notes |
| --- | ------ | ------------- | ----- |
| `vecadd` | Element-wise `c = a + b` with a grid-stride loop | `12 x size` B (768 MiB) | Lowest arithmetic intensity in the set; the bandwidth-bound end of the spectrum. |
| `matmul` | Tiled dense matrix multiply using 16x16 shared-memory tiles | `12 x size^2` B (48 MiB) | High arithmetic intensity, keeps the GPU near its power ceiling. |
| `gemm` | Vendor-library SGEMM (cuBLAS `cublasSgemm` / hipBLAS) | `12 x size^2` B (192 MiB) | The tuned counterpart of `matmul`; the pair shows what a hand-written kernel gives up in energy. |
| `reduction` | Shared-memory tree sum with sequential addressing | `4 x size` B (256 MiB) | Synchronization heavy, so the power profile differs sharply from `matmul`. |
| `stencil` | 2D five-point Jacobi heat diffusion, ping-pong buffers | `8 x size^2` B (128 MiB) | A long sequence of short kernels; steady, repetitive power. |
| `nbody` | Direct O(N^2) gravitational interaction, tiled through shared memory | `24 x size` B (1.5 MiB) | Highest sustained power of the set; a good stress case. |
| `vecadd_sycl` | SYCL port of `vecadd` | `12 x size` B (768 MiB) | One binary for Intel, NVIDIA and AMD. |
| `matmul_sycl` | SYCL port of `matmul`, local-memory tiles over an `nd_range` | `12 x size^2` B (48 MiB) | One binary for Intel, NVIDIA and AMD. |

Each program prints a banner, the work it did and a checksum, and exits non-zero
if verification fails:

```text
[matmul] size=2048 iterations=50
[matmul] total work=858.99 GFLOP
[matmul] checksum=2048.000000 verification=PASS
```

## Running them under Powerlog

The generic form -- CPU and GPU are both measured by default, so no flags are
required:

```bash
powerlog ./bin/<app> [size] [iterations]
```

```text
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

(apps-exact-commands)=

## Exact commands, app by app

Run these from `apps/` after `make`. The `./bin/` prefix is required: `bin` is
not on `PATH`, and neither is the current directory.

The sizes below are chosen to run for roughly ten seconds on an A100-class GPU,
which is comfortably longer than the 100 ms sampling interval. Scale
`iterations` up or down for slower or faster hardware.

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

The built-in defaults are sized for a short run and are useful only as a smoke
test, not as a measurement:

```bash
powerlog ./bin/matmul
```

Every app at once, into `results/`:

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

Measure one domain only:

```bash
powerlog -m gpu ./bin/nbody 65536 500      # GPU energy only
powerlog -m cpu ./bin/nbody 65536 500      # CPU energy only
```

Sample faster for a short run:

```bash
powerlog --interval 0.02 ./bin/matmul 1024 20
```

### Multi-GPU

The example apps use a single GPU, but Powerlog sums every device it sees.
`--gpu N` limits how many are summed, which is what you want when a node is
shared:

```bash
powerlog --gpu 1 ./bin/nbody 131072 500
```

### Cross-vendor runs

The power source is detected automatically, so the same command works on
NVIDIA, AMD and Intel hardware:

```bash
powerlog ./bin/matmul 2048 200        # NVML, ROCm SMI or amdgpu sysfs
powerlog ./bin/matmul_sycl 2048 200   # same, for the SYCL build
```

Check what is visible on the current machine first:

```bash
powerlog --list-backends
```

## Output files

Each run writes two CSVs:

* `<name>.csv` -- one summary row with the CPU/GPU/total energy breakdown.
* `<name>_samples.csv` -- the power trace, one row per sampling interval, with a
  column per GPU device.

The trace is convenient for plotting power over time:

```python
import pandas as pd

df = pd.read_csv("results/matmul_samples.csv")
df.plot(x="Elapsed (s)", y=["CPU Power (W)", "GPU Power (W)"])
```

See {doc}`output` for the full column list.

## Troubleshooting

`powerlog: error: 'matmul' is not on PATH`
: The current directory is not on `PATH` on Linux, so a built binary has to be
  named with a path: run `powerlog ./bin/matmul` from `apps/`, or
  `powerlog ./matmul` from `apps/bin/`. Powerlog exits with `127` and measures
  nothing in this case.

`make` reports *no GPU compiler found*
: Neither `nvcc` nor `hipcc` is on `PATH`. On a module-based cluster, load the
  toolchain first, e.g. `module load cuda`. Run `make help` to see what was
  detected.

Only a handful of samples were taken
: The run finished in well under a second, so most of it was CUDA context
  creation and allocation at idle power. Raise `iterations` until the run lasts
  several seconds.

CPU shows `n/a`
: CPU energy comes from RAPL, which is restricted by default on many systems.
  Enable one of `sudo chmod -R a+r /sys/class/powercap` (rapl-sysfs backend) or
  `sudo sysctl kernel.perf_event_paranoid=-1` (perf backend). Powerlog still
  reports GPU energy and runtime when RAPL is unavailable; see {doc}`backends`.

Energy looks implausibly low
: The run was too short for the 100 ms sampling interval. Raise `iterations` or
  pass `--interval 0.02`.
