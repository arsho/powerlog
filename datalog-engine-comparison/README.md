# Datalog Engine Energy Comparison

A cross-engine CPU--GPU energy study of five GPU-accelerated Datalog engines,
built with Powerlog. This directory holds the measurement harness, the analysis
scripts, and the collected results.

This is a case study that exercises Powerlog on a real workload. It is
independent of the Powerlog library itself: nothing here is required to use
Powerlog.

## Contents

```
datalog-engine-comparison/
├── harness/        measurement drivers (energy sweeps, Nsight counter runs)
├── analysis/       scripts that turn raw CSVs into tables and figures
├── results/        collected measurements
│   ├── cpugpu/{tc,sg}/<Dataset>_<Engine>.csv   per-run raw output
│   ├── energy_summary.csv                      combined per-engine table
│   └── multi_gpu_scaling.csv                   1/2/4 GPU scaling
├── datasets/       manifest and download script (graphs are not vendored)
└── COUNTERS_REPRODUCIBILITY.md                 hardware counter methodology
```

## Engines

No engine source is vendored here. Each engine is developed in its own
repository; this directory only holds the measurement harness and the results.

| Engine        | Join strategy                                     | Data structure                   | Source |
| ------------- | ------------------------------------------------- | -------------------------------- | ------ |
| `MNMGDatalog` | Radix hash join, open addressing + linear probing | GPU hash table                   | [harp-lab/MNMGDatalog](https://github.com/harp-lab/MNMGDatalog) (`tc.cu`, `sg.cu`) |
| `GPULog`      | Sorted hash join                                  | Hash-indexed sorted array (HISA) | [harp-lab/gdlog](https://github.com/harp-lab/gdlog) |
| `BJoin`       | Batch join with buffer reuse (RMM)                | HISA + memory pooling            | [harp-lab/batch_joins](https://github.com/harp-lab/batch_joins) (release pending) |
| `INLJoin`     | Index nested-loop join                            | GPU struct array                 | [harp-lab/MNMGDatalog](https://github.com/harp-lab/MNMGDatalog) (`tc_nl.cu`, `sg_nl.cu`) |
| `cuDF`        | DataFrame merge (RAPIDS)                          | Columnar DataFrame               | [harp-lab/MNMGDatalog](https://github.com/harp-lab/MNMGDatalog) (`related/cudf_programs/`) |

Three checkouts cover all five engines, since MNMGDatalog hosts the INLJoin and
cuDF implementations as well.

## Workloads

Two recursive fixed-point queries:

* **TC** -- transitive closure, on `fe_body`, `sf`, `usroads`, `vsp`.
* **SG** -- same generation, on `ca_hepth`, `fe_body`, `fe_sphere`,
  `loc-brightkite`.

The graphs ship inside the engine repositories, already converted to each
engine's input format -- there is nothing to download. See
[datasets/README.md](datasets/README.md) for the per-engine file mapping and
`datasets/datasets.csv` for graph sizes and upstream provenance.

## Measurement setup

| Axis                | Machine                                          | Domains measured |
| ------------------- | ------------------------------------------------ | ---------------- |
| Single-GPU energy   | AMD EPYC 7532 + 1x NVIDIA A100 40 GB              | CPU (RAPL) + GPU |
| Multi-GPU scaling   | 4x NVIDIA A100 per node                           | GPU              |

Metrics reported:

* **Total energy** -- CPU package plus GPU, in Joules.
* **CPU fraction** -- the CPU share of total energy.
* **Instructions per Joule** -- total GPU instructions executed
  (`sm__inst_executed.sum`, via Nsight Compute) divided by GPU energy. FLOPS-based
  efficiency metrics are a poor fit for Datalog, which is dominated by integer
  joins, hashing and data movement.
* **Energy--delay product (EDP)** -- energy times runtime, to expose the
  energy/time trade-off.

## Reproducing

### 1. Clone and build the engines

Clone the three repositories side by side. `harness/run_cpu_gpu_energy.sh`
expects them at `$HOME` by default; override `GDLOG` and `BJOIN` at the top of
the script if you put them elsewhere.

```bash
cd ~
git clone https://github.com/harp-lab/MNMGDatalog.git
git clone https://github.com/harp-lab/gdlog.git
git clone https://github.com/harp-lab/batch_joins.git   # release pending
```

`batch_joins` is not public yet, so that last clone will fail for now. The
other four engines are unaffected: skip the BJoin steps below and the harness
still reproduces everything else. Its measured results are already in
`results/`.

Build each one following its own README. In outline:

```bash
# MNMGDatalog + INLJoin -- CUDA + MPI, builds tc.out / sg.out / tc_nl.out / sg_nl.out
cd ~/MNMGDatalog && make

# GPULog -- CMake, builds build/TC and build/SG
cd ~/gdlog && mkdir -p build && cd build && cmake .. && make -j

# BJoin -- CMake, builds build/TC and build/SG
cd ~/batch_joins && mkdir -p build && cd build && cmake .. && make -j

# cuDF -- no build step, needs a RAPIDS environment
conda install -c rapidsai -c conda-forge -c nvidia cudf
```

Requirements: CUDA 12.x, an MPI implementation, CMake 3.18+, and RAPIDS cuDF for
the DataFrame baseline.

The graphs come with these checkouts, so there is nothing to download. BJoin is
the one exception: `batch_joins` ships no `data/` directory, so copy its inputs
across as described in [datasets/README.md](datasets/README.md).

### 2. Run the energy sweep

```bash
# quick sanity check of the environment and paths
bash harness/dryrun_cpu_gpu.sh

# full sweep; resumable, skips runs whose CSV already exists
bash harness/run_cpu_gpu_energy.sh
```

Results land in `results/cpugpu/{tc,sg}/<Dataset>_<Engine>.csv`.

The sweep is just a loop over `powerlog` invocations. Each engine is profiled
the same way, with CPU and GPU energy measured by default:

```bash
# MNMGDatalog (TC on usroads)
powerlog --output results/cpugpu/tc/usroads_MNMGDatalog.csv \
    mpiexec -n 1 ./tc.out data/data_165435.bin 0 1 1

# INLJoin -- same repo, non-hash binary
powerlog --output results/cpugpu/tc/usroads_INLJoin.csv \
    mpiexec -n 1 ./tc_nl.out data/data_165435.bin 0 1 1

# GPULog -- run from the gdlog checkout
powerlog --output results/cpugpu/tc/usroads_GPULog.csv \
    ./build/TC ./data/usroad/edge.facts 0

# BJoin -- run from batch_joins/build; last arg is % of free GPU memory to pool
powerlog --output results/cpugpu/tc/usroads_BJoin.csv \
    ./TC ../data/usroads.txt 90

# cuDF -- run from the MNMGDatalog checkout
powerlog --output results/cpugpu/tc/sf_cuDF.csv \
    python related/cudf_programs/tc.py data/data_223001.txt
```

Swap `tc` for `sg` (and `TC` for `SG`) to run the Same Generation query.

### 3. Collect the hardware counters

Instruction counts come from a separate Nsight Compute run, because kernel replay
perturbs timing (but not the instruction count):

```bash
bash harness/run_ncu_instructions.sh
```

See [COUNTERS_REPRODUCIBILITY.md](COUNTERS_REPRODUCIBILITY.md) for the exact
counter definitions and caveats.

### 4. Build the tables

```bash
python analysis/cpu_gpu_energy_tables.py results/cpugpu/tc
python analysis/cpu_gpu_energy_tables.py results/cpugpu/sg
python analysis/instructions_per_joule.py
python analysis/make_energy_split.py
```

## Results

### Energy per engine (single A100, Joules; lower is better)

Reported as `GPU/CPU`. `OOM` marks runs that exhausted GPU memory. The full data,
including CPU fractions and instruction efficiency, is in
`results/energy_summary.csv`.

**Transitive Closure**

| Dataset | GPULog      | MNMGDatalog | cuDF      | BJoin         | INLJoin   |
| ------- | ----------- | ----------- | --------- | ------------- | --------- |
| fe_body | 443/249     | 348/402     | 6814/6624 | **357/249**   | 383/381   |
| sf      | **273/201** | 261/259     | 4626/4703 | 272/213       | 265/275   |
| usroads | 5885/2754   | 5091/5804   | OOM       | **3821/1837** | 5052/5819 |
| vsp     | 6967/3387   | 5325/6291   | OOM       | **3890/1896** | 5493/6290 |

**Same Generation**

| Dataset        | GPULog    | MNMGDatalog | cuDF      | BJoin        | INLJoin |
| -------------- | --------- | ----------- | --------- | ------------ | ------- |
| ca_hepth       | 486/255   | **147/107** | 538/652   | 405/278      | 169/105 |
| fe_body        | 1779/1000 | 932/793     | OOM       | **1168/547** | 975/792 |
| fe_sphere      | 816/451   | **426/356** | 5908/5281 | 582/332      | 436/355 |
| loc-brightkite | 1147/555  | **337/183** | 1303/1324 | 897/487      | 340/182 |

### Multi-GPU scaling (MNMGDatalog)

| Workload       | Metric     | 1 GPU    | 2 GPUs | 4 GPUs |
| -------------- | ---------- | -------- | ------ | ------ |
| TC (usroads)   | Energy (J) | **7964** | 8282   | 9848   |
| SG (vsp)       | Energy (J) | **9630** | 12405  | 13648  |

### Observations

* **No engine wins everywhere.** Engine choice alone changes total energy by up
  to about 3x on the same query and dataset; `cuDF` is consistently highest, by up
  to an order of magnitude.
* **The fastest configuration is not always the most energy-efficient.**
* **The CPU is a large, engine-dependent share of total energy: 32--55%.** CPU
  package power stays near 75--79 W while GPU power swings between roughly
  64 W and 167 W with utilisation. Engines that underutilise the GPU become
  CPU-dominated on large graphs -- on `usroads`, MNMGDatalog spends 5804 J on the
  CPU against 5091 J on the GPU. GPU-only accounting misranks engines and can
  understate total energy by up to 2x.
* **Scaling out trades energy for latency.** Going from 1 to 4 GPUs cuts runtime
  by up to 2.9x but raises energy by 24--42%, as aggregate power scales
  super-linearly and communication adds its own cost.

## References

### Engines

* **MNMGDatalog** -- <https://github.com/harp-lab/MNMGDatalog>
  Multi-node multi-GPU Datalog engine using a radix hash join over an
  open-addressing GPU hash table. Also hosts the INLJoin and cuDF
  implementations used here.
* **GPULog** (`gdlog`) -- <https://github.com/harp-lab/gdlog>
  GPU Datalog engine built on a hash-indexed sorted array (HISA).
* **BJoin** (`batch_joins`) -- <https://github.com/harp-lab/batch_joins>
  (release pending) Batch-join variant of GPULog with GPU buffer reuse via
  RAPIDS Memory Manager.
* **RAPIDS cuDF** -- <https://github.com/NVIDIA/cudf>
  GPU DataFrame library providing the `merge`-based baseline.

### Tooling

* **Powerlog** -- <https://github.com/arsho/powerlog>
  The energy measurement harness used throughout; see the
  [documentation](https://powerlog.readthedocs.io/).
* **Nsight Compute** -- <https://developer.nvidia.com/nsight-compute>
  Source of the `sm__inst_executed.sum` counter used for instructions per joule.

### Datasets

* **SuiteSparse Matrix Collection** -- <https://sparse.tamu.edu>
  `fe_body`, `fe_sphere`, `vsp`, `sf`, `usroads`.
* **SNAP** -- <https://snap.stanford.edu/data>
  `ca_hepth`, `loc-brightkite`.

Per-graph sources and sizes are listed in `datasets/datasets.csv`.
