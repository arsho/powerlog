"""Powerlog: whole-application CPU and GPU energy measurement.

Powerlog runs an unmodified program as a subprocess and samples CPU and GPU
power in lockstep until it exits, reporting a per-domain energy breakdown.

.. code-block:: python

    from powerlog import measure_power

    result = measure_power(["./matmul", "2048"])
    print(f"total {result.total_energy_j:.1f} J "
          f"(cpu {result.cpu_energy_j:.1f} J, gpu {result.gpu_energy_j:.1f} J)")
"""

__version__ = "0.1.1"

from .backends import (
    EnergyCounter,
    PowerSampler,
    available_cpu_backends,
    available_gpu_backends,
    detect_cpu_backend,
    detect_gpu_backend,
)
from .core import (
    DEFAULT_INTERVAL_S,
    MeasurementResult,
    Sample,
    measure_power,
    resolve_program,
)
from .report import (
    DEFAULT_OUTPUT,
    format_summary,
    print_summary,
    write_samples_csv,
    write_summary_csv,
)

__all__ = [
    "__version__",
    "measure_power",
    "resolve_program",
    "MeasurementResult",
    "Sample",
    "DEFAULT_INTERVAL_S",
    "DEFAULT_OUTPUT",
    "format_summary",
    "print_summary",
    "write_summary_csv",
    "write_samples_csv",
    "PowerSampler",
    "EnergyCounter",
    "detect_gpu_backend",
    "detect_cpu_backend",
    "available_gpu_backends",
    "available_cpu_backends",
]
