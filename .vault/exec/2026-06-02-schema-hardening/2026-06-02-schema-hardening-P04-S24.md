---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S24'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Assess workbook parity extraction boundaries

## Scope

- `src/aeat/domain/calculations/registry/_workbook_parity.py`

## Description

- Audit the current `_workbook_parity.py` responsibility clusters and
  working-tree diff.
- Identify staged extraction boundaries for scanning, runner/conversion,
  and parity comparison families.
- Record public re-export and external-runner preservation constraints.
- Define focused verification surfaces for future extraction commits.

## Outcome

- Completed as an audit-only slice. `_workbook_parity.py` had no local
  diff at audit time and remains unchanged by this step.
- The recommended first implementation slice is extraction of workbook
  scanning/classification and coverage inventory behind `_workbook_parity.py`
  compatibility re-exports.
- Runner/conversion extraction should happen after scanning and must
  preserve timeout settings, error types, and executable-discovery
  behavior exactly.

## Notes

- No production code was edited, so no Python tests were run for this
  audit-only step.
- Vault checks and code-review logging were run before commit.
