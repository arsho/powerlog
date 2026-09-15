# Command Line Reference

## Synopsis

```text
powerlog [options] <program> [program arguments...]
```

Everything after the first non-option token is treated as the command to
profile, so the program's own flags are passed through untouched. Use `--` to
disambiguate when the program shares an option name with Powerlog:

```bash
powerlog --output run.csv -- ./my_program --output its_own.dat
```

## Options

```{argparse}
:module: powerlog.cli
:func: build_parser
:prog: powerlog
```

## Exit status

Powerlog returns the exit status of the profiled program, so failures propagate
normally. Its own errors use the conventional shell codes:

| Status | Meaning |
| ------ | ------- |
| `0` | The program ran and exited successfully. |
| *n* | The program exited with status *n*; the summary shows it too. |
| `2` | Usage error, such as a missing command. |
| `126` | The program was found but is not executable. Nothing was measured. |
| `127` | The program was not found on `PATH`. Nothing was measured. |

The program is resolved before any measurement starts, so a typo is reported by
Powerlog itself rather than by a wrapper such as `perf`:

```text
$ powerlog matmul 1024 10
powerlog: error: 'matmul' is not on PATH. It exists in the current
directory, so run it as './matmul'
```

## Examples

Basic run, both domains, default output file:

```bash
powerlog ./matmul 2048
```

Named output, faster sampling:

```bash
powerlog --output matmul.csv --interval 0.05 ./matmul 2048
```

GPU only, no files written:

```bash
powerlog -m gpu --no-csv ./matmul 2048
```

Limit sampling to the first four GPUs of the node:

```bash
powerlog --gpu 4 ./nbody 131072
```

Inspect available power sources:

```bash
powerlog --list-backends
```

Sweep and collect:

```bash
mkdir -p results
for n in 1024 2048 4096; do
  powerlog --quiet --output results/matmul_$n.csv ./matmul $n
done
```
