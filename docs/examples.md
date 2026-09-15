# Examples

## Example applications

The [apps/](https://github.com/arsho/powerlog/tree/main/apps) directory of the
repository contains small, self-contained GPU programs used to exercise
Powerlog. They cover several performance regimes, so their energy profiles
differ in instructive ways.

| App | Regime | Description |
| --- | ------ | ----------- |
| `vecadd` | Memory bandwidth | Element-wise vector addition |
| `matmul` | Compute | Tiled dense matrix multiply (shared memory) |
| `gemm` | Compute (tuned) | Vendor-library SGEMM (cuBLAS / hipBLAS) |
| `reduction` | Latency / sync | Shared-memory tree sum reduction |
| `stencil` | Memory, iterative | 2D five-point Jacobi heat diffusion |
| `nbody` | Compute (FMA heavy) | Direct O(N^2) gravitational N-body step |

SYCL ports of `vecadd` and `matmul` are provided as well, which run on Intel,
NVIDIA and AMD GPUs from a single source.

They are not installed by `pip install powerlog`; clone the repository to build
them.

```bash
git clone https://github.com/arsho/powerlog.git
cd powerlog/apps
make                  # auto-detects nvcc or hipcc
make sycl             # SYCL apps

powerlog ./bin/matmul 2048 200
make run              # profile every app into results/
```

{doc}`apps` documents every application, its two parameters and the exact
command to run each one.

## Comparing a kernel against the vendor library

```bash
powerlog --output hand.csv   ./bin/matmul 4096 20
powerlog --output vendor.csv ./bin/gemm   4096 20
```

```python
import pandas as pd

hand = pd.read_csv("hand.csv").iloc[0]
vendor = pd.read_csv("vendor.csv").iloc[0]

ratio = float(hand["Total Energy (J)"]) / float(vendor["Total Energy (J)"])
print(f"hand-written kernel uses {ratio:.2f}x the energy of the vendor GEMM")
```

## Sweeping a problem size

```python
from powerlog import measure_power

print(f"{'size':>6} {'time (s)':>10} {'energy (J)':>12} {'EDP':>12}")
for size in (1024, 2048, 4096, 8192):
    r = measure_power(["./bin/matmul", str(size)])
    print(f"{size:>6} {r.total_time_s:>10.2f} "
          f"{r.total_energy_j:>12.1f} {r.energy_delay_product:>12.1f}")
```

## Finding the most energy-efficient configuration

```python
from powerlog import measure_power

results = {}
for bodies in (32768, 65536, 131072, 262144):
    results[bodies] = measure_power(["./bin/nbody", str(bodies), "500"])

best_time = min(results, key=lambda k: results[k].total_time_s)
best_energy = min(results, key=lambda k: results[k].total_energy_j
                                         / (k * k))  # energy per interaction

print(f"fastest: {best_time} bodies")
print(f"most efficient: {best_energy} bodies")
```

The two are frequently not the same configuration, which is the main reason to
measure energy rather than infer it from runtime.

## Case study: Datalog engine comparison

The `datalog-engine-comparison/` directory contains a larger study that uses
Powerlog to compare five GPU-accelerated Datalog engines across two recursive
queries and seven graphs. It includes the measurement harness, the analysis
scripts, and the collected results; the engines are cloned from their own
repositories rather than vendored.

| Engine | Source |
| ------ | ------ |
| MNMGDatalog | <https://github.com/harp-lab/MNMGDatalog> |
| GPULog | <https://github.com/harp-lab/gdlog> |
| BJoin | <https://github.com/harp-lab/batch_joins> (release pending) |
| INLJoin | <https://github.com/harp-lab/MNMGDatalog> (`*_nl.cu`) |
| cuDF | <https://github.com/NVIDIA/cudf> |

The BJoin repository is not public yet; its results are included here and the
link starts working once it is released.

A representative finding: the CPU accounts for 32--55% of total energy depending
on the engine, so GPU-only accounting can misrank engines and understate total
energy by up to 2x. See `datalog-engine-comparison/README.md`.
