# Output

Every run prints a summary block and, unless `--no-csv` is given, writes two
CSVs. With `--output run.csv` they are `run.csv` and `run_samples.csv`; by
default, `powerlog_output.csv` and `powerlog_output_samples.csv`. Anything that
could not be measured is `n/a`.

## Reading the summary block

`Total time (s)`
: Wall clock from launch to exit, the same quantity as `Total Time (s)` in the
  CSV. It covers the whole process, including CUDA context creation, allocation
  and teardown — not only the compute phase. Every derived figure below uses
  it, which is why a run must be long enough for start-up to be negligible.

`Energy (J)`
: Measured per domain. GPU energy is the integral of the sampled power; CPU
  energy is the difference of the RAPL counter. `TOTAL` sums only the domains
  that were actually measured.

`Share (%)`
: Each domain's fraction of `TOTAL`.

`Avg Power (W)`
: **Derived, not sampled**: the domain's energy divided by total time. For the
  CPU this is average package power over the run, which includes idle draw and
  anything else on the socket. It is reported even for a backend that has no
  power trace, such as `perf`, because it only needs the energy total.

`EDP (J*s)`
: Energy-delay product, total energy multiplied by total time. It penalises a
  slow run regardless of its power draw, exposing the trade-off that energy
  alone hides: a configuration can lower energy simply by running the hardware
  at a lower-power but less efficient operating point. Lower is better, and the
  units are only meaningful when comparing runs of the same work.

`GPU power (W)` / `CPU power (W)`
: Extremes of the *sampled* power, so these lines appear only for a domain that
  was actually traced. With the `perf` CPU backend there is no CPU trace and
  the `CPU power` line is absent.

`Samples`
: How many times power was polled. Below ten, Powerlog adds a note: the
  integral then says more about the sampling grid than about the workload.

`CPU source` / `GPU source`
: Which interface each number came from — worth recording next to results.

## Summary CSV

One header row and one data row. The columns mirror the summary block above.

```text
Command,Return Code,Total Time (s),CPU Energy (J),GPU Energy (J),Total Energy (J),...
./matmul 2048,0,12.4180,962.4013,2136.7742,3099.1755,...
```

`Command`
: The full command line that was profiled.

`Return Code`
: Exit status of the profiled program.

`Total Time (s)`
: Wall-clock runtime.

`CPU Energy (J)`, `GPU Energy (J)`, `Total Energy (J)`
: Per-domain energy and the sum of the domains that were measured.

`CPU Fraction (%)`, `GPU Fraction (%)`
: Each domain's share of total energy.

`Avg CPU Power (W)`, `Avg GPU Power (W)`
: Domain energy divided by runtime.

`Min GPU Power (W)`, `Max GPU Power (W)`
: Extremes of the sampled GPU power.

`EDP (J*s)`
: Energy-delay product.

`GPU Devices`
: Number of GPUs sampled.

`CPU Model`, `GPU Model`
: Product names; GPU names are separated by `;` if they differ.

`CPU Source`, `GPU Source`
: Which interface each reading came from.

## Samples CSV

The power trace, one row per sampling interval.

```text
Timestamp (ns),Elapsed (s),CPU Power (W),GPU Power (W),GPU0 Power (W),GPU1 Power (W)
1788966841539282000,0.1051,77.42,238.60,119.30,119.30
1788966841642857000,0.2086,78.10,241.20,120.90,120.30
```

`Timestamp (ns)`
: Wall-clock time of the sample.

`Elapsed (s)`
: Seconds since the program was launched.

`CPU Power (W)`
: CPU power over the preceding interval. Empty under the `perf` backend, which
  reports only a total at process exit; use `rapl-sysfs` for a CPU trace.

`GPU Power (W)`
: Total GPU power across the sampled devices.

`GPU<i> Power (W)`
: Power of device `i`; one column per device.

## Working with the output

```python
import glob
import pandas as pd

frames = [pd.read_csv(path) for path in sorted(glob.glob("results/*.csv"))
          if not path.endswith("_samples.csv")]
print(pd.concat(frames)[["Command", "Total Energy (J)", "CPU Fraction (%)"]])

trace = pd.read_csv("powerlog_output_samples.csv")
trace.plot(x="Elapsed (s)", y=["CPU Power (W)", "GPU Power (W)"])
```
