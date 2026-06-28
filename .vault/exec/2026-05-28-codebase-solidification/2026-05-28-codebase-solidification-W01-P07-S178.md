---
tags:
  - "#exec"
  - "#codebase-solidification"
step_id: S178
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S178 — real-behaviour tests for `BINARY_MIME_TYPE`

## Outcome

Extended `src/aeat/core/test_external_constants.py` with four tests:

- `test_binary_mime_type_value` — asserts `BINARY_MIME_TYPE == "application/octet-stream"`
- `test_google_drive_reads_binary_mime_from_external_constants` — imports the
  `_google_drive` module and asserts its `_BINARY_MIME_TYPE` attribute is the
  same object as `external_constants.BINARY_MIME_TYPE`
- `test_blob_store_put_default_content_type_reads_from_external_constants` —
  uses `inspect.signature` on `EncryptedBlobStore.put` to assert the
  `content_type` default equals `BINARY_MIME_TYPE`
- `test_declarations_filed_artefact_uses_binary_mime_constant` — imports
  `_declarations` module and asserts `_BINARY_MIME_TYPE` attribute is the
  canonical constant

## Test results

`32 passed` (all pre-existing + 4 new). Smoke runs:
- `src/aeat/adapters/persistence/storage/blob_store/` — 27 passed
- `src/aeat/adapters/outbound/storage/` — 31 passed

## Files changed

- **Extended**: `src/aeat/core/test_external_constants.py`

## Review gates (G1–G6)

All pass. Tests are real-behaviour (import + identity), no mocks, no skips,
no xfail, no tautological assertions.
