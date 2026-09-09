Command Line Reference
======================

Synopsis
--------

.. code-block:: text

   powerlog [options] <program> [program arguments...]

Everything after the first non-option token is treated as the command to
profile, so the program's own flags are passed through untouched. Use ``--`` to
disambiguate when the program shares an option name with Powerlog:

.. code-block:: bash

   powerlog --output run.csv -- ./my_program --output its_own.dat

Options
-------

.. argparse::
   :module: powerlog.cli
   :func: build_parser
   :prog: powerlog

Exit status
-----------

Powerlog returns the exit status of the profiled program, so failures propagate
normally. It returns ``2`` for its own usage errors, such as a missing command.

Examples
--------

Basic run, both domains, default output file:

.. code-block:: bash

   powerlog ./matmul 2048

Named output, faster sampling:

.. code-block:: bash

   powerlog --output matmul.csv --interval 0.05 ./matmul 2048

GPU only, no files written:

.. code-block:: bash

   powerlog --no-cpu --no-csv ./matmul 2048

Four GPUs under MPI:

.. code-block:: bash

   powerlog --gpu 4 mpiexec -n 4 ./nbody 131072

Pin the vendor backend:

.. code-block:: bash

   powerlog --gpu-backend amd ./matmul
   powerlog --gpu-backend intel ./matmul_sycl

Inspect available power sources:

.. code-block:: bash

   powerlog --list-backends

Sweep and collect:

.. code-block:: bash

   mkdir -p results
   for n in 1024 2048 4096; do
     powerlog --quiet --output results/matmul_$n.csv ./matmul $n
   done
