# Powerlog Example Applications

A set of small, self-contained GPU programs used to exercise and demonstrate
Powerlog. They span the usual performance regimes (bandwidth bound, compute
bound, latency bound, iterative) so that the resulting energy profiles differ in
interesting ways.

Every program takes the same two optional arguments:

```
./<app> [size] [iterations]
```

Increase `iterations` to make a run long enough for stable sampling; a runtime of
at least a few seconds is recommended at the default 100 ms sampling interval.

## Applications

| App            | Source                   | Regime                | Default size | Description |
| -------------- | ------------------------ | --------------------- | ------------ | ----------- |
| `vecadd`       | `cuda/vecadd.cu`         | Memory bandwidth      | 2^26 elems   | Element-wise vector addition with a grid-stride loop. |
| `matmul`       | `cuda/matmul.cu`         | Compute               | 2048x2048    | Tiled dense matrix multiply using shared memory. |
| `gemm`         | `cuda/gemm.cu`           | Compute (tuned)       | 4096x4096    | Vendor-library SGEMM (cuBLAS / hipBLAS). |
| `reduction`    | `cuda/reduction.cu`      | Latency / sync        | 2^26 elems   | Shared-memory tree sum reduction. |
| `stencil`      | `cuda/stencil.cu`        | Memory, iterative     | 4096x4096    | 2D five-point Jacobi heat diffusion. |
| `nbody`        | `cuda/nbody.cu`          | Compute (FMA heavy)   | 65536 bodies | Direct O(N^2) gravitational N-body step. |
| `vecadd_sycl`  | `sycl/vecadd_sycl.cpp`   | Memory bandwidth      | 2^26 elems   | SYCL port of `vecadd`. |
| `matmul_sycl`  | `sycl/matmul_sycl.cpp`   | Compute               | 2048x2048    | SYCL port of `matmul`. |

The `cuda/` sources build unchanged for both NVIDIA and AMD: `cuda/gpu_common.h`
maps the CUDA runtime names onto HIP when compiled with `hipcc`.

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
```

Binaries are written to `apps/bin/`. Requirements:

* NVIDIA: CUDA toolkit (`nvcc`); `gemm` also needs cuBLAS.
* AMD: ROCm (`hipcc`); `gemm` also needs hipBLAS.
* SYCL: Intel oneAPI (`icpx`) or an `-fsycl` capable `clang++`.

## Running under Powerlog

Powerlog measures CPU and GPU energy by default, so no flags are needed:

```bash
powerlog ./bin/matmul
```

```
================================================================
                    POWERLOG ENERGY SUMMARY
================================================================
Command                 ./bin/matmul
Exit code               0
Runtime (s)             12.4180
Samples                 124
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
CPU backend             CPU package (RAPL powercap sysfs), 2 package domain(s)
GPU backend             NVIDIA GPU (nvidia-smi / NVML) (1 device(s))
================================================================
Summary written to: powerlog_output.csv
Samples written to: powerlog_output_samples.csv
```

### Common invocations

Choose the output file:

```bash
powerlog --output matmul_2048.csv ./bin/matmul 2048 50
```

Sweep a problem size:

```bash
for n in 1024 2048 4096; do
  powerlog --output results/matmul_$n.csv ./bin/matmul $n 50
done
```

Compare a hand-written kernel against the vendor library:

```bash
powerlog --output results/matmul.csv ./bin/matmul 4096 20
powerlog --output results/gemm.csv   ./bin/gemm   4096 20
```

Profile all apps at once:

```bash
make run        # writes results/<app>.csv and results/<app>_samples.csv
```

### Multi-GPU

The example apps use a single GPU. On a multi-GPU node, `--gpu N` limits how many
devices are summed:

```bash
powerlog --gpu 1 ./bin/nbody 131072 100
```

### Cross-vendor runs

The backend is detected automatically, but it can be pinned:

```bash
powerlog --gpu-backend nvidia ./bin/matmul      # NVML
powerlog --gpu-backend amd    ./bin/matmul      # ROCm SMI
powerlog --gpu-backend intel  ./bin/matmul_sycl # Level Zero via xpu-smi
```

Check what is visible on the current machine:

```bash
powerlog --list-backends
```

### If CPU energy shows `n/a`

CPU energy comes from RAPL. Grant unprivileged access with either

```bash
sudo sysctl kernel.perf_event_paranoid=-1     # enables the perf backend
sudo chmod -R a+r /sys/class/powercap          # enables the sysfs backend
```

Powerlog still reports GPU energy and runtime when RAPL is unavailable.

## Output files

Each run writes two CSVs:

* `<name>.csv` -- one summary row with the CPU/GPU/total energy breakdown.
* `<name>_samples.csv` -- the power trace, one row per sampling interval, with a
  column per GPU device.

The sample trace is convenient for plotting power over time:

```python
import pandas as pd

df = pd.read_csv("powerlog_output_samples.csv")
df.plot(x="Elapsed (s)", y=["CPU Power (W)", "GPU Power (W)"])
```
