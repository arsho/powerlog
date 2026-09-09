# Changelog

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
- `--interval`, `--gpu-backend`, `--cpu-backend`, `--no-cpu`, `--no-gpu`,
  `--no-csv`, `--quiet` and `--version` options.
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
