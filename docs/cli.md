# Command Line Reference

```text
powerlog [options] <program> [program arguments...]
```

Everything after the first non-option token is the command to profile, so the
program's own flags are passed through untouched. Use `--` to disambiguate when
the program shares an option name with Powerlog:

```bash
powerlog --output run.csv -- ./my_program --output its_own.dat
```

## Options

```{argparse}
:module: powerlog.cli
:func: build_parser
:prog: powerlog
:noepilog:
```

## Exit status

Powerlog returns the exit status of the profiled program. Its own errors use the
conventional shell codes.

`0`
: The program ran and exited successfully.

*n*
: The program exited with status *n*; the summary reports it as well.

`2`
: Usage error, such as a missing command.

`126`
: The program was found but is not executable. Nothing was measured.

`127`
: The program was not found on `PATH`. Nothing was measured.

The program is resolved before any measurement starts, so a typo is reported by
Powerlog itself rather than by a wrapper such as `perf`:

```text
$ powerlog matmul 1024 10
powerlog: error: 'matmul' is not on PATH. It exists in the current
directory, so run it as './matmul'
```

## Examples

```bash
powerlog ./matmul 2048                                   # both domains
powerlog --output matmul.csv --interval 0.05 ./matmul 2048
powerlog -m gpu --no-csv ./matmul 2048                   # GPU only, no files
powerlog --gpu 4 ./nbody 131072                          # first 4 GPUs
powerlog --list-backends                                 # inspect the machine
```
