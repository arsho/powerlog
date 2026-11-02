#!/usr/bin/env python3
"""Plot a sweep.sh CSV: performance, power and efficiency vs. the set point.

    python3 plot.py results/clock_<host>_<stamp>.csv [more.csv ...]
    python3 plot.py ramp.csv            # a DVFS_TRACE file: power/clock vs time

Writes <csv>.pdf next to each input. Needs matplotlib only.
Values are normalised per benchmark to its best (or default-setting) run so
FP64, FP32 and memory-bound kernels share an axis.
"""
import csv
import sys
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def plot_trace(path, rows):
    """Per-sample NVML trace (DVFS_TRACE): power and SM clock vs time."""
    t = [float(r["t_s"]) for r in rows]
    fig, ax = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    ax[0].plot(t, [float(r["gpu_power_w"]) for r in rows], label="GPU")
    mod = [float(r["module_power_w"]) for r in rows]
    if any(mod):
        ax[0].plot(t, mod, label="module")
    ax[0].set_ylabel("power (W)")
    ax[0].legend()
    ax[0].grid(alpha=0.3)
    ax[1].plot(t, [float(r["sm_mhz"]) for r in rows], drawstyle="steps-post")
    ax[1].set_ylabel("SM clock (MHz)")
    ax[1].set_xlabel("time (s)")
    ax[1].grid(alpha=0.3)
    fig.suptitle(path)
    fig.tight_layout()
    out = path.rsplit(".", 1)[0] + ".pdf"
    fig.savefig(out)
    print(f"wrote {out}")


def plot(path):
    rows = load(path)
    if not rows:
        print(f"{path}: empty")
        return
    if "t_s" in rows[0]:
        plot_trace(path, rows)
        return
    mode = rows[0]["mode"]
    series = defaultdict(list)
    baseline = {}
    for r in rows:
        key = f'{r["kernel"]} i={r["intensity"]}'
        if r["setpoint"] == "default":
            baseline[key] = r
            continue
        series[key].append(r)

    xlabel = {
        "clock": "locked SM clock (MHz)",
        "power": "GPU power limit (W)",
        "module": "module power limit (W)",
    }.get(mode, "set point")

    fig, ax = plt.subplots(2, 3, figsize=(16, 9))
    ax = ax.ravel()
    for key, rs in sorted(series.items()):
        rs.sort(key=lambda r: float(r["setpoint"]))
        x = [float(r["setpoint"]) for r in rs]
        gops = [float(r["gops"]) for r in rs]
        pw = [float(r["gpu_power_w"]) for r in rs]
        eff = [float(r["gops_per_w"]) for r in rs]
        epp = [float(r["energy_per_pass_mj"]) for r in rs]
        sm = [float(r["sm_mhz_avg"]) for r in rs]
        ref = baseline.get(key)
        g0 = float(ref["gops"]) if ref else max(gops)
        e0 = float(ref["energy_per_pass_mj"]) if ref else min(epp)
        edp = [e * (g0 / g) for e, g in zip(epp, gops)]  # energy x relative time
        edp0 = e0

        ax[0].plot(x, [g / g0 for g in gops], "o-", label=key)
        ax[1].plot(x, pw, "o-", label=key)
        ax[2].plot(x, eff, "o-", label=key)
        ax[3].plot(x, [e / e0 for e in epp], "o-", label=key)
        ax[4].plot(x, [e / edp0 for e in edp], "o-", label=key)
        ax[5].plot(x, sm, "o-", label=key)

    titles = [
        "performance (rel. to default / best)",
        "avg GPU power (W)",
        "efficiency (Gop/s per W)",
        "energy per pass (rel.)",
        "EDP (rel.)",
        "measured avg SM clock (MHz)",
    ]
    for a, t in zip(ax, titles):
        a.set_title(t)
        a.set_xlabel(xlabel)
        a.grid(alpha=0.3)
    ax[0].axhline(1.0, color="k", lw=0.6)
    ax[3].axhline(1.0, color="k", lw=0.6)
    ax[4].axhline(1.0, color="k", lw=0.6)
    if mode == "clock":
        lo = min(float(r["setpoint"]) for rs in series.values() for r in rs)
        hi = max(float(r["setpoint"]) for rs in series.values() for r in rs)
        ax[5].plot([lo, hi], [lo, hi], "k--", lw=0.6, label="requested")
    ax[0].legend(fontsize=8)
    fig.suptitle(f"{path}  ({rows[0]['mode']} sweep)")
    fig.tight_layout()
    out = path.rsplit(".", 1)[0] + ".pdf"
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for p in sys.argv[1:]:
        plot(p)
