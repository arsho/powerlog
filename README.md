# Powerlog

[![PyPI version](https://badge.fury.io/py/powerlog.svg)](https://pypi.org/project/powerlog/)


**Powerlog** is a lightweight command-line tool and Python package to profile the energy consumption of a command-line program. It samples **GPU** power via `nvidia-smi` (NVML) and, optionally, **CPU-package** power via RAPL (`perf power/energy-pkg/`) in lockstep, and reports total energy usage, average power, and min/max readings for an *unmodified* program (no source instrumentation).

## Features

* Measures real-time GPU power draw using `nvidia-smi` (NVML)
* Optionally measures CPU-package energy via RAPL (`perf power/energy-pkg/`) with `--cpu`
* Whole-application harness: wraps an unmodified command as a subprocess and samples power on a fixed interval (default 100 ms) with negligible overhead
* Computes:

  * Total runtime
  * Total energy consumed (in Joules) — GPU, CPU, and their sum
  * CPU fraction of total energy (with `--cpu`)
  * Average (sampled and timed), min, and max power (Watts)
* Outputs both summary and raw samples as CSV
* Simple CLI interface, scales to all GPUs in a job
* Reports Avg Power Sampled (mean of all readings) and Avg Power Timed (energy divided by total time)

## Installation

Requires Python 3.6+ and NVIDIA's `nvidia-smi` available in your system PATH.

For CPU-package energy (`--cpu`) you additionally need Linux `perf` with access to
the RAPL `power/energy-pkg/` event. Unprivileged access requires
`kernel.perf_event_paranoid <= 0` (e.g. `sudo sysctl kernel.perf_event_paranoid=-1`),
or run under `sudo`. AMD EPYC and most Intel CPUs expose the package domain; some
platforms also expose DRAM. If the event is unavailable, CPU energy is reported as
`NaN` and only GPU energy is used.

Project page at the Python Package Index (PyPI): [https://pypi.org/project/powerlog/](https://pypi.org/project/powerlog/)

Install with pip:
```bash
pip install powerlog
```

## Usage

GPU only:

```bash
powerlog --output power_report.csv --gpu 1 ./my_gpu_program arg1 arg2
```

GPU + CPU-package energy (RAPL):

```bash
powerlog --cpu --output power_report.csv --gpu 1 ./my_gpu_program arg1 arg2
```

### CLI Options

| Argument     | Description                                          |
| ------------ | ---------------------------------------------------- |
| `--output`   | Base name for the output CSV files                   |
| `--gpu`      | Number of GPUs to monitor (default: 1)               |
| `--cpu`      | Also measure CPU-package energy via RAPL (`perf`)    |
| `cmd`        | Command and arguments to run and profile             |

## Output

If `--output power.csv` is specified:

* `power.csv`: Summary of runtime, energy, and power stats
* `power_samples.csv`: Raw timestamped GPU power draw samples

With `--cpu`, the summary CSV includes additional columns:

```text
Total Time (s),GPU Energy (J),CPU Energy (J),Total Energy (J),CPU Fraction,Avg Power Sampled (W),Avg Power Timed (W),Min Power Sampled (W),Max Power Sampled (W)
```

## Example

```bash
powerlog --output matrix_power.csv --gpu 1 nvidia-smi
```

This will generate `matrix_power.csv` and `matrix_power_samples.csv`.

To also capture CPU-package energy, add `--cpu`:

```bash
powerlog --cpu --output matrix_power.csv --gpu 1 ./my_gpu_program
```

Demo content of `matrix_power.csv`:
```text
Total Time (s),Total Energy (J),Avg Power Sampled (W),Avg Power Timed (W),Min Power Sampled (W),Max Power Sampled (W)
0.1001,1.2856,12.8400,12.8400,12.84,12.84
```

Demo content of `matrix_power_samples.csv`:
```text
Timestamp (ns),Power Draw (W)
1752198440220994393,12.84
```

## Dependencies

* Python standard library (`subprocess`, `argparse`, `time`, `csv`, `tempfile`, `os`)
* NVIDIA GPU with drivers and `nvidia-smi` tool
* (Optional, for `--cpu`) Linux `perf` with RAPL `power/energy-pkg/` access

## How power and energy are calculated?
### Power log collection
Powerlog launches your program as a subprocess and, from the parent process,
samples power at regular intervals (default: every 0.1 seconds) until the program
exits. It samples two sources in lockstep against the same wall clock:

* **GPU** power draw from NVML via `nvidia-smi` (summed over the requested GPUs).
* **CPU-package** energy from RAPL, by wrapping the command in
  `perf stat -e power/energy-pkg/` (only when `--cpu` is given).

## Total energy consumption computation

GPU energy ***E<sub>gpu</sub>*** (in Joules) is computed as
$$
E_{gpu} = \sum_{i=1}^N P_i \cdot \Delta t_i
$$

where:

- **N**: total number of sampling intervals  
- **P<sub>i</sub>**: GPU power draw (Watts) at interval *i*  
- **Δt<sub>i</sub>**: elapsed time (seconds) between sample *i* and sample *i-1*

CPU-package energy ***E<sub>cpu</sub>*** is read directly from RAPL (`perf`).
The reported **total energy** is:
$$
E_{total} = E_{gpu} + E_{cpu}
$$
and the **CPU fraction** is *E<sub>cpu</sub> / E<sub>total</sub>*.

> Note on biases: `nvidia-smi` uses a duty-cycled sensor that can bias absolute
> GPU energy, and RAPL reports package energy (cores + uncore). Because runs on
> the same hardware share identical sampling, these biases do not affect
> *relative* comparisons across programs/engines.

## Example applications and paper results

Powerlog was built for and used in the first heterogeneous CPU–GPU energy
characterization of GPU-powered Datalog engines. In that study, Powerlog
profiles five unmodified engines end to end (I/O, host–device transfers, kernel
launches, synchronization, and fixed-point iterations), capturing energy that
per-kernel tools miss.

### Engines profiled

| Engine        | Join strategy                              | Data structure              |
| ------------- | ------------------------------------------ | --------------------------- |
| **GPULog**    | Sorted hash join                           | Hash-indexed sorted array (HISA) |
| **MNMGDatalog** | Radix hash join (open-addressing, linear probing) | GPU hash table         |
| **cuDF**      | DataFrame merge (RAPIDS)                    | Columnar Python DataFrame   |
| **BJoin**     | Batch join with GPU buffer reuse (RMM)     | HISA + memory pooling       |
| **INLJoin**   | Index nested-loop join                      | GPU struct array            |

### Workloads and datasets

* **Queries**: Transitive Closure (TC) and Same Generation (SG) — recursive,
  fixed-point graph workloads.
* **Datasets** (from [SNAP](https://snap.stanford.edu/data/) and
  [SuiteSparse](https://sparse.tamu.edu/)): `fe_body`, `sf`, `usroads`, `vsp`,
  `ca_hepth`, `fe_sphere`, `loc-brightkite`.

### Measurement setup

* **Single-GPU energy** (GPU + CPU): JLSE node — CPU AMD EPYC 7532, GPU NVIDIA
  A100 40 GB; CPU-package energy via RAPL (`perf`).
* **Multi-GPU scaling** (GPU energy only): Polaris — 4× NVIDIA A100 per node.

### Headline findings

* **Engine choice alone changes total energy by up to ~3×**; the fastest
  configuration is not always the most energy-efficient.
* **The CPU package is a sizable, engine-dependent share: 32–55% of total
  energy.** CPU package power is nearly constant (~75–79 W) while GPU power varies
  (~64–167 W) with utilization, so GPU-underutilizing engines can become
  CPU-dominated on large graphs. GPU-only accounting can understate energy by up
  to ~2×.
* **Multi-GPU scaling (1→4 GPUs)** reduces time-to-solution by up to ~2.9× but
  *increases* energy by 24–42% (e.g., TC/usroads 8.0→9.8 kJ, SG/vsp 9.6→13.6 kJ).

### Example: measured GPU/CPU energy (single A100, Joules; lower is better)

Values shown as `GPU/CPU` energy in Joules. `OOM` = out of memory.

**Transitive Closure (TC)**

| Dataset  | GPULog     | MNMGDatalog | cuDF        | BJoin           | INLJoin    |
| -------- | ---------- | ----------- | ----------- | --------------- | ---------- |
| fe_body  | 443/249    | 348/402     | 6814/6624   | **357/249**     | 383/381    |
| sf       | **273/201**| 261/259     | 4626/4703   | 272/213         | 265/275    |
| usroads  | 5885/2754  | 5091/5804   | OOM         | **3821/1837**   | 5052/5819  |
| vsp      | 6967/3387  | 5325/6291   | OOM         | **3890/1896**   | 5493/6290  |

**Same Generation (SG)**

| Dataset        | GPULog     | MNMGDatalog   | cuDF        | BJoin         | INLJoin   |
| -------------- | ---------- | ------------- | ----------- | ------------- | --------- |
| ca_hepth       | 486/255    | **147/107**   | 538/652     | 405/278       | 169/105   |
| fe_body        | 1779/1000  | 932/793       | OOM         | **1168/547**  | 975/792   |
| fe_sphere      | 816/451    | **426/356**   | 5908/5281   | 582/332       | 436/355   |
| loc-brightkite | 1147/555   | **337/183**   | 1303/1324   | 897/487       | 340/182   |

### Multi-GPU scaling (MNMGDatalog, GPU energy)

| Workload (dataset) | Metric     | 1 GPU     | 2 GPUs | 4 GPUs |
| ------------------ | ---------- | --------- | ------ | ------ |
| TC (usroads)       | Energy (J) | **7964**  | 8282   | 9848   |
| SG (vsp)           | Energy (J) | **9630**  | 12405  | 13648  |

## Development

### Local Testing

To test Powerlog locally during development (before releasing to PyPI), you can install your package in "editable" mode:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Publishing to PyPI
When the package is ready to publish (or update) Powerlog on PyPI, use the following commands:

```
python -m pip install --upgrade build
python3 -m build
python3 -m pip install --upgrade twine
twine upload dist/*
```
This will build the distribution files (.tar.gz and .whl) and upload them to PyPI.

It requires API token for authentication.

### Changelog

See the [Changelog.md](Changelog.md) file in this repository for version history and release notes.

## License

MIT License

## Acknowledgments

- Developed as part of GPU power-efficiency profiling experiments in Datalog-based engines.
- Inspired by the [EUMaster4HPC](https://eumaster4hpc.uni.lu/) 
