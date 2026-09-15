# Methodology

## How a measurement runs

1. Powerlog probes the platform and selects a CPU and a GPU backend.
2. The program is resolved on `PATH`; an unrunnable command is rejected here,
   before anything is measured.
3. The target program is launched as a subprocess. If the `perf` CPU backend was
   chosen, the command is wrapped in `perf stat` at this point.
4. From the parent process, Powerlog polls every backend on a fixed interval
   (default 100 ms), time-stamping each reading pair against the same wall clock
   so the CPU and GPU series share one timeline.
5. When the program exits, a final partial interval is accounted for, counters
   are read one last time, and the summary is written.

Sampling happens out of process, and samples are buffered in memory and flushed
to CSV only at exit, so the overhead on the measured program is negligible.

## Energy computation

For polled power sources (all GPU backends), energy is the integral of power
over time, evaluated as a left Riemann sum:

$$
E_{\mathrm{gpu}} = \sum_{i=1}^{N} P_i \, \Delta t_i
$$

where $N$ is the number of intervals, $P_i$ is the total power drawn across the
selected devices at sample $i$, and $\Delta t_i$ is the elapsed time since the
previous sample.

For energy counters (RAPL), energy is the difference between the final and
initial counter values, with wraparound handled using the domain's reported
maximum range:

$$
E_{\mathrm{cpu}} = C_{\mathrm{end}} - C_{\mathrm{start}}
$$

Total energy is the sum of the domains that were actually measured:

$$
E_{\mathrm{total}} = E_{\mathrm{cpu}} + E_{\mathrm{gpu}}
$$

## Derived metrics

Average power
: Energy divided by wall-clock runtime, reported per domain. This is the
  time-weighted mean, which is more robust than the mean of the samples when
  intervals are uneven.

Domain share
: $E_{\mathrm{domain}} / E_{\mathrm{total}}$, expressed as a percentage. Useful
  for spotting workloads whose energy is dominated by the host rather than the
  accelerator.

Energy--delay product (EDP)
: $E_{\mathrm{total}} \times t$, in Joule-seconds. EDP penalises slow runs
  regardless of their power draw, which exposes the trade-off that energy alone
  hides: a configuration can lower energy simply by running the hardware at a
  less efficient but lower-power operating point.

## Choosing a sampling interval

The default of 100 ms balances resolution against sampling cost. As a rule of
thumb, aim for at least 50 samples over a run:

* Runs shorter than about 5 s: use `--interval 0.02`.
* Runs longer than a few minutes: the default is fine, and a larger interval
  reduces the size of the trace file.

Very short intervals are limited by how fast the vendor tool responds; each
sample spawns a query, so intervals below roughly 10 ms are not useful.

Powerlog adds a note to the summary when a run produced fewer than ten samples,
because at that point the integral says more about the sampling grid than about
the workload.

## Accuracy and known biases

Several systematic biases are worth stating explicitly:

Duty-cycled GPU sensors
: `nvidia-smi` reports a duty-cycled power sensor, which can bias absolute
  energy. Short kernels are affected the most.

RAPL scope
: RAPL package energy covers cores and uncore. Depending on the platform it may
  exclude DRAM, and it never includes the rest of the system (storage, network,
  fans, power-supply losses).

Whole-device attribution
: Both RAPL and NVML report what the *device* draws, not what your process
  draws. Idle power and any other tenant on the node are included, so a short
  run is mostly idle floor. This is intentional -- it is the quantity that
  matters for a node-hours energy budget -- but it means a measurement is only
  as meaningful as the load it sustains.

Fixed start-up cost
: The first GPU call in a process pays for CUDA/HIP context creation, typically
  a few hundred milliseconds at near-idle power. Comparisons are only fair
  between runs long enough for that constant to be negligible.

None of these are corrected. Because runs on the same machine share identical
hardware and sampling, they cancel out in *relative* comparisons between
programs or configurations. Treat absolute Joules as a platform-specific figure,
and prefer comparative claims.

## Practical recommendations

* Make each run last at least a few seconds, and check the `Samples` line.
* Record an idle baseline (`powerlog --no-csv sleep 10`) so you know the floor
  that every measurement includes.
* Compare configurations on the same machine, in the same session.
* Repeat each measurement and report the median; power varies with temperature
  and clock behaviour.
* Discard the first run of a series, which pays for cold caches and clock ramp.
* Keep the machine otherwise idle. Powerlog measures whole-device power, so
  other tenants on the node contribute to the reading.
* Record `--list-backends` output alongside results so the provenance of each
  number is clear.
