---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:ee24e34a1671f1486a4dcbdd03da56884a876b7ad94c0386863525e82179643b'
step_id: 'S05'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# write roundtrip tests asserting manifest absence authorizes zero and a listed modelo derives its capability (vaultspec-standard-executor)

## Scope

- `src/aeat/core/access_gate/tests/test_authorization_manifest.py`

## Description

- Reconcile the stale-open authorization roundtrip-test row against current tests.
- Ground the row with `uvx vaultspec-rag search "authorization manifest derive per modelo capability registry boundary default deny absence roundtrip test" --type code --limit 12`.
- Confirm the tests cover absent/empty manifest default-deny behavior, fragment hydration, listed-modelo derivation, malformed entries, duplicate modelos, and manifest directory resolution.
- Update the plan scope from the old flat test path to the current access-gate test module.

## Outcome

- `src/aeat/core/access_gate/tests/test_authorization_manifest.py` covers the authorization manifest loader and derivation contract.
- `uv run --no-sync pytest -q -n 0 src\aeat\core\access_gate\tests\test_authorization_manifest.py src\aeat\tests\test_modelo_authorization_gate.py`: 9 passed.
- No production source changed in this reconciliation pass.

## Notes

- This row is closed as already implemented at current HEAD.
