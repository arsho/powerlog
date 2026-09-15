"""Command line interface for Powerlog."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .backends import available_cpu_backends, available_gpu_backends
from .core import DEFAULT_INTERVAL_S, measure_power
from .report import (
    DEFAULT_OUTPUT,
    print_summary,
    samples_path_for,
    write_samples_csv,
    write_summary_csv,
)

__all__ = ["build_parser", "main"]

_EPILOG = """\
examples:
  powerlog ./matmul 2048                 measure CPU and GPU energy
  powerlog -m gpu ./matmul 2048          GPU energy only
  powerlog -m cpu ./my_cpu_program       CPU energy only
  powerlog -o run.csv ./matmul 2048      choose the output file name
  powerlog --gpu 4 ./multi_gpu_app       sum power over the first 4 GPUs

CPU and GPU energy are both measured by default, and the power sources are
detected automatically. Any domain that is not available on this machine is
reported as n/a instead of failing.

Powerlog measures the node it runs on; it does not aggregate across nodes.
"""


def build_parser():
    """Return the :class:`argparse.ArgumentParser` used by :func:`main`."""
    parser = argparse.ArgumentParser(
        prog="powerlog",
        description="Measure the CPU and GPU energy consumed by a program.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command", nargs=argparse.REMAINDER,
        help="program to run followed by its arguments (required)",
    )
    parser.add_argument(
        "-o", "--output", nargs="?", const=DEFAULT_OUTPUT, default=None,
        metavar="FILE",
        help=f"summary CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--no-csv", action="store_true",
        help="print the summary but do not write any CSV file",
    )
    parser.add_argument(
        "-m", "--measure", default="all", choices=["all", "cpu", "gpu"],
        help="which domains to measure: all (default), cpu only, or gpu only",
    )
    parser.add_argument(
        "--gpu", type=int, default=None, metavar="N",
        help="sample only the first N GPUs (default: all detected)",
    )
    parser.add_argument(
        "--interval", type=float, default=DEFAULT_INTERVAL_S, metavar="SECONDS",
        help=f"sampling interval in seconds (default: {DEFAULT_INTERVAL_S})",
    )

    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="suppress the summary block",
    )
    parser.add_argument(
        "--list-backends", action="store_true",
        help="print the power sources detected on this machine and exit",
    )
    parser.add_argument("--version", action="version", version=f"powerlog {__version__}")
    return parser


def _list_backends():
    gpus = available_gpu_backends()
    cpus = available_cpu_backends()
    print("Detected power sources:")
    print("  GPU:")
    for backend in gpus:
        print(f"    {backend.name:<12} {backend.vendor}")
    if not gpus:
        print("    (none)")
        print("    hint: the vendor tool must run standalone, e.g.")
        print("          nvidia-smi --query-gpu=power.draw "
              "--format=csv,noheader,nounits")
    print("  CPU:")
    for backend in cpus:
        print(f"    {backend.name:<12} {backend.vendor}")
    if not cpus:
        print("    (none)")
        print("    hint: enable RAPL with "
              "'sudo sysctl kernel.perf_event_paranoid=-1'")
        print("          or 'sudo chmod -R a+r /sys/class/powercap'")
    elif [backend.name for backend in cpus] == ["perf"]:
        print("    note: perf reports one total per run and no CPU power "
              "trace;")
        print("          make /sys/class/powercap readable for the "
              "rapl-sysfs backend.")
    print()
    print("The first source listed for each domain is the one that will be "
          "used.")


def main(argv=None):
    """Entry point for the ``powerlog`` console script.

    :param argv: Argument list (defaults to ``sys.argv[1:]``).
    :returns: The exit status of the profiled program.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_backends:
        _list_backends()
        return 0

    command = list(args.command)
    # Allow the conventional "powerlog [options] -- prog args" spelling.
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.print_help(sys.stderr)
        print("\nerror: a program to run is required", file=sys.stderr)
        return 2

    # Power sources are always auto-detected; --measure picks the domains.
    gpu_backend = "auto" if args.measure in ("all", "gpu") else "none"
    cpu_backend = "auto" if args.measure in ("all", "cpu") else "none"

    try:
        result = measure_power(
            command,
            interval=args.interval,
            gpu_backend=gpu_backend,
            cpu_backend=cpu_backend,
            device_count=args.gpu,
        )
    except FileNotFoundError as exc:
        # 127 is the conventional "command not found" status.
        print(f"powerlog: error: {exc}", file=sys.stderr)
        return 127
    except PermissionError as exc:
        # 126 is the conventional "found but not executable" status.
        print(f"powerlog: error: {exc}", file=sys.stderr)
        return 126
    except ValueError as exc:
        print(f"powerlog: error: {exc}", file=sys.stderr)
        return 2

    if not args.quiet:
        print_summary(result)

    if not args.no_csv:
        summary_path = args.output or DEFAULT_OUTPUT
        if not summary_path.endswith(".csv"):
            summary_path += ".csv"
        samples_path = samples_path_for(summary_path)
        write_summary_csv(summary_path, result)
        write_samples_csv(samples_path, result)
        if not args.quiet:
            print(f"Summary written to: {summary_path}")
            print(f"Samples written to: {samples_path}")

    return result.return_code


if __name__ == "__main__":
    sys.exit(main())
