---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# derive the per-modelo authorization capability from the manifest at the registry boundary, never authored independently (vaultspec-high-executor)

## Scope

- `src/aeat/domain/calculations/registry/_authority.py`

## Description

- Reconcile the stale-open registry-bound derivation row against the current authority.
- Ground the row with `uvx vaultspec-rag search "authorization manifest derive per modelo capability registry boundary default deny absence roundtrip test" --type code --limit 12`.
- Confirm `ValidatedRegistryAuthority.authorization()` derives from the loaded manifest and `modelo_has_engine()`.
- Confirm the capability is not authored per revision or duplicated outside the registry authority boundary.

## Outcome

- `src/aeat/domain/calculations/registry/_authority.py` derives per-modelo authorization from the manifest and engine presence.
- `uv run --no-sync pytest -q -n 0 src\aeat\core\access_gate\tests\test_authorization_manifest.py src\aeat\tests\test_modelo_authorization_gate.py`: 9 passed.
- No production source changed in this reconciliation pass.

## Notes

- This row is closed as already implemented at current HEAD; the plan scope was updated from the old `domain/modelos/registry` path to the live calculations registry authority.
