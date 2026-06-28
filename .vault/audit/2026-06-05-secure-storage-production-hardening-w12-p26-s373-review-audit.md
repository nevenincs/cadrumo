---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S373]]'
---

# `secure-storage-production-hardening` `W12.P26.S373` Review

## S373-001 | PASS | User-profile values do not own storage

`src/aeat/domain/user_profile/_values.py` defines strict profile fact, record, and
snapshot value models plus canonical id/hash helpers. It does not create secure-object
repositories, load settings, inspect active bucket runtime, read environment variables,
open files, scan manifests, provision buckets, or call remote providers.

## S373-002 | PASS | Active-profile and manifest-bucket signals are identity semantics

The active-profile and manifest-bucket terms in `_values.py` are descriptive identity
contract text around the immutable `profile_id`: profile identity keys bucket
directories, keystore directories, secure-object keys, and active-profile pointers.
That description does not make the value module a runtime storage owner.

## S373-003 | PASS | Runtime ownership remains outside the domain value module

Application-layer user-profile repositories and orchestration own the storage boundary:
bucket runtime resolution through centralized settings, `SecureObjectRepository`
binding, plaintext manifest IO, profile bucket lifecycle, and active-profile pointer
operations. S373 therefore closes `_values.py` as `manifest-discovery`, not
`runtime-default`.

## S373-004 | PASS | Focused tests remain real-behavior checks

The domain value tests exercise validation and canonical hash behavior directly, while
the application repository tests use real secure SQL runtime fixtures and real
repository roundtrips. The S373 verification surface does not depend on fakes, stubs,
monkeypatches, skipped tests, or tautological assertions.

## S373-005 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/domain/user_profile/_values.py src/aeat/domain/user_profile/tests/test_values.py src/aeat/domain/user_profile/tests/test_schema.py src/aeat/domain/user_profile/tests/test_registry_contract.py src/aeat/application/user_profile/_repository.py src/aeat/application/user_profile/tests/test_repository.py src/aeat/application/user_profile/tests/test_repository_roundtrip.py` passed.
- `uv run --no-sync pytest -q src/aeat/domain/user_profile/tests/test_values.py src/aeat/domain/user_profile/tests/test_schema.py src/aeat/domain/user_profile/tests/test_registry_contract.py src/aeat/application/user_profile/tests/test_repository.py src/aeat/application/user_profile/tests/test_repository_roundtrip.py` passed with 35 tests.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-rag search "UserProfileRecord UserProfileSnapshot profile_id manifest bucket secure object repository runtime settings" --type code --port 8766 --max-results 8` reported the MCP service on port 8766 as unreachable and did not fall back in-process.

## S373-006 | LOW | Profile repository ownership prose is broader than implementation

Mandatory review noted that `src/aeat/application/user_profile/_profile_repository.py`
opens with "single, sole writer" wording, while orchestration and health repair also
write specific profile stores. This does not block S373 because `_values.py` is still a
non-storage value module, but the wording should be narrowed in a future
profile-repository documentation cleanup.

Reviewer note: no critical, high, or medium manifest-discovery findings remain for the
S373 slice.

Disposition: close `AFR-271` as `manifest-discovery`.
