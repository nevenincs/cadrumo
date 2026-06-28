---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P01.S01'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P01.S01

Introduce the `BucketManifest` pydantic v2 strict model carrying the
non-sensitive metadata for one per-bucket directory under
`<aeat-root>/buckets/<bucket-id>/`.

- Created: `src/aeat/adapters/persistence/storage/bucket/__init__.py`
- Created: `src/aeat/adapters/persistence/storage/bucket/_manifest.py`
- Created: `src/aeat/adapters/persistence/storage/bucket/test_manifest.py`

## Description

`BucketManifest` is a frozen, strict, `extra="forbid"` pydantic v2 model.
Fields match ADR-2 section 3: `bucket_id`, `label`, `created_at`,
`last_unlocked_at`, `kdf_params`, `recovery_enrolled`, `schema_version`.
The nested `KdfParams` record carried by the manifest is intentionally
minimal at this Step (records the algorithm identifier, parameter
version, salt bytes, and the four cost parameters); the canonical
OWASP-pinned constructor lands in P01.S02 under
`master_key/_kdf_params.py`. P02 wires the two surfaces together
when manifest I/O ships; this Step ships the on-disk shape only.

Validators enforce: non-empty `bucket_id`, UTC-aware datetimes
(rejects naive timestamps and non-UTC offsets), strict-positive
`schema_version`, 16-byte `salt`. The model serialises through
`model_dump_json` / `model_validate_json` with base64-encoded `salt`
bytes; the test asserts byte equality on the salt round-trip.

## Tests

`test_manifest.py` asserts:
- strict-validation rejects unknown keys (`extra="forbid"`),
- missing `bucket_id` raises,
- naive (non-UTC) `created_at` is rejected,
- a non-positive `schema_version` is rejected,
- a `salt` of length other than 16 is rejected,
- JSON round-trip preserves byte equality of `salt`.

Lint / type-check: ruff + ty clean on the new modules
(`uv run ruff check src/aeat/adapters/persistence/storage/bucket/` and
`uv run ty check src/aeat/adapters/persistence/storage/bucket/` both
report `All checks passed!`).

Prek-hook deviation: the repo-wide prek `ty` hook fails on
unrelated in-flight work under `src/aeat/entrypoints/cli/_modelo.py`
and other chore-branch modules (218 ty diagnostics, none of them
in files this Step touches). Per the orchestrator brief's prek
escape clause ("`--no-verify` is forbidden unless prek fails for
an unrelated entangled-branch reason; record the decision in the
exec record"), the commit uses `--no-verify`. The new bucket
modules pass ruff and ty in isolation.
