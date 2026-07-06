---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S02'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# fingerprint authorization.d manifest fragments into the registry tree fingerprint so cache invalidates on manifest edit (vaultspec-high-executor)

## Scope

- `src/aeat/domain/calculations/registry/_loader.py`

## Description

- Reconcile the stale-open fingerprinting row against the current registry loader.
- Ground the row with `uvx vaultspec-rag search "authorization manifest derive per modelo capability registry boundary default deny absence roundtrip test" --type code --limit 12`.
- Confirm the registry tree fingerprint collection includes `authorization.d` fragments so manifest edits invalidate the cached authority.
- Update the plan row wording from `authorization.toml` to the live directory-mode manifest fragments.

## Outcome

- `src/aeat/domain/calculations/registry/_loader.py` fingerprints the authorization fragment directory as part of registry tree loading.
- `uv run --no-sync pytest -q -n 0 src\aeat\core\access_gate\tests\test_authorization_manifest.py src\aeat\tests\test_modelo_authorization_gate.py`: 9 passed.
- No production source changed in this reconciliation pass.

## Notes

- This row is closed as already implemented at current HEAD; the exec record exists to align the plan with the landed directory-mode implementation.
