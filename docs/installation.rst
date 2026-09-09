Installation
============

From PyPI
---------

.. code-block:: bash

   pip install powerlog

Powerlog requires Python 3.8 or newer and has no Python dependencies; it uses
only the standard library.

From source
-----------

.. code-block:: bash

   git clone https://github.com/arsho/powerlog.git
   cd powerlog
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .

Vendor requirements
-------------------

The measurement backends are optional and detected at runtime. Install only what
you need for the hardware you are profiling.

GPU
^^^

============  ============================  ==================================
Vendor        Tool                          Ships with
============  ============================  ==================================
NVIDIA        ``nvidia-smi``                NVIDIA driver
AMD           ``rocm-smi`` or ``amd-smi``   ROCm
Intel         ``xpu-smi``                   Intel XPU Manager / oneAPI
============  ============================  ==================================

The tool simply has to be on ``PATH``.

CPU
^^^

CPU energy is read from RAPL on Linux, through one of two sources:

``rapl-sysfs`` (preferred)
   Reads ``/sys/class/powercap/*/energy_uj``. Preferred because it can be polled
   in lockstep with the GPU, which produces a CPU power trace as well as a total.

``perf``
   Wraps the command in ``perf stat -e power/energy-pkg/``. Used as a fallback;
   reports a total only, with no trace.

Both are restricted by default on many distributions. Enable one of them:

.. code-block:: bash

   # allow the perf backend
   sudo sysctl kernel.perf_event_paranoid=-1

   # allow the sysfs backend
   sudo chmod -R a+r /sys/class/powercap

CPU energy measurement is Linux only. On other platforms Powerlog still reports
GPU energy and runtime.

Verifying the installation
--------------------------

List the power sources detected on the current machine:

.. code-block:: bash

   powerlog --list-backends

.. code-block:: text

   Detected power sources:
     GPU:
       nvidia       NVIDIA GPU (nvidia-smi / NVML)
     CPU:
       rapl-sysfs   CPU package (RAPL powercap sysfs)

Then profile a trivial command:

.. code-block:: bash

   powerlog --no-csv sleep 2
