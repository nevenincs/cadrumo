---
tags:
  - '#exec'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S10'
related:
  - "[[2026-07-14-honest-all-green-plan]]"
---

# Make the loader-cache cross-session proof and the import-hygiene scan robust under parallel execution without weakening them

## Scope

- `parallel-sensitive tests`

## Description

- Reproduce the parallel-suspect set sequentially at HEAD: the loader-cache
  cross-session proof, the lockfile wait test, and the import-hygiene debt
  scan all pass under `-n 0` (30/30), confirming load artifacts rather than
  regressions.
- Diagnose the two genuinely load-sensitive tests: the lockfile wait test
  gave a 0.25s-holding subprocess a 2s acquisition budget, and the
  cross-session cache proof gave each spawned real pytest session (a full
  registry compile) a 60s timeout — both embed idle-machine latency
  assumptions this heavily loaded shared box violates.
- Widen both to hang guards (30s acquisition window; 300s subprocess
  timeout) with comments stating the budget is a hang guard, not a latency
  assertion. Assertion sets unchanged — the proven contracts (waiting
  acquisition succeeds once the holder releases; a second real session
  reads rather than recompiles the shared pickle) are intact.

## Outcome

Both modules green sequentially (19 passed); ruff clean. Commit
`d48805e4dc`.

## Notes

The import-hygiene debt-count scan needed no change: it passes in both
modes on a quiesced tree; its parallel-run failure traces to live peer
edits landing mid-suite in this active shared worktree, which the P06
final verification run re-checks. No invariant was weakened; both edits
are wall-clock-budget widenings on guards that only exist to prevent
infinite hangs.
