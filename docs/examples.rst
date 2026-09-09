Examples
========

Example applications
--------------------

The ``apps/`` directory of the repository contains small, self-contained GPU
programs used to exercise Powerlog. They cover several performance regimes, so
their energy profiles differ in instructive ways.

============  =====================  ==============================================
App           Regime                 Description
============  =====================  ==============================================
``vecadd``    Memory bandwidth       Element-wise vector addition
``matmul``    Compute                Tiled dense matrix multiply (shared memory)
``gemm``      Compute (tuned)        Vendor-library SGEMM (cuBLAS / hipBLAS)
``reduction`` Latency / sync         Shared-memory tree sum reduction
``stencil``   Memory, iterative      2D five-point Jacobi heat diffusion
``nbody``     Compute (FMA heavy)    Direct O(N^2) gravitational N-body step
============  =====================  ==============================================

SYCL ports of ``vecadd`` and ``matmul`` are provided as well, which run on Intel,
NVIDIA and AMD GPUs from a single source.

The CUDA sources build unchanged for both NVIDIA and AMD; a small compatibility
header maps the CUDA runtime names onto HIP when compiled with ``hipcc``.

Building and running:

.. code-block:: bash

   cd apps
   make                  # auto-detects nvcc or hipcc
   make sycl             # SYCL apps

   powerlog ./bin/matmul 2048
   make run              # profile every app into results/

See ``apps/README.md`` for the full guide.

Comparing a kernel against the vendor library
---------------------------------------------

.. code-block:: bash

   powerlog --output hand.csv   ./bin/matmul 4096 20
   powerlog --output vendor.csv ./bin/gemm   4096 20

.. code-block:: python

   import pandas as pd

   hand = pd.read_csv("hand.csv").iloc[0]
   vendor = pd.read_csv("vendor.csv").iloc[0]

   ratio = float(hand["Total Energy (J)"]) / float(vendor["Total Energy (J)"])
   print(f"hand-written kernel uses {ratio:.2f}x the energy of the vendor GEMM")

Sweeping a problem size
-----------------------

.. code-block:: python

   from powerlog import measure_power

   print(f"{'size':>6} {'time (s)':>10} {'energy (J)':>12} {'EDP':>12}")
   for size in (1024, 2048, 4096, 8192):
       r = measure_power(["./bin/matmul", str(size)])
       print(f"{size:>6} {r.total_time_s:>10.2f} "
             f"{r.total_energy_j:>12.1f} {r.energy_delay_product:>12.1f}")

Finding the most energy-efficient configuration
-----------------------------------------------

.. code-block:: python

   from powerlog import measure_power

   results = {}
   for threads in (64, 128, 256, 512):
       r = measure_power(["./bin/nbody", "131072", "100"],
                         )
       results[threads] = r

   best_time = min(results, key=lambda k: results[k].total_time_s)
   best_energy = min(results, key=lambda k: results[k].total_energy_j)
   print(f"fastest: {best_time}, most efficient: {best_energy}")

The two are frequently not the same configuration, which is the main reason to
measure energy rather than infer it from runtime.

Case study: Datalog engine comparison
-------------------------------------

The ``datalog-engine-comparison/`` directory contains a larger study that uses
Powerlog to compare five GPU-accelerated Datalog engines across two recursive
queries and seven graphs. It includes the measurement harness, the analysis
scripts, and the collected results.

A representative finding: the CPU accounts for 32--55% of total energy depending
on the engine, so GPU-only accounting can misrank engines and understate total
energy by up to 2x. See ``datalog-engine-comparison/README.md``.
