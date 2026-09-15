# Changelog

## 0.1.1

Follow-up to 0.1.0, fixing a CPU backend that could advertise itself without
being able to measure, and making the example applications findable and
runnable from the documentation alone.

### Fixed
- `perf` is no longer reported as an available CPU backend unless it actually
  returns a Joules value. Availability was previously inferred from the event
  name appearing in perf's output, which several perf versions also do inside
  their permission-denied message; `--list-backends` could therefore list
  `perf` on a machine where every run came back with no CPU energy.
- The program is resolved before measurement starts, so an unrunnable command
  is reported by Powerlog instead of by the wrapper. Previously, with the
  `perf` backend active, `powerlog matmul 1024 10` surfaced as perf's
  `Workload failed: No such file or directory` and exit status 255, with an
  energy summary for a program that never ran.
- `perf stat` output is parsed in either locale, so a comma decimal separator
  no longer inflates the reading, and `<not supported>` / `<not counted>`
  counters are treated as missing rather than as a parse failure.
- The note printed when `perf` returns no energy now distinguishes a workload
  that failed from a permissions problem, and says what to try.

### Added
- `powerlog.resolve_program()`, the pre-flight executable check, is public.
- Exit status `127` when the program is not found and `126` when it is found
  but not executable, following the usual shell convention.
- `--list-backends` explains what to do when a domain is empty, and flags that
  `perf` yields no CPU power trace.
- A summary note when a run produced fewer than ten power samples, where the
  integrated GPU energy is mostly the idle floor and process start-up rather
  than the workload.
- Documentation: an
  [Example Applications](https://powerlog.readthedocs.io/en/latest/apps.html)
  page covering every app, both of its parameters, the exact command to run
  each one, and the fact that `pip install powerlog` does not ship them.
- Troubleshooting is consolidated on the Backends page, which every other page
  now links to instead of repeating it.
- A "Reading the summary block" section on the Output page, explaining every
  line of the printed report, including which figures are measured and which
  are derived.
- A supported-platforms table in the README: what each domain is read through,
  what it needs, and what it yields.

### Changed
- The summary's `Runtime (s)` line is now `Total time (s)  (wall clock)`, the
  same name the CSV uses, and the block states how the two derived figures are
  obtained: `avg power = energy / total time, EDP = energy x total time`.
  Neither is sampled, which was not obvious for a domain with no power trace.
- Trailing column padding is stripped from the summary block.
- The `perf` backend describes itself as "total only (no CPU power trace)" in
  the summary.
- The documentation is now written in Markdown (MyST) throughout, matching this
  changelog and the repository's other prose; the reStructuredText sources have
  been converted.
- The documentation is roughly half its previous length: content that was
  repeated across pages now has a single home, the separate Examples and
  Citation pages are gone (the case study is covered under Example
  Applications, the citation stays in the README), and the README is a short
  pointer to Read the Docs.
- The Python API is presented as what it is -- a way to script the CLI -- rather
  than as a parallel interface shown alongside every command.
- BJoin is marked "release pending" wherever it is linked, since
  `harp-lab/batch_joins` is not public yet.

## 0.1.0

Powerlog now measures CPU and GPU energy together by default and reports a
per-domain breakdown.

### Added
- CPU package energy measurement via RAPL, using the powercap sysfs interface
  (`rapl-sysfs`) or `perf` (`perf`), selected automatically.
- AMD GPU support via ROCm SMI (`rocm-smi` / `amd-smi`), with an
  `amd-sysfs` fallback reading the `amdgpu` hwmon nodes directly so no
  ROCm installation is required.
- Intel GPU / SYCL support via Level Zero (`xpu-smi`).
- Per-domain energy breakdown: CPU, GPU, total, per-domain share, average power
  and energy-delay product.
- Per-device GPU power columns in the samples CSV.
- Python API: `measure_power()` returning a `MeasurementResult`, plus
  `format_summary()`, `print_summary()`, `write_summary_csv()`,
  `write_samples_csv()` and the backend discovery helpers.
- Pluggable backend classes `PowerSampler` and `EnergyCounter`.
- `--list-backends` to show the power sources detected on the current machine.
- `-m/--measure` to pick the domains, plus `--interval`, `--gpu`, `--no-csv`,
  `--quiet` and `--version` options.
- Documentation site built with Sphinx and published on Read the Docs.
- `apps/`: example GPU programs (`vecadd`, `matmul`, `gemm`, `reduction`,
  `stencil`, `nbody`) that build for NVIDIA and AMD, plus SYCL ports.
- `datalog-engine-comparison/`: Datalog engine energy case study with harness,
  analysis scripts and results.

### Changed
- CPU and GPU are both measured by default; previously only the GPU was.
- `--output` is now optional and defaults to `powerlog_output.csv`.
- Only the program and its arguments are required.
- The summary is always printed, including when a domain cannot be measured.
- Summary CSV columns expanded with the CPU/GPU breakdown and backend
  provenance.
- Powerlog exits with the profiled program's exit status.
- Console script entry point moved to `powerlog.cli:main`.

### Fixed
- Unmeasurable domains now report `n/a` instead of failing the run.
- The final partial sampling interval is accounted for, so short runs no longer
  under-report energy.
- RAPL counter wraparound is handled using `max_energy_range_uj`.
- `--gpu N` now limits the devices that are summed, as documented.

## 0.0.2 (2025-07-10)
- Fix CLI command
- Updated documentation

## 0.0.1 (2025-07-01)
- Initial release
