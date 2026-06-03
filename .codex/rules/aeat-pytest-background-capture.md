---
name: aeat-pytest-background-capture
trigger: always_on
---

# Background pytest capture: write the full log to disk, then read

## Rule

When launching pytest in the background, write the **full** output to a log file and read it back from disk. Do not pipe through `Select-Object -Last N` (or `tail -n N`) BEFORE Tee-Object — the truncation happens upstream of the file write, and only the last N lines reach the log. The `FAILED` / `ERROR` summary lines are then lost and the diagnostic value of the background run is destroyed.

## Why

Across one rolling burndown session three separate background pytest captures used the pattern `pytest ... 2>&1 | Tee-Object -FilePath foo.log | Select-Object -Last 5` and produced 5-line log files instead of full output. The fail list went into the truncated pipe before Tee wrote, and Tee dutifully wrote 5 lines. The runs were correct but their value was zero because there was no way to identify which tests failed. Re-running the same probe cost 7 to 45 minutes each pass — the cost of a bad capture is the cost of an extra full suite run.

The correct shape is to let Tee-Object see the full stream, then read the file with `Get-Content -Tail N` or `Select-String -Pattern '^FAILED'` afterwards. The on-disk log keeps every line; the operator decides how to slice it.

## How

- **Good:** background launch with full file capture:
  `uv run --no-sync pytest src/aeat -n auto -q --tb=no --no-header 2>&1 | Out-File -FilePath suite.log -Encoding utf8`
  then post-completion `Get-Content suite.log | Where-Object { $_ -match '^FAILED' } | Sort-Object -Unique` to extract the fail list.

- **Good:** when launching via the Bash/PowerShell `run_in_background: true` flag (which already writes the full pipe to a per-task output file), simply `Read` the output file and use `Select-String` or `Where-Object` to slice the relevant rows.

- **Bad:** `pytest ... 2>&1 | Tee-Object -FilePath suite.log | Select-Object -Last 5` — the file only carries the last 5 lines. Same shape with `| head -N` (bash) is the same trap.

- **Bad:** `pytest ... 2>&1 > suite.log; Get-Content suite.log -Tail 5` looks fine but actually skips stdout redirection unless `2>&1 >` is paired correctly. Prefer `Out-File` or `Tee-Object` without truncation in the pipeline.

- **Bad:** running a 45-minute full suite, watching the summary, and discarding the per-test FAILED rows — the next investigation cycle then has to re-run the suite.

## Source

Operator-direct burndown session 2026-06-02 to 2026-06-03; three suite runs lost their FAILED lists to the Tee-Then-Select truncation antipattern. Recorded under session-honest-followups plan Step P03.S16.
