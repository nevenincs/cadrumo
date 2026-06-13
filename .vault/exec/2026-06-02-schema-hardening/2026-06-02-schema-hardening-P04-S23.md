---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S23'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Assess applicability extraction boundaries

## Scope

- `src/aeat/domain/calculations/registry/_applicability.py`

## Description

- Audit the current `_applicability.py` responsibility clusters and
  working-tree diff.
- Identify extraction boundaries that preserve the focused public facade
  and canonical rule-table ownership.
- Record the active shared-worktree formatting WIP as a production-code
  edit blocker.
- Define focused verification surfaces for future extraction commits.

## Outcome

- Completed as an audit-only slice. `_applicability.py` remains unchanged
  by this step because it contains active peer formatting WIP.
- The recommended first implementation slice is tax-route derivation
  extraction behind `_applicability.py` and `applicability.py`
  compatibility re-exports.
- The recommended second implementation slice is Modelo 202 modality
  extraction.
- The seed applicability rule table and `derive_modelo_applicability`
  should remain canonical in `_applicability.py` unless a future ADR
  changes rule authoring ownership.

## Notes

- No production code was edited, so no Python tests were run for this
  audit-only step.
- Vault checks and code-review logging were run before commit.
