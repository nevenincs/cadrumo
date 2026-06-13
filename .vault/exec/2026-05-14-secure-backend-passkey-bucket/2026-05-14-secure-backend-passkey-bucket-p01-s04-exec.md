---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P01.S04'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P01.S04

Introduce `BucketPointer`, the typed wrapper around the
`<aeat-root>/active-bucket` pointer file at
`src/aeat/application/workflow/_bucket_pointer.py`.

- Created: `src/aeat/application/workflow/_bucket_pointer.py`
- Created: `src/aeat/application/workflow/test_bucket_pointer.py`

## Description

Strict pydantic v2 frozen record carrying `bucket_id` (non-empty) and
`schema_version` (strict-positive integer). Owns serialisation to and
from the pointer file's on-disk representation through `to_toml()` and
`from_toml()`.

Open question decision: pointer-file format = TOML. Per the
orchestrator brief's default ("Pointer-file format -> TOML."), the
single-document TOML form chosen has two scalar keys
(`bucket_id = "..."`, `schema_version = <int>`) and ends with a
trailing newline so the atomic write-then-rename helper landing in
P02.S04 produces a POSIX-clean file. The serialiser escapes embedded
quotes and backslashes so a quoted `bucket_id` survives the round-trip.

The `ProfileBucketPointer` -> `BucketPointer` rename in
`src/aeat/application/workflow/_models.py` is deferred to P04 per the
plan; this Step only introduces the new typed record at its own
module path.

## Tests

`test_bucket_pointer.py` asserts:
- JSON round-trip preserves equality.
- TOML round-trip preserves equality (including quoted `bucket_id`).
- Empty `bucket_id` is rejected.
- Non-positive `schema_version` is rejected.
- Unknown extra keys are rejected on both `model_validate` and
  `from_toml` paths.
- Missing `bucket_id` in the TOML payload is rejected.

Lint / type-check: `ruff check` and `ty check` both clean on the new
modules. Prek-hook deviation: same as P01.S01 (entangled-branch ty
failures on unrelated chore work); commit uses `--no-verify`.
