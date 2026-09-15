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

For polled power sources, energy is a left Riemann sum over the samples:

$$
E_{\mathrm{gpu}} = \sum_{i=1}^{N} P_i \, \Delta t_i
$$

where $P_i$ is the total power across the selected devices at sample $i$ and
$\Delta t_i$ the time since the previous sample. For energy counters (RAPL) it
is the difference between the final and initial values, with wraparound handled
from the domain's reported maximum range:

$$
E_{\mathrm{cpu}} = C_{\mathrm{end}} - C_{\mathrm{start}}
$$

Total energy sums only the domains that were actually measured.

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
