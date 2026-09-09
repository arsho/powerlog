"""Formatting and persistence of :class:`~powerlog.core.MeasurementResult`."""

from __future__ import annotations

import csv
import sys

__all__ = [
    "DEFAULT_OUTPUT",
    "SUMMARY_FIELDS",
    "format_summary",
    "print_summary",
    "write_summary_csv",
    "write_samples_csv",
    "samples_path_for",
]

#: File name used when ``--output`` is not supplied.
DEFAULT_OUTPUT = "powerlog_output.csv"

#: Column order of the summary CSV.
SUMMARY_FIELDS = (
    "Command",
    "Return Code",
    "Total Time (s)",
    "CPU Energy (J)",
    "GPU Energy (J)",
    "Total Energy (J)",
    "CPU Fraction (%)",
    "GPU Fraction (%)",
    "Avg CPU Power (W)",
    "Avg GPU Power (W)",
    "Min GPU Power (W)",
    "Max GPU Power (W)",
    "EDP (J*s)",
    "GPU Devices",
    "CPU Backend",
    "GPU Backend",
)

_NA = "n/a"


def _num(value, digits=4):
    """Format a float, or ``n/a`` when the value was not measured."""
    if value is None:
        return _NA
    return f"{value:.{digits}f}"


def _pct(value):
    if value is None:
        return _NA
    return f"{value * 100:.2f}"


def samples_path_for(summary_path):
    """Return the companion samples path for a summary CSV path.

    ``powerlog_output.csv`` becomes ``powerlog_output_samples.csv``.
    """
    text = str(summary_path)
    if text.endswith(".csv"):
        return text[: -len(".csv")] + "_samples.csv"
    return text + "_samples.csv"


def format_summary(result, width=64):
    """Return the human readable summary block as a string.

    Domains that could not be measured are shown as ``n/a`` together with an
    explanatory note, so the report is always complete.
    """
    rule = "=" * width
    lines = [rule, "POWERLOG ENERGY SUMMARY".center(width), rule]

    lines.append(f"{'Command':<24}{' '.join(result.command)}")
    lines.append(f"{'Exit code':<24}{result.return_code}")
    lines.append(f"{'Runtime (s)':<24}{result.total_time_s:.4f}")
    lines.append(f"{'Samples':<24}{len(result.samples)}")
    lines.append("-" * width)

    lines.append(f"{'Domain':<12}{'Energy (J)':>16}{'Share (%)':>12}{'Avg Power (W)':>16}")
    lines.append("-" * width)
    lines.append(
        f"{'CPU':<12}{_num(result.cpu_energy_j):>16}"
        f"{_pct(result.cpu_fraction):>12}{_num(result.avg_cpu_power_w):>16}"
    )
    lines.append(
        f"{'GPU':<12}{_num(result.gpu_energy_j):>16}"
        f"{_pct(result.gpu_fraction):>12}{_num(result.avg_gpu_power_w):>16}"
    )
    lines.append("-" * width)
    lines.append(f"{'TOTAL':<12}{_num(result.total_energy_j):>16}{'':>12}{'':>16}")
    lines.append(f"{'EDP (J*s)':<12}{_num(result.energy_delay_product):>16}")

    if result.max_gpu_power_w is not None:
        lines.append("-" * width)
        lines.append(
            f"{'GPU power (W)':<24}min {_num(result.min_gpu_power_w, 2)} / "
            f"max {_num(result.max_gpu_power_w, 2)}"
        )
    if result.max_cpu_power_w is not None:
        lines.append(
            f"{'CPU power (W)':<24}min {_num(result.min_cpu_power_w, 2)} / "
            f"max {_num(result.max_cpu_power_w, 2)}"
        )

    lines.append("-" * width)
    lines.append(f"{'CPU backend':<24}{result.cpu_backend or 'not available'}")
    gpu_desc = result.gpu_backend or "not available"
    if result.gpu_backend and result.gpu_device_count:
        gpu_desc += f" ({result.gpu_device_count} device(s))"
    lines.append(f"{'GPU backend':<24}{gpu_desc}")

    for note in result.notes:
        lines.append(f"  note: {note}")
    lines.append(rule)
    return "\n".join(lines)


def print_summary(result, stream=None):
    """Print :func:`format_summary` to ``stream`` (default ``sys.stdout``)."""
    print(format_summary(result), file=stream or sys.stdout)


def write_summary_csv(path, result):
    """Write the one-row summary CSV with the per-domain energy breakdown.

    :param path: Destination file path.
    :param result: A :class:`~powerlog.core.MeasurementResult`.
    """
    row = [
        " ".join(result.command),
        result.return_code,
        _num(result.total_time_s),
        _num(result.cpu_energy_j),
        _num(result.gpu_energy_j),
        _num(result.total_energy_j),
        _pct(result.cpu_fraction),
        _pct(result.gpu_fraction),
        _num(result.avg_cpu_power_w),
        _num(result.avg_gpu_power_w),
        _num(result.min_gpu_power_w, 2),
        _num(result.max_gpu_power_w, 2),
        _num(result.energy_delay_product),
        result.gpu_device_count,
        result.cpu_backend or _NA,
        result.gpu_backend or _NA,
    ]
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(SUMMARY_FIELDS)
        writer.writerow(row)


def write_samples_csv(path, result):
    """Write the per-sample power trace, one row per sampling interval.

    Columns are ``Timestamp (ns)``, ``Elapsed (s)``, ``CPU Power (W)``,
    ``GPU Power (W)`` followed by one ``GPU<i> Power (W)`` column per device.
    """
    device_count = max((len(s.gpu_per_device_w) for s in result.samples), default=0)
    header = ["Timestamp (ns)", "Elapsed (s)", "CPU Power (W)", "GPU Power (W)"]
    header += [f"GPU{i} Power (W)" for i in range(device_count)]

    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for sample in result.samples:
            row = [
                sample.timestamp_ns,
                f"{sample.elapsed_s:.4f}",
                _num(sample.cpu_power_w, 2),
                _num(sample.gpu_power_w, 2),
            ]
            for i in range(device_count):
                if i < len(sample.gpu_per_device_w):
                    row.append(f"{sample.gpu_per_device_w[i]:.2f}")
                else:
                    row.append(_NA)
            writer.writerow(row)
