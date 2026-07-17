---
tags:
  - '#exec'
  - '#arch-remediation-data-budget'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-02-arch-remediation-data-budget-plan]]"
---

# Add a size-budget gate asserting the _data tree is at or under 550 MB, failing with a message that names the data-budget ADR and the two breach options raise-by-ADR or split

## Scope

- `src/aeat/tests/test_data_size_budget.py`

## Description

- Author `test_data_size_budget.py`: sum the `src/aeat/_data` file bytes and assert at or under a declared 550 MiB budget, failing with a message naming the data-budget ADR and the two breach options (raise-by-ADR or corpus split).

## Outcome

The `_data` tree (currently ~485 MiB summed) is a monitored, ADR-governed number; the next doubling becomes a decision, not a surprise.

## Notes

Budget expressed in MiB to match the operator-facing `du -sh` reading; the gate sums actual file bytes for cross-filesystem determinism rather than block-rounded `du`.
