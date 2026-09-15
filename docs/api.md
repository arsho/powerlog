# Python API Reference

```{currentmodule} powerlog
```

Everything listed here is importable directly from the `powerlog` package.

```{autosummary}
:nosignatures:

measure_power
MeasurementResult
Sample
resolve_program
format_summary
print_summary
write_summary_csv
write_samples_csv
detect_gpu_backend
detect_cpu_backend
available_gpu_backends
available_cpu_backends
PowerSampler
EnergyCounter
```

## Measurement

```{eval-rst}
.. autofunction:: powerlog.measure_power

.. autoclass:: powerlog.MeasurementResult
   :members:
   :undoc-members:
   :member-order: bysource

.. autoclass:: powerlog.Sample
   :members:
   :undoc-members:
   :member-order: bysource

.. autofunction:: powerlog.resolve_program
```

## Reporting

```{eval-rst}
.. automodule:: powerlog.report
   :members:
   :undoc-members:
   :member-order: bysource
```

## Backends

```{eval-rst}
.. automodule:: powerlog.backends
   :members:
   :undoc-members:
   :member-order: bysource
   :show-inheritance:
```

## Command line

```{eval-rst}
.. automodule:: powerlog.cli
   :members:
   :undoc-members:
```

## Constants

```{eval-rst}
.. autodata:: powerlog.DEFAULT_INTERVAL_S
   :no-value:

   Default interval, in seconds, between power samples (``0.1``).

.. autodata:: powerlog.DEFAULT_OUTPUT
   :no-value:

   File name used when ``--output`` is not supplied
   (``"powerlog_output.csv"``).

.. autodata:: powerlog.core.MIN_RELIABLE_SAMPLES
   :no-value:

   Sample count below which a run is flagged as too short to integrate
   (``10``).
```
