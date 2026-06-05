---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
step_id: 'S373'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S373 - Close AFR-271 for user-profile values

Scope: close `AFR-271` for `src/aeat/domain/user_profile/_values.py` with signals
`active-profile, manifest-bucket`, target `manifest-discovery`, and owner `W12.P22.S90`.

## Description

- Audited `_values.py` for direct manifest discovery, active-profile pointer access,
  storage runtime inspection, settings/environment reads, filesystem IO, SQL access,
  secure-object construction, and plaintext persistence.
- Confirmed `_values.py` is a strict immutable value-model module for profile facts,
  live profile roots, snapshots, lifecycle state, UUID minting, and canonical snapshot
  hashes.
- Confirmed persistence ownership remains in the application user-profile repositories
  and storage runtime tests, not in `_values.py`.
- Repaired local import-depth regressions in `test_profile_repository.py` that blocked
  the focused profile repository verification suite.
- Closed `W12.P26.S373` through `vaultspec-core vault plan step check` and updated
  the `AFR-271` register status to `closed`.

## Outcome

`AFR-271` is closed. The scanner signals are model vocabulary: active/tombstoned
profile lifecycle and bucket-qualified persistence semantics documented in value
records. `_values.py` does not perform manifest discovery, active-profile resolution,
or storage IO.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/user_profile/_values.py src/aeat/domain/user_profile/tests/test_values.py src/aeat/application/user_profile/tests/test_repository_roundtrip.py src/aeat/application/user_profile/tests/test_repository_anti_tautology.py src/aeat/application/user_profile/tests/test_profile_repository.py src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories.py`
- `uv run --no-sync pytest -q src/aeat/domain/user_profile/tests/test_values.py src/aeat/application/user_profile/tests/test_repository_roundtrip.py src/aeat/application/user_profile/tests/test_repository_anti_tautology.py src/aeat/application/user_profile/tests/test_profile_repository.py`
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories.py -k "application_repository_defaults_isolate_active_profile_writes or runtime_default_surfaces"`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

During verification, several shared-worktree test imports briefly pointed at parent
packages instead of their production modules. The remaining committed fix is limited to
`test_profile_repository.py`, where local imports still blocked the suite.
