# Quick Start

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
Total time (s)          12.4180  (wall clock)
CPU                     AMD EPYC 7532 32-Core Processor
GPU                     NVIDIA A100-PCIE-40GB
----------------------------------------------------------------
Domain            Energy (J)   Share (%)   Avg Power (W)
----------------------------------------------------------------
CPU                 962.4013       31.05         77.5005
GPU                2136.7742       68.95        172.0707
----------------------------------------------------------------
TOTAL              3099.1755
EDP (J*s)         38485.5614
  avg power = energy / total time,  EDP = energy x total time
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

`Total time` is wall clock, so it includes process start-up; average power and
EDP are derived from it rather than sampled. The `CPU power` and `GPU power`
lines report the extremes of the *sampled* trace, so they appear only for a
domain that is traced — with the `perf` CPU backend there is no CPU trace and
that line is absent. {doc}`output` explains every line, and the two CSVs written
alongside.

Powerlog exits with the profiled program's exit status, so it composes cleanly
inside scripts and job submissions.

## Give the run enough time

Power is sampled every 100 ms, so a run of at least a few seconds is the minimum
for a meaningful integral. A sub-second run mostly measures process start-up at
the device's idle power, and Powerlog says so:

```text
note: Only 3 power sample(s) in 0.44 s. GPU energy is integrated from too few
points to be meaningful, and a run this short is dominated by process start-up
rather than by the workload. Increase the workload or lower --interval.
```

Enlarge the workload, or sample faster with `--interval 0.02`. See
{doc}`methodology`.

## Common invocations

```bash
powerlog --output run01.csv ./my_program   # name the output files
powerlog --no-csv ./my_program             # print only, write nothing
powerlog -m gpu ./my_program               # GPU energy only
powerlog --gpu 4 ./my_program              # sum the first 4 GPUs
powerlog --interval 0.02 ./my_program      # sample every 20 ms
```

The program has to be launchable: give a path (`./my_program`) unless it is on
`PATH`. Powerlog resolves it before measuring and refuses to start otherwise.

If your program is launched through a wrapper, wrap the launcher so the whole
job is covered:

```bash
powerlog --gpu 4 ./launcher ./my_program
```

Full option reference: {doc}`cli`.
