# Background pytest capture: write the full log to disk, then read it

## Rule

When launching pytest in the background, write the **full** output to a log file
and read it back from disk. Do not pipe through `Select-Object -Last N` or
`tail -n N` **before** `Tee-Object` — the truncation happens upstream of the
file write, so only the last N lines reach the log and the `FAILED` / `ERROR`
summary is lost.

## Why

The cost of a bad capture is the cost of an extra full suite run. Three
background captures in one session used the truncate-then-tee shape and produced
five-line log files; the runs were correct but worthless, because there was no
way to identify which tests failed, and re-running cost tens of minutes each.

## How

- **Good:** let the tee see the full stream, then slice the file afterwards:
  `uv run --no-sync pytest src/cadrumo -n auto -q --tb=no --no-header 2>&1 | Out-File -FilePath suite.log -Encoding utf8`
  then
  `Get-Content suite.log | Where-Object { $_ -match '^FAILED' } | Sort-Object -Unique`.
- **Good:** when launching via the harness `run_in_background` flag, which
  already writes the full pipe to a per-task output file, read that file and
  slice it.
- **Bad:** `pytest ... | Tee-Object -FilePath suite.log | Select-Object -Last 5`
  — the file carries only the last five lines. `| head -N` is the same trap.
- **Bad:** running a long suite, reading the summary, and discarding the
  per-test FAILED rows; the next investigation has to re-run the suite.
- **Bad:** citing a pipeline's exit status as the run's result — a pipeline
  exits with its **last** command's status. Redirect to a file, capture the
  status on the very next command, then slice the file.

Companion: `aeat-local-execution` (re-run sequentially before triaging a
parallel failure as a regression).
