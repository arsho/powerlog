# Methodology

## How a measurement runs

Powerlog selects a backend per domain, resolves the program on `PATH` (rejecting
an unrunnable command before anything is measured), then launches it as a
subprocess — wrapped in `perf stat` if the `perf` CPU backend was chosen. From
the parent process it polls every backend on a fixed interval, time-stamping
each reading pair against the same wall clock so the CPU and GPU series share
one timeline. When the program exits, a final partial interval is accounted for,
counters are read once more, and the summary is written.

Sampling happens out of process and samples are buffered in memory until exit,
so the overhead on the measured program is negligible.

## Energy computation

For polled power sources, energy is a right Riemann sum over the samples: power
is read at the *end* of each interval and applied to the interval that just
elapsed.

$$
E_{\mathrm{gpu}} = \sum_{i=1}^{N} P_i \, \Delta t_i
$$

$P_i$ is the total power across the selected devices read at sample $i$, and
$\Delta t_i = t_i - t_{i-1}$ is the measured elapsed time since the previous
sample — not the nominal `--interval`, so scheduling jitter does not bias the
integral. A final partial interval is added after the program exits.

Energy counters need no integration, but `rapl-sysfs` is still read on the same
interval as the GPU. Each difference is both banked as energy and recorded as a
power sample, which is the whole CPU trace:

$$
P^{\mathrm{cpu}}_i = \frac{C_i - C_{i-1}}{t_i - t_{i-1}}
$$

A CPU sample is therefore the *mean* power over its interval, not an
instantaneous reading. Because those per-interval deltas telescope, the total is
exactly the counter's end-to-end difference — with wraparound handled from the
domain's reported maximum range, and the package domains summed:

$$
E_{\mathrm{cpu}} = \sum_i \left( C_i - C_{i-1} \right)
                 = C_{\mathrm{end}} - C_{\mathrm{start}}
$$

`perf` is the exception. It reports once, when the wrapped process exits, so it
yields that total and no trace at all.

Total energy sums only the domains that were actually measured. The trailing
partial interval, between the last sample and the program exiting, is added to
both energy totals but is not recorded as a sample, so it moves the averages
without appearing in the trace.

Average power is energy divided by wall-clock runtime — the time-weighted mean,
more robust than the mean of the samples when intervals are uneven. The
energy-delay product, $E_{\mathrm{total}} \times t$, penalises slow runs
regardless of power draw, exposing the trade-off that energy alone hides: a
configuration can lower energy simply by running the hardware at a
lower-power but less efficient operating point.

## Choosing a sampling interval

The 100 ms default balances resolution against sampling cost; aim for at least
50 samples over a run. Below about 5 s, use `--interval 0.02`. Each sample
spawns a vendor query, so intervals under roughly 10 ms are not useful. Powerlog
flags any run that produced fewer than ten samples, where the integral describes
the sampling grid more than the workload.

## Accuracy and known biases

Duty-cycled GPU sensors
: `nvidia-smi` reports a duty-cycled power sensor, which biases absolute energy.
  Short kernels are affected most.

RAPL scope
: Package energy covers cores and uncore, may exclude DRAM depending on the
  platform, and never includes storage, network, fans or power-supply losses.

Whole-device attribution
: Both RAPL and NVML report what the *device* draws, not what your process
  draws, so idle power and any other tenant on the node are included. This is
  the quantity that matters for a node-hours budget, but it means a measurement
  is only as meaningful as the load it sustains.

Fixed start-up cost
: The first GPU call pays for CUDA/HIP context creation, typically a few hundred
  milliseconds at near-idle power. Comparisons are fair only between runs long
  enough for that constant to be negligible.

None of these are corrected. Runs on the same machine share identical hardware
and sampling, so they cancel out in *relative* comparisons; treat absolute
Joules as a platform-specific figure and prefer comparative claims.

In practice: make each run last several seconds and check the `Samples` line;
record an idle baseline (`powerlog --no-csv sleep 10`) so you know the floor
every measurement includes; repeat and report the median, discarding the first
run of a series; keep the node otherwise idle; and record `--list-backends`
alongside results so the provenance of each number is clear.
