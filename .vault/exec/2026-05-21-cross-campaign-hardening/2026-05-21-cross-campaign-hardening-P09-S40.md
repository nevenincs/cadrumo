---
tags: ["#exec", "#cross-campaign-hardening"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'P09.S40'
related:
  - '[[2026-05-21-cross-campaign-hardening-plan]]'
  - '[[2026-05-21-cross-campaign-hardening-audit]]'
  - '[[2026-05-21-state-architecture-plan]]'
  - '[[2026-05-21-state-architecture-w01-audit]]'
---

# `cross-campaign-hardening` `P09.S40`

Closed GEN-4 task 518 as delegated tracking.

- Verified: `.vault/plan/2026-05-21-state-architecture-plan.md`
- Verified: `.vault/audit/2026-05-21-state-architecture-w01-audit.md`
- Verified: `src/aeat/application/setup/test_atomic_create_roundtrip.py`
- Verified: `src/aeat/application/user_profile/test_repository_roundtrip.py`
- Verified: `src/aeat/application/user_profile/test_profile_repository.py`
- Verified: `src/aeat/application/user_profile/test_lifecycle.py`

## Description

The cross-campaign audit explicitly delegated task 518 to
`cli-workflow-redesign` and instructed this rollout not to
double-implement it. Verified that the delegated state-architecture
plan has completed Wave W01 for UUID identity and records the intended
model: immutable UUID profile identity, decoupled mutable label, UUID
bucket/keystore/pointer keys, and label-only rename.

Reran focused tests that prove the delegated behavior: full profile
create/list/show/switch/show identity roundtrip, encrypted
`profile_id` / `display_name` persistence separation, manifest UUID
drift detection, and label-only rename.

No local production code change was made for this tracking row.

## Tests

`uv run ruff check src/aeat/application/setup/test_atomic_create_roundtrip.py src/aeat/application/user_profile/test_repository_roundtrip.py src/aeat/application/user_profile/test_profile_repository.py src/aeat/application/user_profile/test_lifecycle.py` passed.

`uv run pytest src/aeat/application/setup/test_atomic_create_roundtrip.py::test_atomic_create_roundtrip_identity_is_consistent_across_verbs src/aeat/application/user_profile/test_repository_roundtrip.py::test_user_profile_value_and_snapshot_survive_encrypted_storage_roundtrip src/aeat/application/user_profile/test_profile_repository.py::test_load_surfaces_manifest_uuid_drift src/aeat/application/user_profile/test_lifecycle.py::test_rename_updates_label_only -q` passed with 4 tests in 3.50s.

`uv run vaultspec-core vault plan step check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md S40` closed the row.

`uv run vaultspec-core vault plan check .vault/plan/2026-05-21-cross-campaign-hardening-plan.md` passed.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`, `en.yml`, `es.yml`, and `hu.yml`.

`git diff --check -- .vault/plan/2026-05-21-cross-campaign-hardening-plan.md .vault/exec/2026-05-21-cross-campaign-hardening/2026-05-21-cross-campaign-hardening-P09-S40.md` passed.
