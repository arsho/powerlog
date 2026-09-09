Output Files
============

Each run writes two CSV files. With ``--output run.csv`` they are ``run.csv`` and
``run_samples.csv``; without ``--output`` they default to
``powerlog_output.csv`` and ``powerlog_output_samples.csv``. Use ``--no-csv`` to
print the summary without writing anything.

Values that could not be measured are written as ``n/a``.

Summary file
------------

One header row and one data row, with the energy broken down by domain.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Column
     - Meaning
   * - ``Command``
     - The full command line that was profiled.
   * - ``Return Code``
     - Exit status of the profiled program.
   * - ``Total Time (s)``
     - Wall-clock runtime.
   * - ``CPU Energy (J)``
     - CPU package energy from RAPL.
   * - ``GPU Energy (J)``
     - GPU energy, integrated from sampled power.
   * - ``Total Energy (J)``
     - Sum of the measured domains.
   * - ``CPU Fraction (%)``
     - CPU share of total energy.
   * - ``GPU Fraction (%)``
     - GPU share of total energy.
   * - ``Avg CPU Power (W)``
     - CPU energy divided by runtime.
   * - ``Avg GPU Power (W)``
     - GPU energy divided by runtime.
   * - ``Min GPU Power (W)``
     - Smallest sampled GPU power.
   * - ``Max GPU Power (W)``
     - Largest sampled GPU power.
   * - ``EDP (J*s)``
     - Energy-delay product.
   * - ``GPU Devices``
     - Number of GPUs sampled.
   * - ``CPU Model``
     - Host CPU product name.
   * - ``GPU Model``
     - GPU product name(s), separated by ``;`` if they differ.
   * - ``CPU Source``
     - Which interface the CPU energy was read from.
   * - ``GPU Source``
     - Which tool the GPU power was read from.

Example:

.. code-block:: text

   Command,Return Code,Total Time (s),CPU Energy (J),GPU Energy (J),Total Energy (J),...
   ./matmul 2048,0,12.4180,962.4013,2136.7742,3099.1755,...

Samples file
------------

The power trace, one row per sampling interval.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Column
     - Meaning
   * - ``Timestamp (ns)``
     - Wall-clock time of the sample.
   * - ``Elapsed (s)``
     - Seconds since the program was launched.
   * - ``CPU Power (W)``
     - CPU power over the preceding interval.
   * - ``GPU Power (W)``
     - Total GPU power across the sampled devices.
   * - ``GPU<i> Power (W)``
     - Power of device ``i``; one column per device.

Example:

.. code-block:: text

   Timestamp (ns),Elapsed (s),CPU Power (W),GPU Power (W),GPU0 Power (W),GPU1 Power (W)
   1788966841539282000,0.1051,77.42,238.60,119.30,119.30
   1788966841642857000,0.2086,78.10,241.20,120.90,120.30

.. note::

   The ``CPU Power (W)`` column is empty when the ``perf`` backend is used, since
   ``perf`` only reports a total at process exit. Use the ``rapl-sysfs`` backend
   to obtain a CPU trace.

Working with the output
-----------------------

Load a sweep into a single frame:

.. code-block:: python

   import glob
   import pandas as pd

   frames = [pd.read_csv(path) for path in sorted(glob.glob("results/*.csv"))
             if not path.endswith("_samples.csv")]
   summary = pd.concat(frames, ignore_index=True)
   print(summary[["Command", "Total Energy (J)", "CPU Fraction (%)"]])

Plot a power trace:

.. code-block:: python

   import pandas as pd

   trace = pd.read_csv("powerlog_output_samples.csv")
   ax = trace.plot(x="Elapsed (s)", y=["CPU Power (W)", "GPU Power (W)"])
   ax.set_ylabel("Power (W)")

Bypass the CSV layer entirely and use the result object:

.. code-block:: python

   from powerlog import measure_power

   result = measure_power(["./matmul", "2048"])
   print(result.as_dict())
