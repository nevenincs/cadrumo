---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S117'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# Close AFR-015 for AEAT browser session store

## Scope

- `src/aeat/adapters/outbound/aeat/auth/_session_store.py`
- `src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py`
- `src/aeat/adapters/outbound/aeat/auth/test_authenticator.py`
- `src/aeat/adapters/persistence/storage/test_namespace_registry.py`

## Description

- Replaced the session store's duplicated namespace string and schema version with `AEAT_BROWSER_SESSION_NAMESPACE` from the central storage namespace registry.
- Derived the store's classification, persisted namespace, and schema version from the registered namespace definition.
- Updated the raw-payload authenticator test helper to use the same central namespace definition rather than the session store's private implementation constant.
- Extended the namespace discovery test so production code that imports registered namespace constants through the auth adapter's relative import form is still audited.
- Expanded the real session-store roundtrip test to assert the stored secure-object row uses the registered namespace, sensitivity, and schema version, and that the persisted lookup key is the hashed 32-byte value rather than the raw logical path.

## Outcome

- `uv run --no-sync ruff check src/aeat/adapters/outbound/aeat/auth/_session_store.py src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py src/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/persistence/storage/test_namespace_registry.py` passed.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/auth/test_session_store_roundtrip.py src/aeat/adapters/outbound/aeat/auth/test_authenticator.py src/aeat/adapters/persistence/storage/test_namespace_registry.py` passed: 76 passed.
- `uv run --no-sync vaultspec-core vault plan step check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md W12.P26.S117` closed the step row.

## Notes

- AFR-015 is closed for the session-store runtime-default contract. The remaining W12.P26 rows are still open: browser factory/site-health and AEAT export/sede remote-provider surfaces must be handled in S118-S122.
