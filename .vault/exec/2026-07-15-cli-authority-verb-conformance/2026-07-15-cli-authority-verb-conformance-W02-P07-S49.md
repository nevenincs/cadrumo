---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:7939cdabc92db29a64778eedd307db6e6a48b9707f85eee305729b02ae21e8f7'
step_id: 'S49'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Route auth status, test, login, central session acquisition, live callers, state projection, and modelo provider construction through the active certificate credential resolver by centralizing exact certificate credential projection in the application provider factory and transporting explicit absent values without changing omitted-provider reporting semantics

## Scope

- `src/cadrumo/adapters/persistence/storage/blob_store/_materialisation.py`
- `src/cadrumo/adapters/persistence/storage/blob_store/tests/test_materialisation.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_bucket_session.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_recovery_facade.py`
- `src/cadrumo/adapters/persistence/storage/master_key/tests/test_bucket_session.py`
- `src/cadrumo/tests/secure_sql.py`
- `src/cadrumo/application/auth/__init__.py`
- `src/cadrumo/application/auth/_certificate_secret_backend.py`
- `src/cadrumo/application/auth/_certificate_sources.py`
- `src/cadrumo/application/auth/_certificate_sources_operator.py`
- `src/cadrumo/application/auth/_operator.py`
- `src/cadrumo/application/auth/_operator_scope.py`
- `src/cadrumo/application/auth/_sessions.py`
- `src/cadrumo/application/auth/tests/test_certificate_secret_backend.py`
- `src/cadrumo/application/auth/tests/test_certificate_sources_check.py`
- `src/cadrumo/application/auth/tests/test_operator.py`
- `src/cadrumo/application/state_projection.py`
- `src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py`

## Description

- Ground the certificate and storage routing surface with Vaultspec RAG searches, then confirm every exact caller and construction site with `rg`.
- Centralize certificate provider construction behind one application projection that carries path, password, and friendly name exactly, including explicit absent values.
- Route status, test, login, preflight, central session acquisition, state projection, and modelo workflow construction through the same projected provider settings.
- Preserve omitted-provider reporting: status and test do not invent a provider when workflow state has none.
- Resolve selected named-source secrets only from the selected profile's secure store and fail closed instead of inheriting a global password.
- Make the secret-store factory route-aware across both secret and blob roots, retaining the explicit test override boundary.
- Record storage-root provenance on bucket sessions and require bucket identity plus root identity before reusing an active session.
- Open explicit-settings operator spans before applying their settings scope so a same-UUID bucket in another root cannot inherit ambient key material.
- Synchronize the workflow compatibility path when an active certificate source is re-registered.
- Add real PKCS#12, encrypted-storage, two-bucket, two-root, same-UUID, route-cache, status/test, and session-restoration regressions without mocks, fakes, patches, skips, or mirrored business logic.

## Outcome

- One certificate credential resolver and one application provider-construction choke point now feed every in-scope consumer.
- Named certificate sources cannot fall back to unrelated global credentials, and legacy single-certificate settings remain valid only when no named source is selected.
- Explicit settings select their own workflow state, secret store, blob store, certificate, and bucket key session across different buckets and different storage roots.
- Active session reuse is rejected when only the bucket UUID matches; storage-root provenance must match as well.
- Route-aware stores no longer inherit the first process route, including routes that share a secret directory but differ in blob directory.
- Focused and regression verification passed: certificate and secret backend 48 tests; auth operator/session 44 tests; state projection 20 tests; materialisation 14 tests; bucket-session and recovery 29 tests; master-key fallback/adverse/idle 34 tests; modelo workflow gate 11 tests.
- Ruff passed on every changed Python path. Import Linter analysed 3,435 files and 16,298 dependencies with all five contracts kept and zero broken.

## Notes

- RAG and swarm review found two isolation defects beyond the initial certificate projection: first-call secret-store route capture, and same-UUID active-session reuse across storage roots. Both are covered by real-behaviour regressions.
- One pre-existing preflight fixture constructed a new settings object whose environment-derived storage root differed from the active test root. The fixture now updates the active settings object, making its intended route explicit.
- Final commit waits for the concurrent bucket-lock owner to land overlapping work in the master-key provider file; S49 must not absorb that peer-owned diff.
