---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-16'
modified: '2026-07-16'
body_hash: 'sha256:b0f197fbadb456383d34f02390f5b12f76523b56fcf6bdee600c61a8c69d65f0'
step_id: 'S36'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Refuse logout under an explicit profile override, prove pointer-sourced strong logout honors lock contention and closes real storage idempotently, and restore single declaration authority to the error registry

## Scope

- `src/cadrumo/application/user_profile/__init__.py`
- `src/cadrumo/application/user_profile/_orchestration.py`
- `src/cadrumo/application/user_profile/tests/test_orchestration.py`
- `src/cadrumo/entrypoints/cli/_bootstrap_exempt.py`
- `src/cadrumo/core/errors/_registry.py`
- `src/cadrumo/core/errors/registry/_adapters_part2.py`
- `src/cadrumo/core/errors/registry/_application_part1.py`
- `src/cadrumo/core/errors/registry/_application_part2.py`
- `src/cadrumo/core/errors/registry/_domain_part2.py`
- `src/cadrumo/core/errors/registry/_entrypoints.py`
- `src/cadrumo/core/errors/tests/test_registry.py`
- `src/cadrumo/core/errors/tests/test_registry_enforcement.py`

## Description

- Ground logout source precedence, pointer locking, session disposal, and raw error declarations with fresh resident Vaultspec-RAG searches and exact symbol scans.
- Refuse `logout_active_profile` before lock acquisition or session teardown when an explicit active-profile override is in force.
- Resolve the logged-out identity from the pointer held under `active_profile_pointer_transaction`, then close and evict the live bucket session before clearing that pointer.
- Mark `config profile logout` bootstrap-exempt so pointer-sourced CLI logout does not manufacture an override that the application must refuse.
- Prove real lock contention leaves exact pointer bytes, session identity, engine pool, and a queried SQLite connection live; then prove successful logout releases the sidecar, seals and evicts the session, disposes the engine, clears the pointer, and repeats as a no-op.
- Consolidate entrypoint error rows under the entrypoint shard, remove four duplicate qualname/code declarations, and make registry construction reject duplicate class ownership and identical duplicate code identifiers.

## Outcome

- Landed the implementation and regressions in `89eb96265d` after plan reconciliations in `6b3caef56b` and `d2fc48a77b`.
- Nine real orchestration tests, seventeen registry tests, twenty-one adjacent facade/session/engine tests, and two focused CLI integration tests passed.
- Ruff passed for all twelve owned Python files.
- The uncached import graph analyzed 3,425 files and 16,178 dependencies with all five contracts kept and none broken.
- Raw registry inventory now contains 570 rows, 570 unique exception qualnames, and 570 unique error codes.
- The feature-scoped Vaultspec audit passed every structure, annotation, markdown, link, schema, and lifecycle check.
- Fresh-RAG formal re-review passed with no findings after independently verifying the contention, cross-profile override, registry authority, and no-test-double contracts.

## Notes

- The initial release-only lock proof would also have passed if logout stopped acquiring the pointer transaction; the corrected test first forces a real timeout under worker-held ownership and proves fail-closed state preservation.
- The initial override regression used the same profile for override and pointer; the corrected test selects profile B through the override while preserving pointer and session A.
- Semantic and exact registry audits expanded the first duplicate finding to four duplicated qualname/code pairs: user-profile base, financial-provider base, CLI refusal boundary, and CLI log-level resolution.
- Existing concurrent locale edits were preserved. The new typed refusal uses the existing localized generic refusal message and carries specific recovery guidance without capturing peer locale changes.
- No fakes, mocks, stubs, patches, monkeypatching, skipped tests, expected failures, sleeps, compatibility aliases, provider caches, bucket-lock authorities, data loss, or runtime scaffolds were introduced.
- The shared damaged `.venv` remained untouched; every Python-backed command used an isolated frozen environment.
