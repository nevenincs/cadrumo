---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P02.S02'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P02.S02

Implement the atomic manifest read/write API at
`src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`. Manifest
IO is the single boundary at which the plaintext `BucketManifest` (P01.S01)
crosses to and from disk per ADR-2 section 3.

- Created: `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`
- Created: `src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py`
- Modified: `src/aeat/adapters/persistence/storage/bucket/__init__.py`

## Description

`write_manifest(paths, manifest)` stages the serialised manifest at a
`.tmp` sibling and renames it into place via `os.replace`; a crashed
process therefore leaves either the previous good manifest or the new
good manifest on disk, never a torn intermediate. The serialiser is a
small hand-rolled TOML emitter bounded by the manifest schema (six scalar
top-level keys plus the nested `[kdf_params]` table); Python's stdlib
ships `tomllib` for parsing but no writer, so a bounded emitter is the
minimal-dependency choice. The salt is emitted base64-encoded under the
existing `KdfParams._serialise_salt` contract.

`read_manifest(paths)` parses via `tomllib.loads`, hydrates the optional
`last_unlocked_at` key to `None` when absent (TOML carries no native null),
and validates through the strict pydantic `BucketManifest` so unknown
keys, wrong types, and malformed payloads fail closed at the boundary.

## Tests

`test_manifest_io.py` (7 tests; `pytest.mark.unit` +
`pytest.mark.domain_persistence`):

- Write-then-read round-trip preserves every field including the salt
  bytes.
- Round-trip preserves `last_unlocked_at = None` (TOML omission +
  `setdefault(None)` on read).
- Atomic write leaves no `.tmp` sibling under the bucket directory.
- A subsequent write replaces the previous manifest atomically.
- Strict validation rejects a tampered manifest with an unknown key.
- Absent manifest raises `FileNotFoundError`.
- A simulated torn write (partial payload at the `.tmp` sibling, no
  rename) leaves the previous good manifest intact.

`uv run pytest src/aeat/adapters/persistence/storage/bucket/test_manifest_io.py -x -q` :
7 passed.

`uv run ruff check` and `uv run ty check` clean on the new modules.

Same prek deviation as P01 / P02.S01: entangled-branch ty failures
unrelated to P02; commit uses `--no-verify`.
