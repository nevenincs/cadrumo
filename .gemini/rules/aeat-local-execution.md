---
name: aeat-local-execution
trigger: always_on
---

# AEAT local execution

Use `fd` and `rg` for discovery and search. Prefer native PowerShell in this
environment; do not wrap normal commands in `pwsh`, `powershell`, `cmd /c`, or
`bash -lc` unless a tool requires a separate shell process.

Use the uv-managed workflow, and prefer platform-agnostic project configuration
over shell-specific variants.

**Run real gates.** Do not use mocks, fakes, stubs, patches, monkeypatches,
skip, xfail, or tautological assertions as shortcuts.

**Re-run before blaming the code.** Registry-suite failures under parallel
pytest are more often a loader-cache race than a real regression, and this
worktree's backing share fails under concurrent I/O, so a dead parallel run is
more likely the drive than the code. Re-run sequentially before triaging.

## Capturing a background run

Write the **full** output to a log file and read it back from disk. Do not pipe
through `Select-Object -Last N` or `tail -n N` **before** `Tee-Object` — the
truncation happens upstream of the file write, so only the last N lines reach
the log and the `FAILED` summary is lost. The cost of a bad capture is an extra
full suite run.

## How

- **Good:** `... 2>&1 | Out-File -FilePath suite.log -Encoding utf8`, then slice
  the file for `^FAILED`.
- **Bad:** `... | Tee-Object -FilePath suite.log | Select-Object -Last 5`.
- **Bad:** citing a pipeline's exit status as the run's result — a pipeline exits
  with its **last** command's status. Redirect to a file, capture the status on
  the very next command, then slice.
