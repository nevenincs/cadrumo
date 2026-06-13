---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-06-09'
step_id: 'S01'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---




# extract complexity calculation heredocs with zero-noise success filtering

## Scope

- `scripts/audit_complexity.py`

## Description

- Extracted complexity calculation logic from the `justfile` into a standalone, robust Python script `scripts/audit_complexity.py`.
- Configured the script to execute `radon cc`, `radon mi`, and `complexipy` with custom thresholds.
- Enforced a zero-noise output policy by filtering out success messages and only showing actionable grade violations (CC >= C, MI < A, Cognitive Complexity > 20).
- Handled cases where `complexipy` is missing or fails to parse files gracefully.

## Outcome

The script `scripts/audit_complexity.py` was created and successfully executed via `uv run --no-sync python scripts/audit_complexity.py`. It correctly filtered out passing files and listed the exact functions/files exceeding complexity thresholds.

## Notes

