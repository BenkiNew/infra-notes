# Sync succeeded, data went stale: how Bash and systemd hid a failure after a move

**Author:** Kostiantyn Bank (ХакерБанк / XAKERBANK) · [XAKERBANK Labs](https://github.com/BenkiNew) · **Date:** 11.10.2026

Published on [DOU](https://dou.ua/forums/topic/62516/) on 11.10.2026 (in Ukrainian); this text is synchronized with that publication. Original source and scripts: [GitHub Gist](https://gist.github.com/BenkiNew/03f6f203f6709b8102b2e47b7b899d02), where the material had the working title “How a failed update became ‘unchanged’”. [Українська версія](../uk/bash-errexit-hidden-failure.md).

Scripts: [minimal reproduction](../../examples/bash-errexit/bash-errexit-repro.sh), [additional contexts](../../examples/bash-errexit/bash-errexit-contexts.sh).

After moving a shared dictionary into a separate directory, the applications kept running, the web pages kept opening, and the synchronization finished with an “unchanged” message. A data check, however, showed that some new entries never reached the dictionary.

Two independent mechanisms caused this. A systemd filesystem restriction prevented the generator from writing data to the new path. And the execution context of `set -e` in Bash let the script continue after a failure and still report success.

This analysis is useful for people who maintain Linux services, write Bash synchronization scripts, or move runtime data between directories. Below: a minimal reproduction, the explanation of the cause, the fix, and the limits of the checks performed. Service names, paths, and data in the examples are fictional.

## Why a working service did not mean current data

Several applications used the dictionary. A generator built it from current data, and consumers loaded the result when their process started.

After the move, the generator was supposed to write files into the new shared directory. But consumers already had the previous dictionary version, and fallback normalization rules handled some unknown forms. Therefore the failed update did not make the services unavailable.

This created a misleading picture:

- services were running;
- pages were opening;
- previous data remained available;
- the sync reported “unchanged”;
- new dictionary entries never appeared.

An HTTP availability check could confirm that the application responds. It could not confirm that its dictionary matches the current data source.

Residual normalization differences became the reason to check the whole path: source → generator → files → loading by consumers.

## First cause: the new directory was not in ReadWritePaths

The loader service used `ProtectSystem=strict`. For its processes the filesystem was mostly read-only, and writes were allowed only into explicitly listed directories.

Before the move the generator worked with an allowed path. After the move the data directory changed, while the service configuration did not.

The generator finished with an error:

```text
Read-only file system
```

At the syscall level this is `EROFS`. It is important to distinguish a read-only restriction from an ordinary permission denial.

Checking file ownership or the result of `chmod` does not explain the whole picture. A process started in a terminal and a process started by systemd with a filesystem sandbox can see different write capabilities for the same path.

The simplified configuration looked like this:

```ini
[Service]
Type=oneshot
User=app
ProtectSystem=strict
ReadWritePaths=/var/lib/example/old-data
```

After the move the generator started writing into `/var/lib/example/shared-data`. The existence of that directory and a correct owner did not add it to `ReadWritePaths` automatically.

The fix was to update the allowed paths. Besides the final data directory, the working directory of the generator must be included if it creates temporary files there.

Disabling `ProtectSystem=strict` for the whole service was not required.

## Second cause: set -e did not stop the block

In the script a critical step was inside a construct of this form:

```bash
(
  set -e
  generate
  compare
) || report_failure
```

The expectation was simple: if `generate` returns an error, `set -e` stops the subshell, and then `report_failure` runs.

For this construct the expectation is wrong.

The subshell is on the left side of `||`. In that context Bash ignores `errexit` inside the tested block. Calling `set -e` inside the parentheses does not restore the expected behavior.

After the generator fails, the next command runs. It compares the files and sees that they did not change. That is true: the failed generator left the old files.

If the last command succeeds, the subshell returns 0. The outer error handler does not run.

Minimal reproduction:

```bash
(set -e; false; printf 'UNCHANGED\n') || printf 'FAILED\n'
```

The block prints `UNCHANGED` and returns status 0.

So the script confused two different states:

1. Generation succeeded and the new data is identical to the previous data.
2. Generation never happened and the old files remained on disk.

Comparing files cannot distinguish these states by itself. First you must check whether the generator completed successfully.

This is documented Bash behavior, not a new interpreter defect. The fix belongs in the application control flow, so proposing a change to Bash itself would not be an appropriate bugfix PR here.

## Moving the code into a function does not remove the trap

The same context affects shell functions. For example:

```bash
generate_and_compare() {
  set -e
  false
  printf 'CONTINUED\n'
}

generate_and_compare || printf 'HANDLED\n'
```

The function continues after `false` and prints `CONTINUED`.

This is an important nuance for refactoring: function behavior depends not only on its body but also on the calling context. Moving a sequence of commands into a function and adding `|| handler` to the call therefore requires a separate check of error handling.

## Why pipefail, an ERR trap and an outer if do not fix this case

There are several attractive but insufficient alternatives here.

### set -o pipefail

`pipefail` changes how the status of a pipeline is determined. The minimal example has no pipeline:

```bash
(
  set -e -o pipefail
  false
  printf 'CONTINUED\n'
) || printf 'HANDLED\n'
```

The command after `false` still runs. `pipefail` is useful for its own purpose, but it does not restore `errexit` in this context.

### trap ERR

An `ERR` trap has context exceptions similar to the `errexit` exceptions. Inheriting the trap with `set -E` does not mean it fires for every failure inside a tested block:

```bash
(
  set -eE
  trap 'printf "ERR_TRAP\n"' ERR
  false
  printf 'CONTINUED\n'
) || printf 'HANDLED\n'
```

In the verified scenario `CONTINUED` is printed and the trap message does not appear. A trap can be useful for logging or termination, but it also has to be verified in the concrete calling context.

### if ! at the outer level

Another attempt is to test the whole block with `if`:

```bash
if ! (
  set -e
  false
  printf 'CONTINUED\n'
); then
  printf 'HANDLED\n'
fi
```

This is a tested context as well: the block continues and returns the status of the last successful command.

The problem is solved by an explicit check of the critical step inside the block.

## Explicit check of the generator

The corrected scheme:

```bash
(
  if ! generate; then
    printf 'Generation failed\n' >&2
    exit 1
  fi

  compare
) || report_failure
```

Here the generator status is checked directly. After its failure an explicit `exit 1` runs, so the file comparison never starts.

This is a scheme, not a standalone executable script: the functions `generate`, `compare`, and `report_failure` must be defined.

Besides the generator, other critical operations deserve an explicit check: reading the initial state, reading the configuration, comparing the result, and creating the update marker. In this context relying on `set -e` alone is not appropriate.

After the fix, the “unchanged” message means that the generator completed successfully and the comparison found no update.

## Restarting consumers as a separate step

Updating the files is not enough if consumers load the dictionary only at startup.

In the analyzed case the loader has `Type=oneshot`. Its `ExecStartPost` runs after `ExecStart` completes successfully. `RemainAfterExit=yes` is not required for this usage.

The consumer restart was moved into a separate step:

1. The unprivileged sync generates data successfully.
2. If the files changed, the sync creates a marker.
3. A separate step checks the marker and restarts the consumers.
4. After success the marker is removed.
5. If the restart fails, the marker remains for a retry.

For other service types the moment when `ExecStartPost` runs is defined by their successful-startup contract. Do not transfer the `oneshot` explanation to every unit without checking.

## What the + prefix means in systemd

A privileged step is a separate trust boundary.

According to the [systemd v257 documentation](https://github.com/systemd/systemd/blob/v257/man/systemd.service.xml), the `+` prefix for a specific command bypasses restrictions set through `User=`, `Group=`, `CapabilityBoundingSet=`, and also filesystem namespace settings such as `PrivateTmp=`.

Therefore it is incorrect to assume that `+` only changes the user while preserving all filesystem restrictions of the unprivileged process.

At the same time, restrictions applied to the whole cgroup, such as `DevicePolicy=`, are not bypassed. The `!` prefix has a different, narrower contract concerning user/group credentials. These are not interchangeable notations.

In practice this means a privileged helper must be short, controlled, and perform only the required operation.

## Marker and concurrent runs

The performed checks confirmed marker behavior for sequential execution. They do not prove correctness when competing writers exist.

A single systemd unit does not run two of its own activations simultaneously. However, a manual script invocation or another unit can create parallel execution.

For such a scenario the simple order “check the marker → restart → remove” requires separate analysis. For example, a new update request can appear during a restart, while the completion of the previous operation removes the shared marker.

`RuntimeDirectory=` and `StateDirectory=` organize directories, but by themselves they do not block competing participants. Atomic rename also does not replace the whole protocol.

`flock` can be part of the solution if all participants use the same lock. The whole cycle must be coordinated: generation, marker creation, restart, and acknowledgement of processing.

In this analysis the concurrent scenario remains unverified. No claim is made about full reliability of the mechanism under parallel runs.

## How the fix was validated

First, a test with a forced generator failure was run against the old code. It reproduced the problem: the script returned 0 instead of the expected non-zero status.

After the fix, five synthetic scenarios passed:

- a generator failure returns an error and does not report “unchanged”;
- an unchanged dictionary does not create a restart request;
- a changed dictionary creates a marker;
- a failed restart retains the marker;
- a successful restart removes the marker.

Additionally, write access to the allowed directories inside the systemd sandbox was verified. Then a real generation was executed separately from the full loader, and consumer state was checked after the restart.

A separate set of synthetic examples confirmed the Bash behavior for a function, `pipefail`, the outer `if !`, and the `ERR` trap.

These checks answer different questions:

| Check | What it confirms |
| --- | --- |
| Minimal Bash example | Failure hiding in a specific context |
| Regression tests | Correct error and marker handling |
| Writing in the systemd sandbox | Availability of allowed paths for the generator |
| Real generation | Successful dictionary update |
| Consumer check | Service operation after restart |

None of them alone proves the correctness of every application business scenario.

## How to reproduce the Bash behavior

The repository and the [public Gist](https://gist.github.com/BenkiNew/03f6f203f6709b8102b2e47b7b899d02) contain two synthetic executable files:

- [bash-errexit-repro.sh](../../examples/bash-errexit/bash-errexit-repro.sh) — the initial example and the corrected check;
- [bash-errexit-contexts.sh](../../examples/bash-errexit/bash-errexit-contexts.sh) — four additional context scenarios.

Download the files and run them explicitly with Bash:

```bash
bash --version
bash bash-errexit-repro.sh
bash bash-errexit-contexts.sh
```

Expected output of `bash-errexit-repro.sh` (the failure message goes to stderr, so stdout/stderr ordering may differ):

```text
UNCHANGED (misleading)
Generation failed
legacy=0 fixed=1
```

Expected output of `bash-errexit-contexts.sh`:

```text
PASS: function
PASS: pipefail
PASS: outer_if
PASS: err_trap
```

The first reproduction confirms `legacy=0 fixed=1`. The test script itself returns 0 only when both expected statuses are confirmed. The contexts script returns 0 only when all four scenarios printed `CONTINUED` with status 0. Both files are synthetic: no data, network access, file writes, or service operations.

The examples were verified with GNU Bash 5.2.26. They do not reproduce the systemd mount namespace and are not a universal contract for other shells or all Bash modes.

## What to take from this case

After a move it is not enough to verify that the process runs and the page responds. Systems with derived data need a separate freshness check.

Changing a data directory also requires checking the service environment: allowed paths, temporary files, and the way consumers load the result.

Finally, `set -e` does not replace an explicit check of critical operations, especially when commands run inside a function or subshell whose status is tested through `||`, `if`, or `!`.

In this case the old files really were “unchanged”. The mistake was using that fact as proof of successful generation.

## Sources and limits

- [GNU Bash: The Set Builtin](https://www.gnu.org/s/bash/manual/html_node/The-Set-Builtin.html) — `set -e` semantics and the contexts where `errexit` is ignored.
- [GNU Bash: Bourne Shell Builtins](https://www.gnu.org/software/bash/manual/html_node/Bourne-Shell-Builtins.html) — `trap` and the context exceptions of `ERR`.
- [systemd v257: systemd.service](https://github.com/systemd/systemd/blob/v257/man/systemd.service.xml) — command prefixes `+` and `!`, `ExecStartPost`, `Type=oneshot`.
- [systemd.exec](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html) — `ProtectSystem=`, `ReadWritePaths=`, `RuntimeDirectory=`, `StateDirectory=`.

The examples generalize our case with fictional service names and paths. The checks confirm Bash control flow, the systemd filesystem sandbox configuration, and marker handling. They do not prove the correctness of every application business scenario and are not a universal contract for other shells, Bash versions, or service types.
