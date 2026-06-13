---
tags:
  - '#exec'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'P02.S04'
related:
  - '[[2026-05-14-secure-backend-passkey-bucket-plan]]'
---

# secure-backend-passkey-safety P02.S04

Implement the active-bucket pointer-file IO at
`src/aeat/application/workflow/_bucket_pointer_io.py`. Reads return
`None` when the pointer is absent; writes are atomic via
write-then-rename per ADR-2 sections 5 and 6.

- Created: `src/aeat/application/workflow/_bucket_pointer_io.py`
- Created: `src/aeat/application/workflow/test_bucket_pointer_io.py`

## Description

`pointer_path(root)` returns the canonical `<aeat-root>/active-bucket`
path. `read_pointer(root)` returns `None` when the pointer file is
absent (the precedence-chain resolver in P04 handles the missing case);
otherwise it parses the file as single-document TOML through the
strict-validated `BucketPointer.from_toml` (P01.S04) so unknown keys
and malformed payloads fail closed at the boundary.

`write_pointer(root, pointer)` stages the rendered TOML at a `.tmp`
sibling and renames into place via `os.replace`; a crash mid-write leaves
either the previous good pointer or the new good pointer, never a torn
intermediate. The root directory is created lazily.

## Open-question default honoured

Pointer-file representation: single-document TOML keyed by `bucket_id`
and `schema_version` (per the orchestrator default and the
`BucketPointer.to_toml` / `from_toml` serialisation committed in P01.S04).

## Tests

`test_bucket_pointer_io.py` (7 tests; `pytest.mark.unit` +
`pytest.mark.domain_application`, matching P01.S04's marker choice):

- Round-trip preserves the pointer.
- Absent pointer reads as `None`.
- Atomic write leaves no `.tmp` sibling.
- Overwrite replaces the previous pointer atomically.
- Simulated torn write (`.tmp` carrying partial payload, no rename)
  leaves the previous good pointer intact.
- Strict validation rejects an unknown key in the pointer file.
- Write creates parent directories lazily.

`uv run pytest src/aeat/application/workflow/test_bucket_pointer_io.py -x -q` :
7 passed.

`uv run ruff check` and `uv run ty check` clean on the new modules.
