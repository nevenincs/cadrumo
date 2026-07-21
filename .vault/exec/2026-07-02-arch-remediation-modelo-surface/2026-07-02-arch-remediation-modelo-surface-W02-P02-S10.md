---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S10'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Declare the iva-wallet owned relation-target binding set and the previous-filing exclusion binding id as one registry or core declaration

## Scope

- `src/aeat/domain/calculations/registry/_validate_relation_sources.py`

## Description

- Move `MODELO_303_IVA_COMPENSATION_BINDING_ID` to the registry domain and derive `IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS` from it.
- Export both on the registry package facade.

## Outcome

One canonical declaration of the iva-wallet-owned binding id and set now lives in the registry domain, reachable by both the domain validator and the application orchestrator. Commit `e353111d8`.

## Notes
