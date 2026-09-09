"""Power measurement backends.

This module provides the vendor-specific backends that :mod:`powerlog.core`
uses to sample power and accumulate energy.

Two families of backends exist:

* :class:`PowerSampler` -- polled *power* sources (Watts). Energy is obtained by
  integrating the sampled power over time. All GPU backends are of this kind.
* :class:`EnergyCounter` -- monotonically increasing *energy* counters (Joules),
  such as RAPL. Energy is obtained by differencing the counter.

Backends are discovered automatically via :func:`detect_gpu_backend` and
:func:`detect_cpu_backend`, so that a plain ``powerlog ./my_program`` measures
both CPU and GPU energy whenever the platform allows it.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess

__all__ = [
    "PowerSampler",
    "EnergyCounter",
    "NvidiaSmiSampler",
    "RocmSmiSampler",
    "XpuSmiSampler",
    "RaplSysfsCounter",
    "PerfRaplCounter",
    "cpu_model",
    "parse_perf_energy",
    "GPU_BACKENDS",
    "CPU_BACKENDS",
    "detect_gpu_backend",
    "detect_cpu_backend",
    "available_gpu_backends",
    "available_cpu_backends",
]

_RUN_TIMEOUT_S = 10


def _run(cmd):
    """Run ``cmd`` and return stdout as text, or ``None`` on any failure."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=_RUN_TIMEOUT_S
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


class PowerSampler:
    """Base class for polled power sources reporting Watts.

    Subclasses must define :attr:`name`, :attr:`vendor` and implement
    :meth:`is_available` and :meth:`read_power`.
    """

    #: Short backend identifier used by the ``--gpu-backend`` CLI option.
    name = "base"
    #: Human readable vendor/device description.
    vendor = "unknown"

    def __init__(self, device_count=None):
        #: Limit sampling to the first ``device_count`` devices (``None`` = all).
        self.device_count = device_count

    @classmethod
    def is_available(cls):
        """Return ``True`` when this backend can be used on this machine."""
        raise NotImplementedError

    def read_power(self):
        """Return a list of per-device power readings in Watts.

        Returns an empty list when no reading could be obtained.
        """
        raise NotImplementedError

    def device_names(self):
        """Return the product name of each device, e.g. ``["NVIDIA A100"]``.

        Returns an empty list when the names cannot be determined.
        """
        return []

    def read_total_power(self):
        """Return the summed power (W) across the selected devices."""
        values = self.read_power()
        if self.device_count is not None:
            values = values[: self.device_count]
        return sum(values) if values else 0.0

    def describe(self):
        """Return a human readable description of the active backend."""
        return self.vendor


class EnergyCounter:
    """Base class for monotonic energy counters reporting Joules."""

    name = "base"
    vendor = "unknown"

    @classmethod
    def is_available(cls):
        """Return ``True`` when this backend can be used on this machine."""
        raise NotImplementedError

    def read_energy(self):
        """Return the cumulative energy in Joules, or ``None`` if unavailable."""
        raise NotImplementedError

    def describe(self):
        """Return a human readable description of the active backend."""
        return self.vendor

    # Counter-style backends read directly; wrapper-style backends (perf) need
    # to decorate the child command instead.
    #: ``True`` when the backend measures by wrapping the target command.
    wraps_command = False

    def wrap(self, cmd):
        """Return ``cmd`` decorated so the backend can measure it."""
        return cmd

    def start(self):
        """Hook called just before the target command is launched."""

    def finish(self):
        """Return total energy in Joules measured for the wrapped command."""
        return None


# --------------------------------------------------------------------------- #
# GPU backends
# --------------------------------------------------------------------------- #


class NvidiaSmiSampler(PowerSampler):
    """NVIDIA GPU power via ``nvidia-smi`` (NVML)."""

    name = "nvidia"
    vendor = "NVIDIA GPU (nvidia-smi / NVML)"

    @classmethod
    def is_available(cls):
        if shutil.which("nvidia-smi") is None:
            return False
        return _run(["nvidia-smi", "--query-gpu=power.draw",
                     "--format=csv,noheader,nounits"]) is not None

    def read_power(self):
        out = _run(["nvidia-smi", "--query-gpu=power.draw",
                    "--format=csv,noheader,nounits"])
        if out is None:
            return []
        values = []
        for line in out.strip().splitlines():
            line = line.strip()
            try:
                values.append(float(line))
            except ValueError:
                # "[N/A]" on GPUs without a power sensor.
                values.append(0.0)
        return values

    def device_names(self):
        out = _run(["nvidia-smi", "--query-gpu=name",
                    "--format=csv,noheader"])
        if out is None:
            return []
        return [line.strip() for line in out.strip().splitlines() if line.strip()]


class RocmSmiSampler(PowerSampler):
    """AMD GPU power via ``amd-smi`` or ``rocm-smi`` (ROCm SMI)."""

    name = "amd"
    vendor = "AMD GPU (rocm-smi / amd-smi)"

    @classmethod
    def _tool(cls):
        for tool in ("amd-smi", "rocm-smi"):
            if shutil.which(tool):
                return tool
        return None

    @classmethod
    def is_available(cls):
        tool = cls._tool()
        if tool is None:
            return False
        return RocmSmiSampler()._raw() is not None

    def _raw(self):
        tool = self._tool()
        if tool is None:
            return None
        if tool == "amd-smi":
            return _run(["amd-smi", "metric", "-p", "--csv"])
        return _run(["rocm-smi", "--showpower", "--csv"])

    def read_power(self):
        out = self._raw()
        if out is None:
            return []
        values = []
        for line in out.strip().splitlines():
            low = line.lower()
            if not line.strip() or "power" in low and "," in line and any(
                c.isalpha() for c in line.split(",")[-1]
            ):
                # Header row such as "device,Average Graphics Package Power (W)".
                continue
            parts = [p.strip() for p in line.split(",")]
            for part in reversed(parts):
                try:
                    values.append(float(part))
                    break
                except ValueError:
                    continue
        return values

    def device_names(self):
        tool = self._tool()
        if tool is None:
            return []
        if tool == "amd-smi":
            out = _run(["amd-smi", "static", "-a", "--csv"])
        else:
            out = _run(["rocm-smi", "--showproductname", "--csv"])
        if out is None:
            return []
        names = []
        for line in out.strip().splitlines()[1:]:
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) >= 2:
                names.append(parts[-1])
        return names


class XpuSmiSampler(PowerSampler):
    """Intel GPU power via ``xpu-smi`` (Level Zero / SYCL devices)."""

    name = "intel"
    vendor = "Intel GPU (xpu-smi, SYCL/Level Zero)"

    @classmethod
    def _tool(cls):
        for tool in ("xpu-smi", "xpumcli"):
            if shutil.which(tool):
                return tool
        return None

    @classmethod
    def is_available(cls):
        if cls._tool() is None:
            return False
        return bool(XpuSmiSampler().read_power())

    def read_power(self):
        tool = self._tool()
        if tool is None:
            return []
        # -m 1 selects the "GPU Power (W)" metric; -n 1 takes a single sample.
        out = _run([tool, "dump", "-d", "-1", "-m", "1", "-n", "1"])
        if out is None:
            return []
        values = []
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 3:
                continue
            try:
                values.append(float(parts[-1]))
            except ValueError:
                continue  # header row
        return values

    def device_names(self):
        tool = self._tool()
        if tool is None:
            return []
        out = _run([tool, "discovery"])
        if out is None:
            return []
        names = []
        for line in out.splitlines():
            if "Device Name" in line:
                names.append(line.split("|")[-1].strip())
        return names


#: GPU backends in auto-detection priority order.
GPU_BACKENDS = (NvidiaSmiSampler, RocmSmiSampler, XpuSmiSampler)


# --------------------------------------------------------------------------- #
# CPU backends
# --------------------------------------------------------------------------- #


class RaplSysfsCounter(EnergyCounter):
    """CPU package energy from the Linux powercap RAPL sysfs interface.

    Reads ``/sys/class/powercap/*/energy_uj`` for every package domain. This is
    the preferred CPU backend because it can be polled in lockstep with the GPU
    samplers, producing a CPU power trace as well as a total.
    """

    name = "rapl-sysfs"
    vendor = "CPU package (RAPL powercap sysfs)"

    def __init__(self):
        self._domains = self._find_domains()
        self._max = {}
        self._last = {}
        self._accumulated = 0.0
        for path in self._domains:
            base = os.path.dirname(path)
            self._max[path] = self._read_int(os.path.join(base, "max_energy_range_uj"))

    @staticmethod
    def _find_domains():
        """Return the ``energy_uj`` paths of all top-level package domains."""
        paths = []
        for base in sorted(glob.glob("/sys/class/powercap/*")):
            name = os.path.basename(base)
            # Top-level package domains only (skip ":0:0" style subdomains such
            # as core/uncore/dram, which would double count).
            if name.count(":") != 1:
                continue
            if not (name.startswith("intel-rapl") or name.startswith("amd")):
                continue
            energy = os.path.join(base, "energy_uj")
            if os.access(energy, os.R_OK):
                paths.append(energy)
        return paths

    @staticmethod
    def _read_int(path):
        try:
            with open(path) as handle:
                return int(handle.read().strip())
        except (OSError, ValueError):
            return None

    @classmethod
    def is_available(cls):
        return bool(cls._find_domains())

    def read_energy(self):
        """Return cumulative energy in Joules across all package domains."""
        if not self._domains:
            return None
        total_uj = 0
        for path in self._domains:
            value = self._read_int(path)
            if value is None:
                continue
            previous = self._last.get(path)
            if previous is not None and value < previous:
                # Counter wrapped around its maximum range.
                span = self._max.get(path)
                if span:
                    self._accumulated += (span - previous + value) / 1e6
                self._last[path] = value
                continue
            self._last[path] = value
            total_uj += value
        return self._accumulated + total_uj / 1e6

    def describe(self):
        return f"{self.vendor}, {len(self._domains)} package domain(s)"


class PerfRaplCounter(EnergyCounter):
    """CPU package energy via ``perf stat -e power/energy-pkg/``.

    Used when the powercap sysfs files are not world readable. Because ``perf``
    wraps the target process, only a single total is available (no CPU power
    trace).
    """

    name = "perf"
    vendor = "CPU package (RAPL via perf)"
    wraps_command = True

    def __init__(self):
        self._output_path = None

    @classmethod
    def is_available(cls):
        if shutil.which("perf") is None:
            return False
        # `perf stat true` succeeds only if the RAPL event is readable.
        try:
            proc = subprocess.run(
                ["perf", "stat", "-e", "power/energy-pkg/", "true"],
                capture_output=True, text=True, timeout=_RUN_TIMEOUT_S,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return "energy-pkg" in proc.stderr and "not supported" not in proc.stderr

    def wrap(self, cmd):
        import tempfile

        self._output_path = tempfile.NamedTemporaryFile(
            prefix="powerlog_perf_", suffix=".txt", delete=False
        ).name
        return ["perf", "stat", "-e", "power/energy-pkg/",
                "-o", self._output_path] + list(cmd)

    def read_energy(self):
        # perf only reports at process exit.
        return None

    def finish(self):
        """Parse the perf report and return CPU package energy in Joules."""
        if self._output_path is None:
            return None
        energy = parse_perf_energy(self._output_path)
        try:
            os.unlink(self._output_path)
        except OSError:
            pass
        self._output_path = None
        return energy


def cpu_model():
    """Return the host CPU product name, or ``None`` if it cannot be determined.

    Reads ``/proc/cpuinfo`` on Linux and falls back to ``sysctl`` on macOS.
    """
    try:
        with open("/proc/cpuinfo") as handle:
            for line in handle:
                if line.startswith(("model name", "Model name")):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    out = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if out and out.strip():
        return out.strip()
    import platform

    return platform.processor() or None


def parse_perf_energy(path):
    """Extract Joules for ``power/energy-pkg/`` from a ``perf stat`` report.

    :param path: Path to the file produced by ``perf stat -o``.
    :returns: Energy in Joules, or ``None`` when the value is not present.
    """
    try:
        with open(path) as handle:
            for line in handle:
                if "energy-pkg" not in line:
                    continue
                tokens = line.strip().split()
                for index, token in enumerate(tokens):
                    if token.lower().startswith("joule"):
                        raw = tokens[index - 1].replace(",", "")
                        try:
                            return float(raw)
                        except ValueError:
                            return None
    except OSError:
        pass
    return None


#: CPU backends in auto-detection priority order.
CPU_BACKENDS = (RaplSysfsCounter, PerfRaplCounter)


# --------------------------------------------------------------------------- #
# Detection helpers
# --------------------------------------------------------------------------- #


def available_gpu_backends():
    """Return the list of GPU backend classes usable on this machine."""
    return [backend for backend in GPU_BACKENDS if backend.is_available()]


def available_cpu_backends():
    """Return the list of CPU backend classes usable on this machine."""
    return [backend for backend in CPU_BACKENDS if backend.is_available()]


def detect_gpu_backend(preferred="auto", device_count=None):
    """Instantiate a GPU power sampler.

    :param preferred: ``"auto"`` to probe every vendor, ``"none"`` to disable
        GPU measurement, or one of ``"nvidia"``, ``"amd"``, ``"intel"``.
    :param device_count: Limit sampling to the first N devices.
    :returns: A :class:`PowerSampler` instance, or ``None`` if unavailable.
    """
    if preferred in (None, "none", "off"):
        return None
    if preferred == "auto":
        for backend in GPU_BACKENDS:
            if backend.is_available():
                return backend(device_count=device_count)
        return None
    for backend in GPU_BACKENDS:
        if backend.name == preferred:
            if not backend.is_available():
                return None
            return backend(device_count=device_count)
    raise ValueError(f"unknown GPU backend: {preferred!r}")


def detect_cpu_backend(preferred="auto"):
    """Instantiate a CPU energy counter.

    :param preferred: ``"auto"`` to probe every source, ``"none"`` to disable
        CPU measurement, or one of ``"rapl-sysfs"``, ``"perf"``.
    :returns: An :class:`EnergyCounter` instance, or ``None`` if unavailable.
    """
    if preferred in (None, "none", "off"):
        return None
    if preferred == "auto":
        for backend in CPU_BACKENDS:
            if backend.is_available():
                return backend()
        return None
    for backend in CPU_BACKENDS:
        if backend.name == preferred:
            if not backend.is_available():
                return None
            return backend()
    raise ValueError(f"unknown CPU backend: {preferred!r}")
