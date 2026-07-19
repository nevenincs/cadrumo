---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-19'
modified: '2026-07-19'
step_id: 'S09'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# DEFERRED pending (a) protected-browser S08 closure and (b) resolution of the namespace-authority-split adjudication in P03.S27: remove duplicate namespace and custody declarations from Clave, LLM cache and usage, bundle, attachment, and secure-storage consumers without conflating certificate custody with master-key keyring custody. The auth zone is the S08 quiescence surface and in active auth-cert churn, so editing clave and certificate lifecycle now risks colliding with or reopening behavioral work

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/`

## Description

This step's two blockers were already cleared at HEAD before this record was written: `P03.S08` (protected-browser closure) and `P03.S27` (namespace-authority adjudication) both carry `[x]` in the plan. Verified, did not re-implement, that the dedup itself already landed:

- Confirmed `_clave_movil_page_flow.py` sources its diagnostic namespace, sensitivity, and schema version from `CLAVE_MOVIL_DIAGNOSTICS_NAMESPACE` (the registry definition), not a raw literal — commit `57d2039f6a` (`relocation:clave-diagnostics-namespace`).
- Confirmed `_clave_permanente_support.py` carries no duplicated namespace literal.
- Confirmed `adapters/outbound/llm/_cache.py` and `_usage.py` derive `_CACHE_NAMESPACE`/`_USAGE_NAMESPACE`, schema version, and sensitivity from `LLM_CACHE_NAMESPACE`/`LLM_USAGE_NAMESPACE` in the storage registry.
- Confirmed `application/evidence/_service.py` derives its namespace/sensitivity/schema-version `ClassVar`s from `APPLICATION_EVIDENCE_BUNDLE_NAMESPACE`.
- Confirmed `adapters/persistence/storage/attachment.py` derives its blob and manifest namespaces from `ATTACHMENT_BLOB_NAMESPACE`/`ATTACHMENT_MANIFEST_NAMESPACE`.
- No consumer in the auth zone or these secure-storage consumers redeclares a raw namespace/sensitivity/schema-version literal duplicating the registry.

## Outcome

Verified complete, zero production-code changes needed. `src/cadrumo/application/tests/test_storage_namespace_adoption.py` and `src/cadrumo/adapters/outbound/aeat/auth/tests` (164 tests) pass: `uv run --no-sync pytest src/cadrumo/application/tests/test_storage_namespace_adoption.py src/cadrumo/adapters/outbound/aeat/auth/tests -q` → `164 passed`.

## Notes

Bookkeeping-only closure: this record documents verification against HEAD `8af409cd3f`, not new implementation. The step's own DEFERRED text is now stale (both cited blockers resolved) but is left verbatim per the no-hand-edit-frontmatter/step-text discipline; the plan checkbox is the source of truth for closure.
