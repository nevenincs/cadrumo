---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S22'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Assess record-design extraction boundaries

## Scope

- `src/aeat/domain/calculations/registry/_record_design.py`

## Description

- Audit the current `_record_design.py` parser and derivation families.
- Identify extraction boundaries that preserve the public dispatcher and
  registry re-export contract.
- Record the active shared-worktree formatting WIP as a production-code
  edit blocker.
- Define focused verification surfaces for future extraction commits.

## Outcome

- Completed as an audit-only slice. `_record_design.py` remains
  unchanged by this step because it contains active peer formatting WIP.
- The recommended first implementation slice is workbook/XLS parser
  extraction behind `_record_design.py` compatibility re-exports.
- PDF text and visual-chart parsing should move together initially.
- Completeness and coverage derivation can move separately after parser
  extraction or after the active peer formatting WIP lands.

## Notes

- No production code was edited, so no Python tests were run for this
  audit-only step.
- Vault checks and code-review logging were run before commit.
