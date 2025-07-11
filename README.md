# Powerlog

[![PyPI version](https://badge.fury.io/py/powerlog.svg)](https://pypi.org/project/powerlog/)


**Powerlog** is a lightweight command-line tool and Python package to profile Nvidia GPU power consumption during the execution of a command-line program. It uses `nvidia-smi` to sample power draw at regular intervals and reports total energy usage, average power, and min/max readings.

## Features

* Measures real-time GPU power draw using `nvidia-smi`
* Computes:

  * Total runtime
  * Total energy consumed (in Joules)
  * Average (sampled and timed), min, and max power (Watts)
* Outputs both summary and raw samples as CSV
* Simple CLI interface
* Reports Avg Power Sampled (mean of all readings) and Avg Power Timed (energy divided by total time)

## Installation

Requires Python 3.6+ and NVIDIA's `nvidia-smi` available in your system PATH.

Project page at the Python Package Index (PyPI): [https://pypi.org/project/powerlog/](https://pypi.org/project/powerlog/)

Install with pip:
```bash
pip install powerlog
```

## Usage

```bash
powerlog --output power_report.csv --gpu 1 ./my_gpu_program arg1 arg2
```

### CLI Options

| Argument     | Description                                 |
| ------------ | ------------------------------------------- |
| `--output`   | Base name for the output CSV files          |
| `--gpu`      | Number of GPUs to monitor (default: 1)      |
| `cmd`        | Command and arguments to run and profile    |

## Output

If `--output power.csv` is specified:

* `power.csv`: Summary of runtime, energy, and power stats
* `power_samples.csv`: Raw timestamped power draw samples

## Example

```bash
powerlog --output matrix_power.csv --gpu 1 nvidia-smi
```

This will generate `matrix_power.csv` and `matrix_power_samples.csv`

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

* Python standard library (`subprocess`, `argparse`, `time`, `csv`)
* NVIDIA GPU with drivers and `nvidia-smi` tool

## How power and energy are calculated?
### Power log collection  
Powerlog uses `nvidia-smi` to measure GPU power draw at regular intervals (default: every 0.1 seconds). The Python wrapper script automatically runs this measurement loop from the start to the end of your program.

## Total energy consumption computation

Total energy ***E*** (in Joules) is computed as
$$
E = \sum_{i=1}^N P_i \cdot \Delta t_i
$$

where:

- **N**: total number of sampling intervals  
- **P<sub>i</sub>**: GPU power draw (Watts) at interval *i*  
- **Δt<sub>i</sub>**: elapsed time (seconds) between sample *i* and sample *i-1*

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
