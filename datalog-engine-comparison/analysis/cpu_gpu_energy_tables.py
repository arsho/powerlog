#!/usr/bin/env python3
"""Summarize per-run CPU+GPU energy CSVs into LaTeX-ready tables.

Reads ``<dir>/<Dataset>_<Engine>.csv`` (as written by ``powerlog --output``) and
prints, per (dataset, engine): total energy, GPU energy, CPU package energy and
the CPU fraction, followed by pivoted tables for each metric.

Usage:
    python cpu_gpu_energy_tables.py ../results/cpugpu/tc
"""

import glob
import os
import sys

import pandas as pd

ENGINES = ["GPULog", "MNMGDatalog", "cuDF", "BJoin", "INLJoin"]

# Current powerlog column -> archived column produced by the original harness.
COLUMN_ALIASES = {
    "total_j": ("Total Energy (J)", "TotalEnergy(J)"),
    "gpu_j": ("GPU Energy (J)", "GPUEnergy(J)"),
    "cpu_j": ("CPU Energy (J)", "CPUEnergy(J)"),
    "time_s": ("Total Time (s)", "TotalTime(S)"),
}


def pick(row, names):
    """Return the first present, numeric value among ``names``."""
    for name in names:
        if name in row.index:
            try:
                return float(row[name])
            except (TypeError, ValueError):
                continue
    return float("nan")


def load(directory):
    """Load every ``<Dataset>_<Engine>.csv`` in ``directory`` into a DataFrame."""
    rows = []
    for path in sorted(glob.glob(os.path.join(directory, "*.csv"))):
        base = os.path.splitext(os.path.basename(path))[0]
        if base.endswith("_samples") or "_" not in base:
            continue
        dataset, engine = base.rsplit("_", 1)
        try:
            row = pd.read_csv(path).iloc[0]
        except Exception as exc:  # noqa: BLE001 - report and keep going
            print(f"skip {path}: {exc}", file=sys.stderr)
            continue
        rows.append(
            dict(
                Dataset=dataset,
                Engine=engine,
                Total=pick(row, COLUMN_ALIASES["total_j"]),
                GPU=pick(row, COLUMN_ALIASES["gpu_j"]),
                CPU=pick(row, COLUMN_ALIASES["cpu_j"]),
                Time=pick(row, COLUMN_ALIASES["time_s"]),
            )
        )
    return pd.DataFrame(rows)


def pivot_latex(frame, column, fmt, title):
    """Print one metric as LaTeX table rows."""
    table = frame.pivot(index="Dataset", columns="Engine", values=column)
    table = table.reindex(columns=ENGINES)
    print(f"\n% {title}")
    print("Dataset & " + " & ".join(ENGINES) + r" \\")
    for dataset, row in table.iterrows():
        cells = [
            "--" if pd.isna(row[engine]) else format(row[engine], fmt)
            for engine in ENGINES
        ]
        print(f"{dataset:15} & " + " & ".join(cells) + r" \\")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    directory = sys.argv[1]
    frame = load(directory)
    if frame.empty:
        print(f"no result CSVs found in {directory}", file=sys.stderr)
        return 1

    frame["CPUfrac"] = frame["CPU"] / frame["Total"] * 100
    print(frame.sort_values(["Dataset", "Engine"]).to_string(index=False))

    pivot_latex(frame, "Total", ".0f", "Total energy CPU+GPU (J)")
    pivot_latex(frame, "CPUfrac", ".0f", "CPU package energy fraction (%)")
    pivot_latex(frame, "GPU", ".0f", "GPU energy (J)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
