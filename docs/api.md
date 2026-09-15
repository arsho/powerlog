# Python API Reference

Powerlog is primarily a command-line tool. This API exists for scripting a
measurement from Python — a sweep, a regression test — and mirrors what the
CLI does.

```{currentmodule} powerlog
```

## Measurement

```{eval-rst}
.. autofunction:: powerlog.measure_power

.. autofunction:: powerlog.resolve_program

.. autoclass:: powerlog.MeasurementResult
   :members:
   :undoc-members:
   :member-order: bysource

.. autoclass:: powerlog.Sample
   :members:
   :undoc-members:
   :member-order: bysource
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
