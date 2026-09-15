# Example Applications

Small, self-contained GPU programs used to exercise Powerlog. They span the
usual performance regimes, so their energy profiles differ in instructive ways.

They are **not** part of the wheel: they are C++/CUDA sources that must be
compiled for your GPU. If you want to run them, they are in the
[apps/](https://github.com/arsho/powerlog/tree/main/apps) directory of the
repository.

```bash
git clone https://github.com/arsho/powerlog.git
cd powerlog/apps
make                  # nvcc if present, else hipcc; binaries land in bin/
make sycl             # SYCL apps (icpx, else clang++ -fsycl)
make help             # show the detected toolchain
```

`gemm` additionally needs cuBLAS (NVIDIA) or hipBLAS (AMD). The `cuda/` sources
build unchanged for both vendors: `cuda/gpu_common.h` maps the CUDA runtime
names onto HIP under `hipcc`.

## Parameters

Every program takes the same two positional, optional arguments:

```text
./<app> [size] [iterations]
```

`size`
: What is computed over — a matrix dimension, a grid dimension, an element
  count or a body count, per the table below.

`iterations`
: How many times the kernel is launched. Changes the amount of work, not the
  result. This is the knob to turn for a run long enough to sample well.

Both are parsed with `strtol`; anything missing, non-numeric or `<= 0` falls
back to the default, so `./matmul abc` runs the default 2048 case.

| App | `size` means | Default size | Default iters | Regime and kernel |
| --- | ------------ | ------------ | ------------- | ----------------- |
| `vecadd` | float elements per vector | `67108864` | `200` | Memory bandwidth; element-wise `c = a + b` |
| `matmul` | dimension of an `n x n` product | `2048` | `50` | Compute; 16x16 shared-memory tiled multiply |
| `gemm` | dimension of an `n x n` product | `4096` | `50` | Compute, vendor tuned; cuBLAS/hipBLAS SGEMM |
| `reduction` | float elements summed | `67108864` | `300` | Latency/sync; shared-memory tree sum |
| `stencil` | dimension of an `n x n` grid | `4096` | `500` | Memory, iterative; 2D five-point Jacobi |
| `nbody` | number of bodies | `65536` | `100` | Compute, FMA heavy; direct O(N^2) gravitation |
| `vecadd_sycl` | float elements per vector | `67108864` | `200` | SYCL port of `vecadd` |
| `matmul_sycl` | dimension of an `n x n` product | `2048` | `50` | SYCL port of `matmul` |

Each prints a banner, the work done and a checksum, and exits non-zero if
verification fails:

```text
[matmul] size=2048 iterations=50
[matmul] total work=858.99 GFLOP
[matmul] checksum=2048.000000 verification=PASS
```

## Running them

The generic form, from `apps/`. The `./bin/` prefix is required — neither `bin`
nor the current directory is on `PATH`:

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

If a run misbehaves, see the troubleshooting section of {doc}`backends`.

## Datalog case study

Beyond these micro-benchmarks, the repository carries a larger study that uses
Powerlog to compare five GPU-accelerated Datalog engines across two recursive
queries and seven graphs, with the measurement harness, the analysis scripts and
the collected results. A representative finding: the CPU accounts for 32–55% of
total energy depending on the engine, so GPU-only accounting can misrank engines
and understate total energy by up to 2x.

It is not documented here because it is a dataset and a set of shell scripts
rather than a feature of the tool. Its guide lives with the material, on GitHub:
[datalog-engine-comparison/README.md](https://github.com/arsho/powerlog/blob/main/datalog-engine-comparison/README.md).
