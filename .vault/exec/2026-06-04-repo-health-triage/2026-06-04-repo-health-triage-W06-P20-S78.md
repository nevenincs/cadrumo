---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S78'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W06.P20.S78 Ruff scratch/probe scope verification

Scope: `W06.P20.S78` - Normalize Ruff scope for root scratch and probe
artifacts.

## Description

- Verify the committed Ruff `extend-exclude` configuration for root scratch and
  probe artifacts.
- Re-run full-tree Ruff and confirm the named scratch/probe paths are no longer
  reported.
- Record the remaining full-tree Ruff residuals separately.

## Outcome

Completed. `HEAD` already contains the `pyproject.toml` Ruff `extend-exclude`
block for `run_p04_s11_test.py`, `scratch_probe*.py`, `test_attachment_fix.py`,
`test_m714.py`, and `scripts/classify_m200.py`. Full-tree Ruff output no longer
reports those named artifacts.

Verification:

- `git show HEAD:pyproject.toml` confirmed the committed `extend-exclude` block.
- `uv run --no-sync ruff check . --output-format concise` produced no matches
  for `classify_m200`, `scratch_probe`, `run_p04_s11_test`,
  `test_attachment_fix`, or `test_m714`.
- `uv run --no-sync ruff check . --statistics` exited 1 with 475 remaining
  findings outside the scratch/probe scope.

## Notes

The shared worktree currently contains unrelated dirty `pyproject.toml` changes
from a concurrent test-topology refactor. This step did not stage or modify
`pyproject.toml`.
