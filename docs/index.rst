Powerlog
========

A lightweight harness that measures the CPU and GPU energy consumed by an
unmodified program.

Powerlog runs your program as a subprocess and samples CPU and GPU power in
lockstep until it exits, then reports a per-domain energy breakdown. It needs no
source instrumentation, no profiler integration and no root access on most
systems.

.. code-block:: bash

   pip install powerlog
   powerlog ./my_program --arg value

.. code-block:: python

   from powerlog import measure_power

   result = measure_power(["./my_program", "--arg", "value"])
   print(result.total_energy_j, result.cpu_energy_j, result.gpu_energy_j)

Why whole-application measurement
---------------------------------

Because Powerlog wraps the entire process, the measurement covers everything the
program does: I/O, host-device transfers, kernel launches, synchronization and
iterative solves. Per-kernel profilers miss the energy spent between kernels,
which on many real workloads is a large share of the total.

Supported hardware
------------------

============  ==========================================  ==================
Domain        Source                                      Requirement
============  ==========================================  ==================
NVIDIA GPU    NVML                                        ``nvidia-smi``
AMD GPU       ROCm SMI                                    ``rocm-smi``/``amd-smi``
Intel GPU     Level Zero (SYCL devices)                   ``xpu-smi``
CPU           RAPL package domains                        powercap sysfs or ``perf``
============  ==========================================  ==================

Any domain that is unavailable is reported as ``n/a`` rather than failing the
run.

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   installation
   quickstart
   cli
   backends
   methodology
   output

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api

.. toctree::
   :maxdepth: 1
   :caption: Project

   examples
   changelog
   citation

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
