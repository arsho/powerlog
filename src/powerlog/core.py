"""Whole-application CPU and GPU energy measurement.

:func:`measure_power` launches an unmodified program as a subprocess and samples
CPU and GPU power in lockstep until it exits, returning a
:class:`MeasurementResult` with a per-domain energy breakdown.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field

from .backends import cpu_model, detect_cpu_backend, detect_gpu_backend

__all__ = ["Sample", "MeasurementResult", "measure_power", "DEFAULT_INTERVAL_S"]

NS_IN_S = 1_000_000_000

#: Default interval, in seconds, between power samples.
DEFAULT_INTERVAL_S = 0.1


@dataclass
class Sample:
    """A single point on the shared measurement timeline.

    :param timestamp_ns: Wall-clock time of the sample, in nanoseconds.
    :param elapsed_s: Seconds since the target program was launched.
    :param cpu_power_w: CPU package power in Watts (``None`` if unmeasured).
    :param gpu_power_w: Total GPU power in Watts (``None`` if unmeasured).
    :param gpu_per_device_w: Per-device GPU power readings in Watts.
    """

    timestamp_ns: int
    elapsed_s: float
    cpu_power_w: float | None = None
    gpu_power_w: float | None = None
    gpu_per_device_w: list = field(default_factory=list)


@dataclass
class MeasurementResult:
    """Outcome of a :func:`measure_power` run.

    Energy values are ``None`` when the corresponding domain could not be
    measured on this machine, which lets the caller distinguish "zero energy"
    from "not measured".
    """

    #: Command line that was profiled.
    command: list = field(default_factory=list)
    #: Exit status of the profiled program.
    return_code: int = 0
    #: Wall-clock runtime in seconds.
    total_time_s: float = 0.0

    #: CPU package energy in Joules, or ``None``.
    cpu_energy_j: float | None = None
    #: GPU energy in Joules, or ``None``.
    gpu_energy_j: float | None = None

    #: Description of the active CPU backend, or ``None``.
    cpu_backend: str | None = None
    #: Description of the active GPU backend, or ``None``.
    gpu_backend: str | None = None
    #: Number of GPU devices sampled.
    gpu_device_count: int = 0

    #: Host CPU product name, e.g. ``"AMD EPYC 7532 32-Core Processor"``.
    cpu_model: str | None = None
    #: Product name of each GPU sampled, e.g. ``["NVIDIA A100-PCIE-40GB"]``.
    gpu_models: list = field(default_factory=list)

    #: Collected samples on the shared timeline.
    samples: list = field(default_factory=list)
    #: Human readable notes, e.g. why a domain was skipped.
    notes: list = field(default_factory=list)

    # -- derived quantities ------------------------------------------------- #

    @property
    def total_energy_j(self):
        """Sum of the measured domains, or ``None`` if nothing was measured."""
        parts = [e for e in (self.cpu_energy_j, self.gpu_energy_j) if e is not None]
        return sum(parts) if parts else None

    @property
    def cpu_fraction(self):
        """CPU share of total energy in ``[0, 1]``, or ``None``."""
        total = self.total_energy_j
        if self.cpu_energy_j is None or not total:
            return None
        return self.cpu_energy_j / total

    @property
    def gpu_fraction(self):
        """GPU share of total energy in ``[0, 1]``, or ``None``."""
        total = self.total_energy_j
        if self.gpu_energy_j is None or not total:
            return None
        return self.gpu_energy_j / total

    @property
    def avg_cpu_power_w(self):
        """Mean CPU power (energy divided by runtime), or ``None``."""
        if self.cpu_energy_j is None or not self.total_time_s:
            return None
        return self.cpu_energy_j / self.total_time_s

    @property
    def avg_gpu_power_w(self):
        """Mean GPU power (energy divided by runtime), or ``None``."""
        if self.gpu_energy_j is None or not self.total_time_s:
            return None
        return self.gpu_energy_j / self.total_time_s

    @property
    def energy_delay_product(self):
        """Energy--delay product in Joule-seconds, or ``None``."""
        total = self.total_energy_j
        if total is None:
            return None
        return total * self.total_time_s

    def _gpu_series(self):
        return [s.gpu_power_w for s in self.samples if s.gpu_power_w is not None]

    def _cpu_series(self):
        return [s.cpu_power_w for s in self.samples if s.cpu_power_w is not None]

    @property
    def min_gpu_power_w(self):
        """Smallest sampled GPU power in Watts, or ``None``."""
        series = self._gpu_series()
        return min(series) if series else None

    @property
    def max_gpu_power_w(self):
        """Largest sampled GPU power in Watts, or ``None``."""
        series = self._gpu_series()
        return max(series) if series else None

    @property
    def min_cpu_power_w(self):
        """Smallest sampled CPU power in Watts, or ``None``."""
        series = self._cpu_series()
        return min(series) if series else None

    @property
    def max_cpu_power_w(self):
        """Largest sampled CPU power in Watts, or ``None``."""
        series = self._cpu_series()
        return max(series) if series else None

    def as_dict(self):
        """Return a flat ``dict`` of the summary metrics."""
        return {
            "command": " ".join(self.command),
            "return_code": self.return_code,
            "total_time_s": self.total_time_s,
            "cpu_energy_j": self.cpu_energy_j,
            "gpu_energy_j": self.gpu_energy_j,
            "total_energy_j": self.total_energy_j,
            "cpu_fraction": self.cpu_fraction,
            "gpu_fraction": self.gpu_fraction,
            "avg_cpu_power_w": self.avg_cpu_power_w,
            "avg_gpu_power_w": self.avg_gpu_power_w,
            "min_cpu_power_w": self.min_cpu_power_w,
            "max_cpu_power_w": self.max_cpu_power_w,
            "min_gpu_power_w": self.min_gpu_power_w,
            "max_gpu_power_w": self.max_gpu_power_w,
            "energy_delay_product_js": self.energy_delay_product,
            "cpu_backend": self.cpu_backend,
            "gpu_backend": self.gpu_backend,
            "gpu_device_count": self.gpu_device_count,
            "cpu_model": self.cpu_model,
            "gpu_models": list(self.gpu_models),
        }


def measure_power(
    command,
    interval=DEFAULT_INTERVAL_S,
    gpu_backend="auto",
    cpu_backend="auto",
    device_count=None,
):
    """Run ``command`` and measure the energy it consumes.

    Both CPU and GPU energy are measured by default. Whenever a domain is not
    available on the current machine it is skipped, a note is recorded, and the
    remaining domain is still reported.

    :param command: Program and arguments, e.g. ``["./matmul", "2048"]``.
    :param interval: Seconds between samples (default ``0.1``).
    :param gpu_backend: ``"auto"``, ``"none"``, ``"nvidia"``, ``"amd"`` or
        ``"intel"``.
    :param cpu_backend: ``"auto"``, ``"none"``, ``"rapl-sysfs"`` or ``"perf"``.
    :param device_count: Sample only the first N GPUs (default: all).
    :returns: A :class:`MeasurementResult`.
    :raises ValueError: If ``command`` is empty or a backend name is unknown.

    .. code-block:: python

        from powerlog import measure_power

        result = measure_power(["./matmul", "2048"])
        print(result.total_energy_j, result.cpu_energy_j, result.gpu_energy_j)
    """
    command = list(command)
    if not command:
        raise ValueError("command must contain at least the program name")

    gpu = detect_gpu_backend(gpu_backend, device_count=device_count)
    cpu = detect_cpu_backend(cpu_backend)

    result = MeasurementResult(command=command)
    # Host identification is independent of whether energy can be measured.
    result.cpu_model = cpu_model()

    if gpu is None:
        if gpu_backend in (None, "none", "off"):
            result.notes.append("GPU energy not measured (disabled by request).")
        elif gpu_backend == "auto":
            result.notes.append(
                "GPU energy not measured (no supported GPU backend detected)."
            )
        else:
            result.notes.append(
                f"GPU energy not measured (backend {gpu_backend!r} unavailable)."
            )
    else:
        result.gpu_backend = gpu.describe()
        warmup = gpu.read_power()
        result.gpu_device_count = (
            min(len(warmup), device_count) if device_count else len(warmup)
        )
        names = gpu.device_names()
        result.gpu_models = names[:result.gpu_device_count] if names else []

    if cpu is None:
        if cpu_backend in (None, "none", "off"):
            result.notes.append("CPU energy not measured (disabled by request).")
        elif cpu_backend == "auto":
            result.notes.append(
                "CPU energy not measured (RAPL unavailable; on Linux try "
                "'sysctl kernel.perf_event_paranoid=-1' or run as root)."
            )
        else:
            result.notes.append(
                f"CPU energy not measured (backend {cpu_backend!r} unavailable)."
            )
    else:
        result.cpu_backend = cpu.describe()

    # `perf` must decorate the child process; sysfs counters are read in-loop.
    run_command = cpu.wrap(command) if cpu is not None and cpu.wraps_command else command

    gpu_energy_j = 0.0 if gpu is not None else None
    cpu_energy_j = None
    cpu_start_energy = None
    if cpu is not None and not cpu.wraps_command:
        cpu_start_energy = cpu.read_energy()
        if cpu_start_energy is None:
            result.notes.append("CPU counter returned no reading; CPU energy skipped.")
            cpu = None
        else:
            cpu_energy_j = 0.0

    try:
        proc = subprocess.Popen(run_command)
    except OSError as exc:
        raise ValueError(f"failed to launch {command[0]!r}: {exc}") from exc

    if cpu is not None:
        cpu.start()

    start_ns = last_ns = time.time_ns()
    last_cpu_energy = cpu_start_energy

    while True:
        try:
            proc.wait(timeout=interval)
            break
        except subprocess.TimeoutExpired:
            now_ns = time.time_ns()
            delta_s = (now_ns - last_ns) / NS_IN_S

            gpu_power = None
            per_device = []
            if gpu is not None:
                per_device = gpu.read_power()
                if device_count:
                    per_device = per_device[:device_count]
                gpu_power = sum(per_device) if per_device else 0.0
                gpu_energy_j += gpu_power * delta_s

            cpu_power = None
            if cpu is not None and not cpu.wraps_command:
                reading = cpu.read_energy()
                if reading is not None and last_cpu_energy is not None:
                    delta_j = reading - last_cpu_energy
                    if delta_j >= 0:
                        cpu_energy_j += delta_j
                        cpu_power = delta_j / delta_s if delta_s else None
                    last_cpu_energy = reading

            result.samples.append(
                Sample(
                    timestamp_ns=now_ns,
                    elapsed_s=(now_ns - start_ns) / NS_IN_S,
                    cpu_power_w=cpu_power,
                    gpu_power_w=gpu_power,
                    gpu_per_device_w=per_device,
                )
            )
            last_ns = now_ns

    end_ns = time.time_ns()
    result.total_time_s = (end_ns - start_ns) / NS_IN_S
    result.return_code = proc.returncode

    # Final partial interval, so short runs are not reported as zero energy.
    tail_s = (end_ns - last_ns) / NS_IN_S
    if gpu is not None and tail_s > 0:
        per_device = gpu.read_power()
        if device_count:
            per_device = per_device[:device_count]
        gpu_energy_j += (sum(per_device) if per_device else 0.0) * tail_s

    if cpu is not None:
        if cpu.wraps_command:
            cpu_energy_j = cpu.finish()
            if cpu_energy_j is None:
                result.notes.append("perf did not report a RAPL energy value.")
        else:
            reading = cpu.read_energy()
            if reading is not None and last_cpu_energy is not None:
                delta_j = reading - last_cpu_energy
                if delta_j >= 0:
                    cpu_energy_j += delta_j

    result.cpu_energy_j = cpu_energy_j
    result.gpu_energy_j = gpu_energy_j

    if result.total_energy_j is None:
        result.notes.append(
            "No energy domain could be measured; only runtime is reported."
        )
    return result
