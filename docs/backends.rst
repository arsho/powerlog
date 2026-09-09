Backends
========

Powerlog separates *what* it measures from *how* the platform exposes it. Each
domain has a set of backends that are probed in priority order and selected
automatically.

Two kinds of backend exist:

:class:`~powerlog.PowerSampler`
   Polled *power* sources reporting Watts. Energy is obtained by integrating the
   sampled power over time. All GPU backends work this way.

:class:`~powerlog.EnergyCounter`
   Monotonic *energy* counters reporting Joules. Energy is obtained by
   differencing the counter. RAPL works this way.

GPU backends
------------

Probed in the order below; the first available one wins.

``nvidia``
^^^^^^^^^^

NVIDIA GPUs through NVML, via
``nvidia-smi --query-gpu=power.draw --format=csv,noheader,nounits``. Power is
summed across visible devices. GPUs without a power sensor report ``[N/A]`` and
contribute zero.

``amd``
^^^^^^^

AMD GPUs through ROCm SMI. Prefers ``amd-smi metric -p --csv`` and falls back to
``rocm-smi --showpower --csv``.

``intel``
^^^^^^^^^

Intel GPUs (SYCL / Level Zero devices) through
``xpu-smi dump -d -1 -m 1 -n 1``, which reports the ``GPU Power (W)`` metric.
``xpumcli`` is accepted as an alias.

CPU backends
------------

``rapl-sysfs`` (preferred)
^^^^^^^^^^^^^^^^^^^^^^^^^^

Reads ``/sys/class/powercap/*/energy_uj`` for each top-level package domain.
Only top-level domains are summed, so core/uncore/DRAM subdomains are not double
counted. Counter wraparound is handled using ``max_energy_range_uj``.

This backend is preferred because it can be polled in lockstep with the GPU,
which yields a CPU power trace in addition to the total.

``perf``
^^^^^^^^

Wraps the command in ``perf stat -e power/energy-pkg/`` and parses the Joules
value from the report. Because ``perf`` only reports at process exit, this
backend produces a total with no trace, and the ``CPU Power (W)`` column of the
samples file stays empty.

Selecting a backend
-------------------

Detection is automatic and you should not normally need to choose a backend. The
case that does require it is a machine with GPUs from more than one vendor, for
example an Intel integrated GPU alongside a discrete NVIDIA card: probing order
prefers NVIDIA, so profiling a SYCL program on the integrated GPU needs
``--gpu-backend intel``.

From the command line:

.. code-block:: bash

   powerlog --gpu-backend amd ./my_program
   powerlog --cpu-backend perf ./my_program

To choose *which domains* are measured rather than which tool reads them, use
``-m/--measure``:

.. code-block:: bash

   powerlog -m gpu ./my_program                 # GPU only
   powerlog -m cpu ./my_program                 # CPU only

From Python:

.. code-block:: python

   from powerlog import measure_power

   result = measure_power(["./my_program"], gpu_backend="amd", cpu_backend="none")

Discovering what is available
-----------------------------

.. code-block:: bash

   powerlog --list-backends

.. code-block:: python

   from powerlog import available_cpu_backends, available_gpu_backends

   for backend in available_gpu_backends():
       print(backend.name, backend.vendor)

Writing a custom backend
------------------------

Subclass :class:`~powerlog.PowerSampler` for a polled source:

.. code-block:: python

   from powerlog.backends import PowerSampler

   class MyMeter(PowerSampler):
       name = "mymeter"
       vendor = "External wall meter"

       @classmethod
       def is_available(cls):
           return True

       def read_power(self):
           return [read_watts_from_somewhere()]

Register it by prepending to the probe order:

.. code-block:: python

   import powerlog.backends as backends

   backends.GPU_BACKENDS = (MyMeter,) + backends.GPU_BACKENDS

Troubleshooting
---------------

*CPU shows* ``n/a``
   RAPL is not readable. Try ``sudo sysctl kernel.perf_event_paranoid=-1`` or
   ``sudo chmod -R a+r /sys/class/powercap``. CPU measurement is Linux only.

*GPU shows* ``n/a``
   No vendor tool was found on ``PATH``. Confirm with ``powerlog
   --list-backends``, and check that the tool runs standalone.

*Energy looks too low on a short run*
   The default 100 ms interval needs a run of at least a few seconds. Lower it
   with ``--interval 0.02`` or increase the workload.
