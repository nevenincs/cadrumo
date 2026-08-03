---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:23d905874dcecc241664d01d3571b0effc07800cbf1f0a8fc38c94f9b620c02b'
step_id: 'S71'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add the liveness gate asserting every taxonomy member declares a consumer_module confirmed present in that module's AST or an explicit dormant_reason, discounting docstring mentions and the settings model's own field declarations so neither satisfies the claim by naming a field without using it

## Scope

- `src/cadrumo/core/tests/test_storage_liveness_gate.py`

## Description

- Add the gate asserting every taxonomy member declares a `consumer_module` confirmed present in that module's AST, or an explicit `dormant_reason`.
- Discount docstring mentions and the settings model's own field-declaration sites from counting as "use".
- Derive the digest-exclusion set from the same participation axis this gate makes truthful.

## Outcome

Landed in commit `f7493b4431` (ADR R9's third supporting gate). Found four writer-less categories by AST audit (see S73).

## Notes
