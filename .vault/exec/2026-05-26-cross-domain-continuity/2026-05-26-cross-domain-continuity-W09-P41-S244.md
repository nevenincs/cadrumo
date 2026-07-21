---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-10'
step_id: 'S244'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# FU-W02-C MUST-FIX rewrite test_legal_entity_can_create_modelo_202_work_unit with isolated_runtime_profile fixture

## Scope

- `currently uses monkeypatch AEAT_SECRET_STORE_BACKEND=unsecured to work around the storage regression S209`
- `once S209 lands the unsecured workaround in this test must be removed`
- `blocks Wave-2 quality-gate sign-off`
- `src/aeat/entrypoints/cli/test_modelo_202_modality.py`

## Description

- Reconciles the checked historical S244 row against the direct evidence named in the related reconciliation audit.
- Adds no production-source change.

## Outcome

- Restores the one-Step/one-record traceability edge for this historical checked row.
- The related audit names the exact supporting audit, execution record, or commit evidence.

## Notes

- This record asserts no new implementation or re-run verification; it records evidence reconciliation only.
