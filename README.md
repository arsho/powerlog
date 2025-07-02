# powerlog

**Powerlog** is a lightweight command-line tool and Python package to profile GPU power consumption during the execution of a command-line program. It uses `nvidia-smi` to sample power draw at regular intervals and reports total energy usage, average power, and min/max readings.

## Features

* Measures real-time GPU power draw using `nvidia-smi`
* Computes:

  * Total runtime
  * Total energy consumed (in Joules)
  * Average, min, and max power (Watts)
* Outputs both summary and raw samples as CSV
* Simple CLI interface

## Installation

Requires Python 3.6+ and NVIDIA's `nvidia-smi` available in your system PATH.

```bash
pip install powerlog
```

## Usage

```bash
powerlog --output power_report.csv --gpu 2 ./my_gpu_program arg1 arg2
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
powerlog --output matrix_power.csv --gpu 1 ./matrix_multiply data/input.bin
powerlog --output matrix_power.csv --gpu 1 nvidia-smi
```

## Dependencies

* Python standard library (`subprocess`, `argparse`, `time`, `csv`)
* NVIDIA GPU with drivers and `nvidia-smi` tool

## License

MIT License

## Acknowledgments

Developed as part of GPU power-efficiency profiling experiments in Datalog-based engines.
