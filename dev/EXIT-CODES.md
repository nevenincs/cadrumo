# The exit-code contract

A command's exit code is its contract with CI and with the developer. This
document states that contract; the numbers it names live in
`dev/exit_codes.py`, which is its machine-readable form, and
`dev/tests/test_exit_code_contract.py` enforces both.

## The governing distinction

A tool that RAN and found something is not the same event as a tool that FAILED
TO RUN. The first is a measurement; the second is the absence of one. Any
mechanism that maps both onto the same status hides a broken tool, and the shape
it usually takes is `some-scanner ; exit 0`: a literal `exit 0` maps *every*
non-zero status onto success, so a scanner that was never installed, whose
config no longer parses, or that crashed halfway through reports exactly like a
clean run.

Advisory intent is legitimate, but it suppresses only the statuses that mean
"findings" (`FINDINGS_CODES`, `{1}` by default). Anything else propagates as
`TOOL_BROKEN` (7), which `ADVISORY_BROKEN` is the advisory-facing name for. One
code serves gates and advisories alike: "the scanner did not run" means the
same thing whichever kind of command hit it, and whether that gates is carried
by the command's verb class.

## Verb classes, keyed to CONSEQUENCE

| Verb class | Gates? | 0 means | Non-zero means |
|---|---|---|---|
| `check-*` | yes | read-only inspection found nothing | a finding, or the checker could not run |
| `fix-*` | on failure only | the repair pass completed | the repair pass failed; `5` under `CADRUMO_FIX_STRICT` when it had to change something |
| `test-*` | yes | tests ran and passed | a failure |
| `audit-*` | no | the scan completed | `7` when a scanner could not run |
| `build-*` | yes | artefacts produced | the build failed |
| `health-*` | never | always; the output is the product | — |

`check` is read-only and `fix` mutates: that is the whole of the difference
between them, and it is why `fix` may not be used as a gate. A `fix` that
exited non-zero because it changed a file would make every clean local
development loop red.

The dependency vulnerability scan is a `check`, not an `audit`:
`just check-dependency-vulnerabilities` exits `1` on a published advisory
against a pinned version and `7` when advisory data cannot be obtained. A
published advisory is a verdict about a specific artefact with a mechanical
remedy (change the pin); a duplication, dead-code or complexity scan yields a
lead to confirm by hand. `uv audit` has exited 0 while printing advisories, so
the verdict is derived from the printed summary AND the exit code, never from
the exit code alone.

## The numbers

| Code | Name | Meaning |
|---|---|---|
| 0 | `OK` | ran; nothing that gates |
| 1 | `FAILED` | ran; reported a gating result |
| 2 | `INIT_HOST_TOOL_MISSING` | `just init`: a required host tool is absent |
| 3 | `INIT_STALE` | `just init check`: the environment is stale relative to its inputs |
| 4 | `INIT_STEP_FAILED` | `just init`: one bootstrap step failed |
| 5 | `DRIFT` | managed content differs from its generated form (`fix` under `CADRUMO_FIX_STRICT`, a `--check` pin refresh) |
| 6 | `INIT_LOCKED` | `just init`: the environment is held open by another process |
| 7 | `TOOL_BROKEN` (`ADVISORY_BROKEN`) | the tool failed to RUN: it started and could not do its job |
| 8 | `NOTHING_SELECTED` | nothing ran; `selection_result` maps pytest's "no tests collected" (5) onto it |
| 127 | `TOOL_MISSING` | required tool absent, no fallback |

An absent executable found at dispatch time is `127`, the shell's own
command-not-found status, legible without a lookup table.

## Aggregates and pipelines

An aggregate composes independent measurements. `just check-code`
(`dev/quality/suite.py`) runs every gate even after one fails, because the
reader wants the complete picture and fail-fast costs one CI round-trip per
defect. It exits with the FIRST non-zero status it saw: the earliest failure is
the one that may explain the rest, and its value distinguishes a gate that
found something (1) from one that could not run (127).

`just init` is a pipeline and is deliberately FAIL-FAST. Its first step
provisions the environment the rest run inside, so a later step is not an
independent measurement: its result is unreadable once the step before it
failed. Run every step when each step ANSWERS SOMETHING; stop at the first
failure when each step DEPENDS ON the one before it.

`just audit-code` (`dev/audit/advisory.py`) runs every advisory dimension and
exits `0` whatever they found, and `7` when a dimension's scanner could not
produce data.

## Findings statuses are declared per tool

The default `FINDINGS_CODES` is `{1}`, but not every tool uses 1 for findings:
vulture reports dead code with 3 and reserves 1 and 2 for invalid input and
invalid arguments. Read under `{1}`, a vulture finding looks like a broken
scanner and a broken vulture invocation looks like a finding. So a tool that
does not use 1 states its own findings statuses: `advisory_result` takes them
as an argument, and `dev/quality/fixes.py` declares them per repair command
(`ruff format` has none).

## Where the contract lives

- `dev/exit_codes.py`: the constants and the two mapping functions.
- `dev/tests/test_exit_code_contract.py`: asserts the mapping functions behave
  as written and that no justfile recipe re-implements a swallow (`; exit 0`,
  a trailing bare `exit 0`, `|| true`) or tests `$LASTEXITCODE` on a standalone
  recipe line, where it is always unset.
- `dev/tests/test_just_exit_forwarding.py`: proves every recipe line hands its
  command's own status to `just` under the repository's shell settings.
