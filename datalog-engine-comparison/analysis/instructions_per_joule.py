#!/usr/bin/env python3
"""Compute instructions-per-joule for the GPU Datalog engines.

Workflow (no engine code changes needed):
  1. Run each engine once under Nsight Compute collecting ONLY the instruction
     counter, e.g.:

       ncu --metrics sm__inst_executed.sum --target-processes all \
           --csv --log-file <Dataset>_<Engine>.csv \
           ./tc_interactive.out data/data_165435.bin 0 1 1

     ncu prints one row per kernel; this script SUMS them to a per-run total.
  2. Put every ncu csv under a directory (default: logs/ncu/) named
     "<Dataset>_<Engine>.csv"  (e.g. usroads_MNMGDatalog.csv).
  3. Run it against an energy CSV with ``Dataset``, ``Engine`` and a GPU-energy
     column, built from the ``results/cpugpu/`` per-run outputs:

       python instructions_per_joule.py energy_tc.csv logs/ncu/tc

It joins total instructions to the existing energy CSV and emits a LaTeX table
of instructions, energy, and instructions/joule.

The metric is GPU instructions per **GPU** joule, so the denominator must be GPU
energy. Beware that two energy CSV layouts are in use and both spell a column
``TotalEnergy(J)`` while meaning different things:

  * ``power.py`` (GPU only)     -> ``TotalEnergy(J)`` IS the GPU energy.
  * ``power_cpu_gpu.py``        -> ``GPUEnergy(J)``, ``CPUEnergy(J)`` and
                                   ``TotalEnergy(J)`` = CPU + GPU.

Taking ``TotalEnergy(J)`` blindly therefore divides GPU work by host+device
energy on the second layout, understating the metric by 1.5-2.2x at the CPU
shares we measure. :func:`gpu_energy_column` picks the right column and says
which one it used.

Instruction count is deterministic for a given (engine, dataset, args), so it is
valid to combine an ncu run with a separately measured energy run. ncu perturbs
timing/power (kernel replay), so we take only the COUNT from it, never time.
"""
import os
import re
import sys
import glob
import pandas as pd


def parse_ncu_csv(path):
    """Return total instructions (sum of sm__inst_executed.sum over kernels).

    ncu --csv output is preceded by app stdout (e.g. the engine's own
    "# Input,# Process,..." header and FILE-IO timestamps). We locate the real
    ncu table by the header line that contains both "ID" and "Metric Value".
    """
    from io import StringIO
    with open(path) as f:
        lines = f.readlines()

    # Find the ncu CSV header: quoted columns including "Metric Value".
    start = None
    for i, l in enumerate(lines):
        if '"Metric Value"' in l and '"ID"' in l:
            start = i
            break
    if start is None:
        raise ValueError(f"No ncu CSV header ('Metric Value') found in {path}")

    df = pd.read_csv(StringIO("".join(lines[start:])))

    # Long layout: one row per (kernel, metric) with Metric Name/Value columns.
    if {"Metric Name", "Metric Value"}.issubset(df.columns):
        sub = df[df["Metric Name"].astype(str).str.contains("inst_executed")]
        vals = pd.to_numeric(
            sub["Metric Value"].astype(str).str.replace(",", ""), errors="coerce")
        return float(vals.sum())

    # Wide layout: a dedicated sm__inst_executed.sum column.
    col = next((c for c in df.columns if "inst_executed" in c.replace('"', '')), None)
    if col is None:
        raise ValueError(f"No inst_executed data found in {path}: {list(df.columns)}")
    vals = pd.to_numeric(df[col].astype(str).str.replace(",", ""), errors="coerce")
    return float(vals.sum())


def collect_instructions(ncu_dir):
    """Map (Dataset, Engine) -> total instructions from <Dataset>_<Engine>.csv."""
    rows = []
    for path in glob.glob(os.path.join(ncu_dir, "*.csv")):
        base = os.path.splitext(os.path.basename(path))[0]
        if "_" not in base:
            print(f"skip (need Dataset_Engine.csv): {path}")
            continue
        dataset, engine = base.rsplit("_", 1)
        try:
            total = parse_ncu_csv(path)
        except Exception as e:
            print(f"skip {path}: {e}")
            continue
        rows.append({"Dataset": dataset, "Engine": engine, "Instructions": total})
    return pd.DataFrame(rows)


def gpu_energy_column(columns):
    """Return the column holding GPU energy, for either energy CSV layout.

    :param columns: Column names of the energy CSV.
    :returns: The name of the GPU-energy column.
    :raises ValueError: If the CSV carries CPU energy but no GPU energy column,
        in which case ``TotalEnergy(J)`` is host+device and there is no way to
        recover the GPU-only figure.
    """
    if "GPUEnergy(J)" in columns:
        return "GPUEnergy(J)"
    if "CPUEnergy(J)" in columns:
        raise ValueError(
            "energy CSV has CPUEnergy(J) but no GPUEnergy(J): its "
            "TotalEnergy(J) is CPU+GPU, which cannot be used as the "
            "denominator for GPU instructions per GPU joule"
        )
    if "TotalEnergy(J)" in columns:
        # Legacy power.py layout: the run was GPU only, so the total is the GPU
        # energy.
        return "TotalEnergy(J)"
    raise ValueError(f"no energy column found in {list(columns)}")


def main():
    if len(sys.argv) < 3:
        print("usage: python instructions_per_joule.py <power_csv> <ncu_dir>")
        sys.exit(1)
    power_csv, ncu_dir = sys.argv[1], sys.argv[2]

    power = pd.read_csv(power_csv)
    inst = collect_instructions(ncu_dir)
    if inst.empty:
        print(f"No ncu CSVs parsed under {ncu_dir}")
        sys.exit(1)

    energy_col = gpu_energy_column(power.columns)
    print(f"GPU energy taken from column: {energy_col}")

    merged = power.merge(inst, on=["Dataset", "Engine"], how="left")
    merged["InstrPerJoule"] = merged.apply(
        lambda r: r["Instructions"] / r[energy_col]
        if pd.notna(r.get("Instructions")) and r[energy_col] > 0 else float("nan"),
        axis=1,
    )

    cols = ["Dataset", "Engine", "Instructions", energy_col, "InstrPerJoule"]
    print(merged[cols].to_string(index=False))

    # Auto-scale units: pick G/M/k-instructions per joule for readability.
    vals = merged["InstrPerJoule"].dropna()
    med = vals.median() if not vals.empty else 0
    if med >= 1e9:
        scale, unit = 1e9, "G"
    elif med >= 1e6:
        scale, unit = 1e6, "M"
    else:
        scale, unit = 1e3, "k"

    engines = ["GPULog", "MNMGDatalog", "cuDF", "BJoin", "INLJoin"]
    merged["Scaled"] = merged["InstrPerJoule"] / scale
    pivot = merged.pivot(index="Dataset", columns="Engine", values="Scaled").reindex(columns=engines)
    print(f"\n% Instructions per joule ({unit}-instructions/J)")
    print("Dataset & " + " & ".join(engines) + " \\\\")
    for dataset, row in pivot.iterrows():
        cells = ["--" if pd.isna(row[e]) else f"{row[e]:.1f}" for e in engines]
        print(f"{dataset:15} & " + " & ".join(cells) + " \\\\")

    # Also emit total instructions (in billions) per engine/dataset.
    merged["GInstr"] = merged["Instructions"] / 1e9
    pivot_i = merged.pivot(index="Dataset", columns="Engine", values="GInstr").reindex(columns=engines)
    print("\n% Total GPU instructions (billions)")
    print("Dataset & " + " & ".join(engines) + " \\\\")
    for dataset, row in pivot_i.iterrows():
        cells = ["--" if pd.isna(row[e]) else f"{row[e]:.1f}" for e in engines]
        print(f"{dataset:15} & " + " & ".join(cells) + " \\\\")


if __name__ == "__main__":
    main()
