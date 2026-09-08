import subprocess
import sys
import time
import csv
import os
import tempfile
import argparse

NS_IN_S = 1_000_000_000  # Nanoseconds in a second

def log(message):
    print(message, file=sys.stdout)

def get_power_draw(total_gpu_on_node=1):
    proc = subprocess.run(
        ["nvidia-smi", "--query-gpu=power.draw", "--format=csv,noheader,nounits"],
        capture_output=True
    )
    stdout = proc.stdout.decode("utf-8").strip()
    power_values = [float(line.strip()) for line in stdout.splitlines()]
    return sum(power_values[:total_gpu_on_node])

def parse_perf_energy(perf_file):
    """Extract Joules for power/energy-pkg/ from a `perf stat` output file.

    On CPUs that expose RAPL package energy (e.g. AMD EPYC, most Intel) and where
    unprivileged access is available (perf_event_paranoid <= 0), `perf stat -e
    power/energy-pkg/` reports a line like:
        58.35 Joules power/energy-pkg/
    Returns the CPU package energy in Joules, or NaN if unavailable.
    """
    try:
        with open(perf_file) as f:
            for line in f:
                if "energy-pkg" in line:
                    tokens = line.strip().split()
                    for i, t in enumerate(tokens):
                        if t.lower().startswith("joule"):
                            return float(tokens[i - 1].replace(",", ""))
    except FileNotFoundError:
        pass
    return float("nan")

def measure_power(cmd_args, resolution=0.1, total_gpu_on_node=1, cpu=False):
    get_power_draw()  # warm-up

    perf_tmp = None
    if cpu:
        perf_tmp = tempfile.NamedTemporaryFile(
            prefix="perf_", suffix=".txt", delete=False
        ).name
        # Wrap the whole command in `perf stat` to collect CPU-package energy
        # (RAPL) in lockstep with the GPU sampling below.
        run_cmd = ["perf", "stat", "-e", "power/energy-pkg/", "-o", perf_tmp] + cmd_args
    else:
        run_cmd = cmd_args

    energy_j = 0
    power_draw_samples = []

    proc = subprocess.Popen(run_cmd)
    start_time_ns = time.time_ns()
    time_ns = start_time_ns

    while True:
        try:
            proc.wait(timeout=resolution)
        except subprocess.TimeoutExpired:
            new_time_ns = time.time_ns()
            draw_w = get_power_draw(total_gpu_on_node)
            delay_ns = new_time_ns - time_ns
            energy_j += delay_ns * draw_w / NS_IN_S
            power_draw_samples.append((new_time_ns, draw_w))
            time_ns = new_time_ns
        else:
            break

    end_time_ns = time_ns
    total_time_s = (end_time_ns - start_time_ns) / NS_IN_S
    sampled_draws = [v[1] for v in power_draw_samples]
    avg_power_sampled = sum(sampled_draws) / len(sampled_draws)
    avg_power_timed = energy_j / total_time_s
    min_draw = min(sampled_draws)
    max_draw = max(sampled_draws)

    cpu_energy_j = float("nan")
    if cpu:
        cpu_energy_j = parse_perf_energy(perf_tmp)
        try:
            os.unlink(perf_tmp)
        except OSError:
            pass

    # Total energy = GPU energy + CPU energy (CPU counted only when available).
    cpu_valid = cpu_energy_j == cpu_energy_j  # NaN check
    total_energy_j = energy_j + (cpu_energy_j if cpu_valid else 0)
    cpu_fraction = (cpu_energy_j / total_energy_j) if (cpu_valid and total_energy_j) else float("nan")

    return {
        "total_time_s": total_time_s,
        "energy_j": energy_j,
        "gpu_energy_j": energy_j,
        "cpu_energy_j": cpu_energy_j,
        "total_energy_j": total_energy_j,
        "cpu_fraction": cpu_fraction,
        "avg_power_sampled": avg_power_sampled,
        "avg_power_timed": avg_power_timed,
        "min_draw": min_draw,
        "max_draw": max_draw,
        "samples": power_draw_samples
    }

def save_summary_csv(path, result, cpu=False):
    with open(path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        if cpu:
            writer.writerow([
                "Total Time (s)",
                "GPU Energy (J)",
                "CPU Energy (J)",
                "Total Energy (J)",
                "CPU Fraction",
                "Avg Power Sampled (W)",
                "Avg Power Timed (W)",
                "Min Power Sampled (W)",
                "Max Power Sampled (W)"
            ])
            writer.writerow([
                f"{result['total_time_s']:.4f}",
                f"{result['gpu_energy_j']:.4f}",
                f"{result['cpu_energy_j']:.4f}",
                f"{result['total_energy_j']:.4f}",
                f"{result['cpu_fraction']:.4f}",
                f"{result['avg_power_sampled']:.4f}",
                f"{result['avg_power_timed']:.4f}",
                f"{result['min_draw']:.2f}",
                f"{result['max_draw']:.2f}"
            ])
        else:
            writer.writerow([
                "Total Time (s)",
                "Total Energy (J)",
                "Avg Power Sampled (W)",
                "Avg Power Timed (W)",
                "Min Power Sampled (W)",
                "Max Power Sampled (W)"
            ])
            writer.writerow([
                f"{result['total_time_s']:.4f}",
                f"{result['energy_j']:.4f}",
                f"{result['avg_power_sampled']:.4f}",
                f"{result['avg_power_timed']:.4f}",
                f"{result['min_draw']:.2f}",
                f"{result['max_draw']:.2f}"
            ])

def save_samples_csv(path, samples):
    with open(path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Timestamp (ns)", "Power Draw (W)"])
        for t_ns, draw in samples:
            writer.writerow([t_ns, f"{draw:.2f}"])

def main():
    parser = argparse.ArgumentParser(description="Measure GPU (and optionally CPU) power during execution.")
    parser.add_argument("cmd", nargs=argparse.REMAINDER, help="Command to run (mandatory)")
    parser.add_argument("--output", type=str, help="Output CSV base name (optional)")
    parser.add_argument("--gpu", type=int, default=1, help="Number of GPUs per node (default 1)")
    parser.add_argument("--cpu", action="store_true",
                        help="Also measure CPU-package energy via RAPL (perf power/energy-pkg/)")

    try:
        args = parser.parse_args()
    except:
        parser.print_help()
        sys.exit(0)

    if not args.cmd:
        parser.print_help()
        sys.exit(0)

    where = "GPU + CPU" if args.cpu else "GPU"
    log(f"Running command: {' '.join(args.cmd)} on {args.gpu} GPU ({where} energy)")
    result = measure_power(args.cmd, total_gpu_on_node=args.gpu, cpu=args.cpu)

    # Display to stdout
    log("\n" + "=" * 60)
    if args.cpu:
        log("CPU + GPU POWER USAGE SUMMARY")
        log(f"Total Time:           {result['total_time_s']:.4f} s")
        log(f"GPU Energy:           {result['gpu_energy_j']:.4f} J")
        log(f"CPU Energy (pkg):     {result['cpu_energy_j']:.4f} J")
        log(f"Total Energy:         {result['total_energy_j']:.4f} J")
        log(f"CPU Fraction:         {result['cpu_fraction']:.2%}")
        log(f"Avg GPU Power (Timed):    {result['avg_power_timed']:.4f} W")
        log(f"Avg GPU Power (Sampled):  {result['avg_power_sampled']:.4f} W")
        log(f"Min GPU Power (Sampled):  {result['min_draw']:.2f} W")
        log(f"Max GPU Power (Sampled):  {result['max_draw']:.2f} W")
    else:
        log("GPU POWER USAGE SUMMARY")
        log(f"Total Time:           {result['total_time_s']:.4f} s")
        log(f"Total Energy:         {result['energy_j']:.4f} J")
        log(f"Avg Power (Timed):    {result['avg_power_timed']:.4f} W")
        log(f"Avg Power (Sampled):  {result['avg_power_sampled']:.4f} W")
        log(f"Min Power (Sampled):  {result['min_draw']:.2f} W")
        log(f"Max Power (Sampled):  {result['max_draw']:.2f} W")
    log("=" * 60)

    # Save to CSVs if output requested
    if args.output:
        summary_csv = args.output if args.output.endswith(".csv") else args.output + ".csv"
        samples_csv = summary_csv.replace(".csv", "_samples.csv")
        save_summary_csv(summary_csv, result, cpu=args.cpu)
        save_samples_csv(samples_csv, result["samples"])
        log(f"Saved summary to: {summary_csv}")
        log(f"Saved power samples to: {samples_csv}")

if __name__ == "__main__":
    main()


# GPU only:
# powerlog --output power_report.csv --gpu 4 ./tc.out data/data_7035.bin 0 0 1
# GPU + CPU (RAPL):
# powerlog --cpu --output power_report.csv --gpu 4 ./tc.out data/data_7035.bin 0 0 1
