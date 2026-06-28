---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S231]]'
---

# `secure-storage-production-hardening` `W12.P26.S231` Review

## S231-001 | PASS | Verify observations are encrypted remote mirrors

`VerifyObservationRepository` persists AEAT live verify observations through
`LIVE_VERIFY_OBSERVATION_NAMESPACE`, typed `Envelope` payloads, and
`secure_object_repository_for_bucket()`. The reviewed module does not own a
plaintext JSONL writer, direct SQL route, naked environment access, or an
AEAT-side mutation verb.

## S231-002 | PASS | Lookup and integrity refusals are localized and bounded

Blank object-key inputs, lookup misses, ambiguous prefixes, bucket mismatch,
and observation-id mismatch paths now carry application-live verify locale
keys. Lookup refusals record only the requested id or match count, not the
active bucket id or matched full observation ids.

## S231-003 | PASS | List-time bucket contamination fails closed

`VerifyObservationRepository.list_observations()` previously decrypted every
row in the namespace and silently filtered rows whose embedded bucket id did
not match the repository bucket. The reviewed implementation now raises
`LiveApplicationInputError` with bounded context when a misrouted payload is
encountered.

## S231-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/live/_verify.py src/aeat/application/live/test_verify.py` passed.
- `uv run --no-sync pytest -q src/aeat/application/live/test_verify.py` passed with 18 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "verify or s85_runtime"` passed with 1 selected runtime-migration test.
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit` passed.
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` returned only the existing `PLAN022` warning.

Reviewer note: verify locale leaves were scaffolded and set through
`python -m aeat.locales`; no catalogue leaf was hand-authored.

Disposition: close `AFR-129` as `remote-mirror`.
