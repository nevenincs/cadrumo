---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S03'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# declare the closed authorization-status StrEnum and the per-revision authorization record (vaultspec-high-executor)

## Scope

- `src/aeat/core/access_gate/_authorization.py`

## Description

- Reconcile the stale-open authorization type row against `core/access_gate`.
- Ground the row with `uvx vaultspec-rag search "authorization manifest derive per modelo capability registry boundary default deny absence roundtrip test" --type code --limit 12`.
- Confirm `AuthorizationState`, `ModeloAuthorizationEntry`, `ModeloAuthorization`, and the manifest models are declared in the core access-gate authority.
- Confirm the type boundary enforces the two-distinct-renta-years claim before a manifest entry can construct.

## Outcome

- `src/aeat/core/access_gate/_authorization.py` owns the closed authorization state and strict authorization records.
- `uv run --no-sync pytest -q -n 0 src\aeat\core\access_gate\tests\test_authorization_manifest.py src\aeat\tests\test_modelo_authorization_gate.py`: 9 passed.
- No production source changed in this reconciliation pass.

## Notes

- This row is closed as already implemented at current HEAD.
