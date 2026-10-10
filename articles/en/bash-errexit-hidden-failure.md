# How a failed update became “unchanged”

Original publication: [GitHub Gist](https://gist.github.com/BenkiNew/03f6f203f6709b8102b2e47b7b899d02) · [Українська версія](../uk/bash-errexit-hidden-failure.md).

Scripts: [minimal reproduction](../../examples/bash-errexit/bash-errexit-repro.sh), [additional contexts](../../examples/bash-errexit/bash-errexit-contexts.sh).

Author: **Kostiantyn Bank (ХакерБанк / XAKERBANK)** · [XAKERBANK Labs](https://github.com/BenkiNew) · [DOU](https://dou.ua/users/kostyantin-bank/).

In Bash, `(set -e; generate; compare) || report_failure` can hide a failure in `generate`. The subshell is on the left side of `||`, so `errexit` is ignored inside it. If execution reaches a successful final command, the block returns 0. This is documented Bash behavior; changing Bash itself would not be an appropriate bugfix for this case.

The failure can surface after moving a data directory under a systemd service with `ProtectSystem=strict`: the generator gets EROFS, a subsequent comparison finds the old files unchanged, and the log reports success. The reproduction below demonstrates the control-flow problem only; it does not reproduce the systemd mount namespace.

```bash
(set -e; false; printf 'UNCHANGED\n') || printf 'FAILED\n'
```

This prints `UNCHANGED` and returns 0. Check critical steps explicitly:

```bash
(
  if ! generate; then
    printf 'Generation failed\n' >&2
    exit 1
  fi
  compare
) || report_failure
```

`ReadWritePaths` must include the new data directory and, if the generator writes temporary files there, its working directory. Keep `ProtectSystem=strict`. A privileged service restart can be performed in a separate, narrowly scoped `ExecStartPost` step gated by a change marker. Keep that root step controlled: systemd's `+` prefix requests privileged execution rather than inheriting all restrictions of the unprivileged sync step.

Validation covered a red/green regression for the hidden failure status, an unchanged dictionary without a restart request, and an updated dictionary with a restart request. Two further checks verified that a failed restart retains the marker for retry and a successful restart removes it. The attached `bash-errexit-repro.sh` reproduces `legacy=0, fixed=1` without data, network access, or service operations. These checks validate error handling and the application configuration; they do not establish that every application workflow is correct.

## Reproduction

Download [bash-errexit-repro.sh](../../examples/bash-errexit/bash-errexit-repro.sh) and run it explicitly with Bash:

```bash
bash --version
bash bash-errexit-repro.sh
```

Expected output (the failure message goes to stderr, so stdout/stderr ordering may differ):

```text
UNCHANGED (misleading)
Generation failed
legacy=0 fixed=1
```

The reproduction script itself exits with status 0 only when both expected statuses are confirmed. The `generate`/`compare` snippet above illustrates the fix; those functions are undefined and it is not a standalone runnable example. The executable script uses `false` to inject a synthetic failure.

Verified with GNU Bash 5.2.26. The reproduction demonstrates control flow, not the complete incident or every Bash version.

References: [GNU Bash: The Set Builtin](https://www.gnu.org/s/bash/manual/html_node/The-Set-Builtin.html), [systemd.service: command prefixes and ExecStartPost](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html#ExecStart=).

## Clarifications after technical review

The calling context also affects shell functions: `f() { set -e; false; printf 'CONTINUED\n'; }; f || handler` continues after `false`. Moving the code into a function does not guarantee termination on failure.

`pipefail` controls pipeline status; there is no pipeline here. `ERR` traps have context exceptions similar to `errexit`; `set -E` does not make this block a reliable failure check. Wrapping it in `if ! (set -e; false; printf 'CONTINUED\n'); then handler; fi` also suppresses `errexit` in the tested block. Explicitly check the critical command inside the block.

The application loader uses `Type=oneshot` without `RemainAfterExit=yes`: `ExecStartPost` follows successful completion of `ExecStart`. `RemainAfterExit=yes` is not required. Other service types define successful startup differently.

According to the [systemd v257 documentation](https://github.com/systemd/systemd/blob/v257/man/systemd.service.xml), `+` bypasses not only `User=`, `Group=` and `CapabilityBoundingSet=` for that command, but also filesystem namespace settings such as `PrivateTmp=`. The claim that `+` always preserves the unit's filesystem sandbox is incorrect. Cgroup-wide restrictions, such as `DevicePolicy=`, are not bypassed. The `!` prefix has a different, narrower contract concerning user/group credentials.

The five described tests do not cover concurrent runs. A single systemd unit does not execute two simultaneous activations of itself, but a manual script invocation or another unit can introduce a competing writer. That scenario requires separate tests and coordinated serialization of generation, marker creation, restart and acknowledgement. `RuntimeDirectory=` or `StateDirectory=` alone do not provide locking; atomic rename alone does not replace the complete protocol either. `flock` can be part of that protocol if all participants use the same lock.

The attached `bash-errexit-contexts.sh` tests four additional cases without service operations. These examples concern verified GNU Bash 5.2.26, not every shell or Bash mode.
