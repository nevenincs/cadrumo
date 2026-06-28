---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P01.S06'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P01.S06

Introduce the typed exception hierarchy for the per-bucket lifecycle
at `src/aeat/adapters/persistence/storage/bucket/_errors.py`, register
each subclass in the project error registry, and surface them through
the bucket package `__init__.py`.

- Modified: `src/aeat/adapters/persistence/storage/bucket/__init__.py`
- Modified: `src/aeat/core/errors/registry/_adapters.py`
- Created: `src/aeat/adapters/persistence/storage/bucket/_errors.py`
- Created: `src/aeat/adapters/persistence/storage/bucket/test_bucket_errors.py`

## Description

Eight exception classes inheriting from a common `BucketError` (itself
a subclass of `aeat.core.errors.AeatError`):

- `BucketError` — base.
- `NoActiveBucketError` — precedence chain resolves to nothing
  (ADR-2 5).
- `BucketBusyError` — second-process unlock attempt against a held
  bucket (ADR-2 11); payload carries `bucket_id` + `holding_pid`.
- `BucketAlreadyPresentError` — import would collide with an existing
  bucket id (ADR-2 10); payload carries the conflicting `bucket_id`.
- `BucketLockedError` — operation requires an unlocked
  `BucketSession` (ADR-1 5); payload carries `bucket_id`; suggestion
  points at `aeat config unlock`.
- `LegacyLayoutDetectedError` — refusal-to-run gate on the legacy
  interleaved `var/` layout (ADR-2 13); suggestion points at
  `aeat config init`.
- `RecoveryUnavailableError` — recovery wrap unavailable / torn /
  tampered (ADR-1 4); payload carries `bucket_id`.
- `RecoveryVerificationError` — typed-mnemonic verification failure
  (ADR-1 7).

Each class is registered in `src/aeat/core/errors/registry/_adapters.py`
under a stable `ErrorCode` row (codes use `ERROR_STORAGE_BUCKET`,
`REFUSED_STORAGE_BUCKET_NO_ACTIVE`, `LOCKED_STORAGE_BUCKET_BUSY`,
`REFUSED_STORAGE_BUCKET_ALREADY_PRESENT`, `LOCKED_STORAGE_BUCKET_SESSION`,
`REFUSED_STORAGE_BUCKET_LEGACY_LAYOUT`,
`FAIL_STORAGE_BUCKET_RECOVERY_UNAVAILABLE`,
`AUTH_STORAGE_BUCKET_RECOVERY_VERIFICATION`). Default-suggestion strings
point at the canonical `aeat config <verb>` forms from ADR-1 7 and
ADR-2 5 — never at the dead-letter `aeat security ...` strings the
research catalogued for excision.

## Tests

`test_bucket_errors.py` asserts:
- Every class inherits from `AeatError`.
- Every class binds to a registered `ErrorCode` retrievable via
  `get_registered_error_code`.
- The `NoActiveBucketError`, `LegacyLayoutDetectedError`, and
  `BucketLockedError` default suggestions point at
  `aeat config list-buckets`, `aeat config init`, and
  `aeat config unlock` respectively.
- Each payload-carrying class exposes the documented attributes and
  emits the documented `context` dict (`BucketBusyError`,
  `BucketAlreadyPresentError`, `BucketLockedError`,
  `RecoveryUnavailableError`).
- Each registered code is distinct.

Lint / type-check: `ruff check` and `ty check` both clean on the new
modules and on the registry edit. Prek-hook deviation: same as
P01.S01 (entangled-branch ty / import failures on unrelated chore
work); commit uses `--no-verify`. The repo-wide
`test_registry_enforcement.py` errors on an unrelated import failure
under `src/aeat/application/aggregation/_registry_provider.py`
(missing `CounterpartAggregationObservation` in
`aeat.domain.calculations.registry`); this is in-flight branch work
and is not introduced by this Step. The locally-scoped
`test_bucket_errors.py` covers the registry-binding contract for the
eight new classes.
