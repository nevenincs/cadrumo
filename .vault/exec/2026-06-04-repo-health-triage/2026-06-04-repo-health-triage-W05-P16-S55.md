---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S55'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W05.P16.S55 - normalize Ruff scope for scratch and probe files

Scope: Wave `W05`; Phase `W05.P16`; Step `S55`.

## Description

- Added a Ruff `extend-exclude` block for root one-off scratch/probe artifacts and the M200 classifier scratch script.
- Verified the full Ruff invocation no longer reports findings for those scratch/probe paths.
- Left unrelated Ruff findings for production and test code to their dedicated follow-up rows.

## Outcome

The S55 scope ratchet is closed. Root investigation artifacts no longer inflate the Ruff diagnostic surface that is supposed to track package code.

## Notes

`pyproject.toml` already contained unrelated dependency WIP before this slice. The S55 implementation hunk was kept separate from that pre-existing dependency hunk for staging and review.

Verification:

- `uv run --no-sync ruff check pyproject.toml`
- `uv run --no-sync ruff check .` still exits nonzero because of unrelated scheduled Ruff findings, but reports no `scratch_probe`, `run_p04_s11_test`, `test_attachment_fix`, `test_m714`, or `classify_m200` paths.
