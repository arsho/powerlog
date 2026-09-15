# Powerlog

A command-line tool that measures the CPU and GPU energy consumed by an
unmodified program.

```bash
pip install powerlog
powerlog ./my_program --arg value
```

Powerlog launches the target as a subprocess and samples per-GPU power from NVML
and CPU-package power from RAPL in lockstep, time-stamping both against the same
wall clock. Nothing is recompiled and no source is instrumented, so the trace
spans I/O, host-device transfers, kernel launches and synchronization — the
energy per-kernel tools miss. Measuring only the GPU is not enough either: the
CPU package is frequently a large, workload-dependent share of the total.

Any domain the platform does not expose is reported as `n/a` rather than failing
the run.

```{toctree}
:maxdepth: 2

installation
quickstart
cli
apps
backends
methodology
output
api
changelog
```

* {ref}`genindex`
* {ref}`search`
