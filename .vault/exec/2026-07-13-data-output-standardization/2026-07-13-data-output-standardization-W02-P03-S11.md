---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:1504d570c2dc496378c4a451d37a9083a3acfb09730ca50ee89c25a7615b7e6c'
step_id: 'S11'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Add retention pruning for per-run trace directories

## Scope

- `src/cadrumo/core/observability/_store.py`

## Description

- Add a `cadrumo_runs_retention_days` Settings field (default 30) as the run-trace retention window.
- Add `prune_run_traces(retention_days=None, settings=None)` to the observability store: enumerate run-id subdirectories under `cadrumo_runs_dir`, remove any whose modification time is older than the cutoff, and return the count removed. Best-effort throughout - an unenumerable runs dir, an unreadable entry, or a failed removal is logged and skipped, never raised.
- Add real-behavior tests: age-cutoff removal, in-window retention, non-run-directory scope exclusion, missing-runs-dir no-op, and the central-settings default.
- Add the env-template entry and regenerate the env-overrides reference.

## Outcome

The per-run trace store now has a declared retention lifecycle rather than accumulating one subdirectory per run forever. Gates: the run-trace retention suite (5 tests) and the settings/env-parity + env-reference freshness gates pass; the full observability suite is 82 passed under sequential (`-n 0`); ruff clean.

## Notes

Age is measured from each run directory's modification time (its last write) rather than a parsed `trace.json` timestamp, so crashed runs that never produced a valid `trace.json` are pruned too instead of accumulating unreadable. Run traces are plain on-disk files with no bucket session, so the tests set directory mtimes directly with `os.utime` and prune under the real clock - no frozen clock is needed or used.
