---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S373'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S373 - Close AFR-271 for user profile values

Scope: close `AFR-271` for `src/aeat/domain/user_profile/_values.py` with signals
`active-profile, manifest-bucket`, target `manifest-discovery`, and owner
`W12.P22.S90`.

## Description

- Audited `src/aeat/domain/user_profile/_values.py` for secure storage, runtime
  settings, direct environment access, filesystem IO, and remote-provider IO.
- Confirmed the file is a strict Pydantic value-model surface for profile facts,
  profile records, snapshots, deterministic snapshot ids, and canonical hashes.
- Confirmed active-profile and manifest-bucket wording in `_values.py` documents the
  identity contract for `profile_id`; it does not implement active-profile pointer IO,
  manifest scanning, bucket provisioning, or encrypted persistence.
- Confirmed repository/runtime ownership remains in application-layer user-profile
  modules, especially `src/aeat/application/user_profile/_repository.py` and the
  profile lifecycle/orchestration surfaces.
- Ran focused real-behavior domain and application repository tests after the shared
  test-topology refactor; scoped import formatting required no retained source diff.
- Closed `W12.P26.S373` through `vaultspec-core vault plan step check` and updated
  the `AFR-271` register status to `closed`.

## Outcome

`AFR-271` is closed as `manifest-discovery`. No production code change was required:
`_values.py` remains a domain value-model and content-addressing boundary, while
active-profile pointer handling, plaintext manifest IO, bucket provisioning, and
secure-object persistence remain outside the domain value module.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/user_profile/_values.py src/aeat/domain/user_profile/tests/test_values.py src/aeat/domain/user_profile/tests/test_schema.py src/aeat/domain/user_profile/tests/test_registry_contract.py src/aeat/application/user_profile/_repository.py src/aeat/application/user_profile/tests/test_repository.py src/aeat/application/user_profile/tests/test_repository_roundtrip.py`
- `uv run --no-sync pytest -q src/aeat/domain/user_profile/tests/test_values.py src/aeat/domain/user_profile/tests/test_schema.py src/aeat/domain/user_profile/tests/test_registry_contract.py src/aeat/application/user_profile/tests/test_repository.py src/aeat/application/user_profile/tests/test_repository_roundtrip.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

`vaultspec-rag` was attempted for user-profile value/repository grounding, but the
service on port 8766 was unreachable and the CLI correctly refused in-process fallback
to avoid taking the shared Qdrant lock. The closure relies on direct source inspection
and focused real-behavior gates.

Mandatory review found one LOW, non-blocking follow-up: the opening documentation in
`src/aeat/application/user_profile/_profile_repository.py` overstates cross-store
ownership as "single, sole writer" because orchestration and health repair also write
specific profile stores. That wording does not affect the S373 disposition because
`_values.py` itself remains non-storage value-model code.
