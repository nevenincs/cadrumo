---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:fe1e3969b623b311aae9adad92694593d16e45dcf82bdf42aec4646ff02d73df'
step_id: 'S100'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh name the profile-to-bucket identity conversion once in the identity package and route the twenty-eight bare string coercions through it, then settle whether the custody capsule records should carry the canonical profile identifier string or whether that identifier needs a documented object form, since three identifier shapes exist where the rules assume two and the bridge between them is currently an unnamed coercion the grounding rule already classes as a boundary leak

## Scope

- `src/cadrumo/core/identity/ and src/cadrumo/adapters/persistence/storage/custody/_capsule_records.py`

## Description

Centralize canonical profile-bucket conversion beside `ProfileId`, route custody serialization and keying sites through it, and preserve resolver-owned reverse comparisons.

## Outcome

`canonical_profile_bucket_id(profile_id: str | UUID) -> str` now lives in `core/identity/_profile.py` beside `ProfileId`, exported from the facade (commit `fd1b71807b`). It validates (parses plainly, then REFUSES non-v4 — the first draft used `UUID(..., version=4)`, which silently re-types the version nibble; the refusal test caught it before it shipped) and returns the canonical lowercase string, mirroring `canonical_bucket_id`'s plain-ValueError convention. The keying/serialization sites were routed through it: custody `_paths.py` repository-id derivation, `_sentinel_contract.py`, `_recovery.py`, `_acceleration_receipt.py` (payload, bucket keying, log context) and `_capsule_records.py` payload writes, plus the shared test door `tests/profile_capsule.py`. The capsule records keep their `UUID`-typed fields (strictest shape; pydantic serialises the canonical string, so on-disk bytes are identical — no persisted-format change, no version bump). The comparison/resolver-scoping sites (class c) were deliberately NOT routed: the bucket-id-to-profile reverse bridge stays a resolver judgment because `BucketId` is looser than `ProfileId`.

## Notes

Gates: ruff clean across `core/identity/` and the custody package; identity suite 117 passed (three new agreement/refusal tests for the conversion); `tests/test_secure_sql.py` 6 passed. Pre-existing reds untouched and noted: `test_path_identity_boundary.py` fails 10 cases at HEAD because the discoverer's private `_canonical_profile_id` re-types non-v4 bucket names via `UUID(..., version=4)` (same hazard this row's refusal test pins — candidate for a follow-up row), and the keychain-environment failures in the acceleration-receipt matrix. The row's 'twenty-eight' coercion figure was stale at HEAD (42 `str(profile_id)` + 33 `bucket_id=str(...)` + 20 `UUID(str(...))`); this row routed the keying class and classified the rest — the remaining bare casts are (b) no-op casts on already-canonical strings and (c) resolver scoping, documented rather than swept.
