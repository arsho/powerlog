# Powerlog Example Applications

Small, self-contained GPU programs used to exercise Powerlog. They span the
usual performance regimes, so their energy profiles differ in instructive ways.

These are **not** installed by `pip install powerlog` — they are C++/CUDA
sources that must be compiled for your GPU.

Full guide:
[Example Applications](https://powerlog.readthedocs.io/en/latest/apps.html).

## Build

```bash
make                  # nvcc if present, else hipcc; binaries land in bin/
make BACKEND=hip      # force AMD
make sycl             # SYCL apps (icpx, else clang++ -fsycl)
make help             # show the detected toolchain
make clean
```

`gemm` additionally needs cuBLAS (NVIDIA) or hipBLAS (AMD). The `cuda/` sources
build unchanged for both vendors: [`cuda/gpu_common.h`](cuda/gpu_common.h) maps
the CUDA runtime names onto HIP under `hipcc`. On a cluster, load the toolchain
first (`module load cuda`).

## Parameters

Every program takes the same two positional, optional arguments:

```
./<app> [size] [iterations]
```

`size` is what the program computes over; `iterations` is how many times the
kernel is launched, which changes the amount of work but not the result. Both
are parsed with `strtol`, so anything missing, non-numeric or `<= 0` falls back
to the default.

| App | `size` means | Default size | Default iters | Regime and kernel |
| --- | ------------ | ------------ | ------------- | ----------------- |
| [`vecadd`](cuda/vecadd.cu) | float elements per vector | `67108864` | `200` | Memory bandwidth; element-wise `c = a + b` |
| [`matmul`](cuda/matmul.cu) | dimension of an `n x n` product | `2048` | `50` | Compute; 16x16 shared-memory tiled multiply |
| [`gemm`](cuda/gemm.cu) | dimension of an `n x n` product | `4096` | `50` | Compute, vendor tuned; cuBLAS/hipBLAS SGEMM |
| [`reduction`](cuda/reduction.cu) | float elements summed | `67108864` | `300` | Latency/sync; shared-memory tree sum |
| [`stencil`](cuda/stencil.cu) | dimension of an `n x n` grid | `4096` | `500` | Memory, iterative; 2D five-point Jacobi |
| [`nbody`](cuda/nbody.cu) | number of bodies | `65536` | `100` | Compute, FMA heavy; direct O(N^2) gravitation |
| [`vecadd_sycl`](sycl/vecadd_sycl.cpp) | float elements per vector | `67108864` | `200` | SYCL port of `vecadd` |
| [`matmul_sycl`](sycl/matmul_sycl.cpp) | dimension of an `n x n` product | `2048` | `50` | SYCL port of `matmul` |

## Run

The generic form, from this directory. The `./bin/` prefix is required --
neither `bin` nor the current directory is on `PATH`:

```bash
powerlog ./bin/<app> [size] [iterations]
```

These sizes run for roughly ten seconds on an A100-class GPU, comfortably longer
than the 100 ms sampling interval. Scale `iterations` for other hardware; the
built-in defaults are a smoke test, not a measurement.

```bash
mkdir -p results
powerlog --output results/vecadd.csv     ./bin/vecadd     67108864 2000
powerlog --output results/matmul.csv     ./bin/matmul     2048 200
powerlog --output results/gemm.csv       ./bin/gemm       4096 200
powerlog --output results/reduction.csv  ./bin/reduction  67108864 2000
powerlog --output results/stencil.csv    ./bin/stencil    4096 2000
powerlog --output results/nbody.csv      ./bin/nbody      65536 500
powerlog --output results/vecadd_sycl.csv ./bin/vecadd_sycl 67108864 2000
powerlog --output results/matmul_sycl.csv ./bin/matmul_sycl 2048 200

make run        # all of the above at their defaults, into results/
```

Two comparisons the set is built for — a hand-written kernel against the vendor
library, and a size sweep:

```bash
powerlog --output results/hand.csv   ./bin/matmul 4096 50
powerlog --output results/vendor.csv ./bin/gemm   4096 50

for n in 1024 2048 4096 8192; do
  powerlog --output results/matmul_$n.csv ./bin/matmul $n 200
done
```

If a run misbehaves — `n/a` energy, too few samples, a binary that will not
launch — see
[Troubleshooting](https://powerlog.readthedocs.io/en/latest/backends.html#troubleshooting).
