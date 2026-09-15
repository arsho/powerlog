# Quick Start

## Measuring a program

Prefix any command with `powerlog`. CPU and GPU energy are both measured by
default, so no flags are required:

```bash
powerlog ./my_program --arg value
```

```text
================================================================
                    POWERLOG ENERGY SUMMARY
================================================================
Command                 ./my_program --arg value
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

The program has to be launchable: give a path (`./my_program`) unless it is on
`PATH`. Powerlog resolves it before measuring and refuses to start otherwise.

Powerlog exits with the exit status of the profiled program, so it composes
cleanly inside scripts and job submissions.

## Give the run enough time

Power is sampled every 100 ms by default, so a run of a few seconds is the
minimum for a meaningful integral. A sub-second run mostly measures process
start-up at the device's idle power, and Powerlog says so:

```text
note: Only 3 power sample(s) in 0.44 s. GPU energy is integrated from too few
points to be meaningful, and a run this short is dominated by process start-up
rather than by the workload. Increase the workload or lower --interval.
```

Either enlarge the workload or sample faster with `--interval 0.02`. See
{doc}`methodology` for the trade-off.

## Choosing the output file

Without `--output` the results go to `powerlog_output.csv` and
`powerlog_output_samples.csv` in the working directory:

```bash
powerlog --output run01.csv ./my_program      # run01.csv + run01_samples.csv
powerlog --no-csv ./my_program                # print only, write nothing
```

## Selecting domains and devices

```bash
powerlog -m gpu ./my_program             # GPU energy only
powerlog -m cpu ./my_program             # CPU energy only
powerlog --gpu 4 ./my_program            # sum the first 4 GPUs
powerlog --interval 0.05 ./my_program    # sample every 50 ms
```

Powerlog measures the node it runs on and does not aggregate across nodes. If
your program is launched through a wrapper, wrap the launcher so that the whole
job is covered:

```bash
powerlog --gpu 4 ./launcher ./my_program
```

## Using the Python API

{func}`powerlog.measure_power` returns a
{class}`~powerlog.MeasurementResult` with the full breakdown:

```python
from powerlog import measure_power

result = measure_power(["./my_program", "--arg", "value"])

print(f"runtime  {result.total_time_s:.2f} s")
print(f"cpu      {result.cpu_energy_j:.1f} J ({result.cpu_fraction:.1%})")
print(f"gpu      {result.gpu_energy_j:.1f} J ({result.gpu_fraction:.1%})")
print(f"total    {result.total_energy_j:.1f} J")
print(f"edp      {result.energy_delay_product:.1f} J*s")
```

Energy attributes are `None` when a domain could not be measured, which lets you
tell "not measured" apart from "zero energy":

```python
if result.cpu_energy_j is None:
    print("CPU energy unavailable:", *result.notes, sep="\n  ")
```

## Comparing configurations

```python
from powerlog import measure_power

for size in (1024, 2048, 4096):
    r = measure_power(["./matmul", str(size)])
    print(f"{size:>5}  {r.total_time_s:7.2f} s  {r.total_energy_j:9.1f} J")
```

## Writing results yourself

```python
from powerlog import measure_power, write_summary_csv, write_samples_csv

result = measure_power(["./matmul", "2048"])
write_summary_csv("matmul.csv", result)
write_samples_csv("matmul_samples.csv", result)
```

## Plotting the power trace

```python
import pandas as pd

df = pd.read_csv("powerlog_output_samples.csv")
df.plot(x="Elapsed (s)", y=["CPU Power (W)", "GPU Power (W)"])
```
