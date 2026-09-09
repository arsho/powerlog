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

import csv
import glob
import io
import os
import re
import shutil
import subprocess

__all__ = [
    "PowerSampler",
    "EnergyCounter",
    "NvidiaSmiSampler",
    "RocmSmiSampler",
    "AmdHwmonSampler",
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

#: Timeout for one-off availability probes. Kept short so that a broken or
#: misconfigured vendor tool cannot stall start-up.
_PROBE_TIMEOUT_S = 3

#: Timeout for a power read taken during sampling. Reads happen once per
#: interval, so a slow tool must not be allowed to block the loop.
_READ_TIMEOUT_S = 5


def _run(cmd, timeout=_READ_TIMEOUT_S):
    """Run ``cmd`` and return stdout as text, or ``None`` on any failure."""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
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
                     "--format=csv,noheader,nounits"],
                    timeout=_PROBE_TIMEOUT_S) is not None

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
    """AMD GPU power via ``amd-smi`` or ``rocm-smi`` (ROCm SMI).

    Both tools are tried in order and the first one that actually returns a
    usable reading is kept. This matters because ``amd-smi`` is a Python wrapper
    that resolves ``libamd_smi.so`` through ctypes rather than the dynamic
    loader, so it can be present on ``PATH`` yet fail on module-based systems
    where ``rocm-smi``, a plain binary, works fine.
    """

    name = "amd"
    vendor = "AMD GPU (rocm-smi / amd-smi)"

    #: (tool, power command, product-name command), tried in order.
    _TOOLS = (
        ("amd-smi",
         ["amd-smi", "metric", "-p", "--csv"],
         ["amd-smi", "static", "-a", "--csv"]),
        ("rocm-smi",
         ["rocm-smi", "--showpower", "--csv"],
         ["rocm-smi", "--showproductname", "--csv"]),
    )

    def __init__(self, device_count=None):
        super().__init__(device_count=device_count)
        self._tool = None  # resolved on first successful call

    #: Header substrings that denote a static rating rather than a live draw.
    _NOT_A_DRAW = ("cap", "limit", "max", "min", "default")

    @staticmethod
    def _parse_csv_column(text, match, exclude=()):
        """Return the numeric values of the first column whose header matches.

        Falls back to the last numeric field of each row when no header looks
        right, which keeps older ``rocm-smi`` layouts working.
        """
        if not text:
            return []
        rows = [row for row in csv.reader(io.StringIO(text)) if row]
        if not rows:
            return []

        # Prefer a column that is explicitly an average/current draw, so a
        # layout listing both "Max ... Power" and "Average ... Power" picks the
        # latter regardless of column order.
        index = None
        candidates = [
            position for position, name in enumerate(rows[0])
            if match in name.lower()
            and not any(bad in name.lower() for bad in exclude)
        ]
        for position in candidates:
            low = rows[0][position].lower()
            if "avg" in low or "average" in low or "current" in low:
                index = position
                break
        if index is None and candidates:
            index = candidates[0]

        values = []
        for row in rows[1:]:
            cell = None
            if index is not None and index < len(row):
                cell = row[index]
            else:
                for candidate in reversed(row):
                    try:
                        float(candidate.strip())
                    except (ValueError, AttributeError):
                        continue
                    cell = candidate
                    break
            if cell is None:
                continue
            try:
                # Cells may carry units, e.g. "35.0 W".
                values.append(float(str(cell).strip().split()[0]))
            except (ValueError, IndexError):
                continue
        return values

    @classmethod
    def _probe(cls, timeout=_PROBE_TIMEOUT_S):
        """Return the first (tool, power command) pair that yields a reading."""
        for tool, power_cmd, _ in cls._TOOLS:
            if shutil.which(tool) is None:
                continue
            out = _run(power_cmd, timeout=timeout)
            # Exclude "power cap"/"power limit" columns, which are static.
            if out and cls._parse_csv_column(out, "power", cls._NOT_A_DRAW):
                return tool, power_cmd
        return None, None

    @classmethod
    def is_available(cls):
        tool, _ = cls._probe()
        return tool is not None

    def _resolve(self):
        """Pick and remember a working tool."""
        if self._tool is None:
            self._tool, _ = self._probe()
        return self._tool

    def read_power(self):
        tool = self._resolve()
        if tool is None:
            return []
        for name, power_cmd, _ in self._TOOLS:
            if name != tool:
                continue
            out = _run(power_cmd)
            return self._parse_csv_column(out, "power", self._NOT_A_DRAW)
        return []

    def device_names(self):
        tool = self._resolve()
        if tool is None:
            return []
        for name, _, name_cmd in self._TOOLS:
            if name != tool:
                continue
            out = _run(name_cmd)
            if not out:
                return []
            rows = [row for row in csv.reader(io.StringIO(out)) if row]
            if len(rows) < 2:
                return []
            # rocm-smi calls it "Card Series"/"Card Model"; amd-smi uses
            # "market_name"/"product_name".
            index = None
            for wanted in ("market", "product", "series", "model", "name"):
                for position, column in enumerate(rows[0]):
                    low = column.lower()
                    if wanted in low and "vendor" not in low and "sku" not in low:
                        index = position
                        break
                if index is not None:
                    break
            names = []
            for row in rows[1:]:
                if index is not None and index < len(row) and row[index].strip():
                    names.append(row[index].strip())
            return names
        return []

    def describe(self):
        tool = self._tool or "rocm-smi/amd-smi"
        return f"AMD GPU ({tool})"


class AmdHwmonSampler(PowerSampler):
    """AMD GPU power read straight from the ``amdgpu`` hwmon sysfs nodes.

    The kernel driver exports instantaneous board power under
    ``/sys/class/drm/card*/device/hwmon/hwmon*/power1_average`` in microwatts.
    Reading it needs no ROCm installation at all, which makes this a reliable
    fallback on systems where ``rocm-smi`` or ``amd-smi`` cannot load their
    shared libraries.
    """

    name = "amd-sysfs"
    vendor = "AMD GPU (amdgpu hwmon sysfs)"

    #: Preferred first; power1_input is used by cards without an averaging node.
    _NODES = ("power1_average", "power1_input")

    def __init__(self, device_count=None):
        super().__init__(device_count=device_count)
        self._paths = self._find_inputs()

    @classmethod
    def _find_inputs(cls):
        """Return one readable power node per distinct AMD GPU.

        Several ``cardN`` entries can refer to the same physical board, for
        example when a MI300X is partitioned, so results are de-duplicated on
        the resolved PCI address. Without that the same board power would be
        counted once per partition.
        """
        paths = []
        seen = set()
        pattern = "/sys/class/drm/card[0-9]*/device/hwmon/hwmon[0-9]*"
        for hwmon in sorted(glob.glob(pattern), key=cls._card_sort_key):
            # Only consider hwmon instances belonging to the amdgpu driver.
            try:
                with open(os.path.join(hwmon, "name")) as handle:
                    if handle.read().strip() not in ("amdgpu", "amdgpu_xgmi"):
                        continue
            except OSError:
                continue

            # .../cardN/device/hwmon/hwmonM -> the PCI device behind cardN.
            device = os.path.realpath(
                os.path.dirname(os.path.dirname(hwmon))
            )
            if device in seen:
                continue

            for node in cls._NODES:
                candidate = os.path.join(hwmon, node)
                if os.access(candidate, os.R_OK):
                    paths.append(candidate)
                    seen.add(device)
                    break
        return paths

    @staticmethod
    def _card_sort_key(path):
        """Sort card paths numerically so card2 precedes card10."""
        match = re.search(r"/card(\d+)/", path)
        return (int(match.group(1)) if match else 0, path)

    @classmethod
    def is_available(cls):
        if not cls._find_inputs():
            return False
        return bool(AmdHwmonSampler().read_power())

    def read_power(self):
        values = []
        for path in self._paths:
            try:
                with open(path) as handle:
                    # hwmon reports microwatts.
                    values.append(int(handle.read().strip()) / 1e6)
            except (OSError, ValueError):
                continue
        return values

    def device_names(self):
        names = []
        for path in self._paths:
            # .../cardN/device/hwmon/hwmonM/power1_* -> .../cardN/device
            device = os.path.dirname(os.path.dirname(os.path.dirname(path)))
            label = None
            try:
                with open(os.path.join(device, "product_name")) as handle:
                    label = handle.read().strip()
            except OSError:
                label = None
            if not label:
                # Fall back to the raw PCI id, which needs qualifying.
                try:
                    with open(os.path.join(device, "device")) as handle:
                        pci_id = handle.read().strip()
                    label = f"AMD GPU {pci_id}" if pci_id else None
                except OSError:
                    label = None
            names.append(label or "AMD GPU")
        return names

    def describe(self):
        return self.vendor


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
        return bool(XpuSmiSampler().read_power(timeout=_PROBE_TIMEOUT_S))

    def read_power(self, timeout=_READ_TIMEOUT_S):
        tool = self._tool()
        if tool is None:
            return []
        # -m 1 selects the "GPU Power (W)" metric; -n 1 takes a single sample.
        out = _run([tool, "dump", "-d", "-1", "-m", "1", "-n", "1"],
                   timeout=timeout)
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
GPU_BACKENDS = (NvidiaSmiSampler, RocmSmiSampler, AmdHwmonSampler,
                XpuSmiSampler)


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
                capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S,
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
