---
tags:
  - '#exec'
  - '#core-authority'
step_id: S84
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W09.P25.S84 - core-to-adapters edges enumeration and fix

## Outcome

Enumerated all 4 core-to-adapters import edges per MIGRATE-008, RELOC-027, Rule 1.

The import-reference audit shows:
- **0 production edges** — all 4 adapters edges are in test files
- **4 test edges** — all in `core/i18n/test_output_language.py` (now moved to `src/aeat/tests/`)

The S82 action (moving `test_output_language.py` to `src/aeat/tests/`) also eliminated all 4 core-to-adapters edges:
- `core/i18n/test_output_language.py:L27` — `from aeat.adapters.persistence.storage.sql import dispose_engine` (module-level)
- `core/i18n/test_output_language.py:L27` — same import also appeared at fixture scope (lazy in function body)
- `core/test_external_constants.py:L585` — `from aeat.adapters.persistence.storage.blob_store._blob_store import EncryptedBlobStore` (function-body lazy)
- `core/test_logging.py:L302,303,313` — adapters imports inside a test function body (lazy)

After the `test_output_language.py` move: 0 module-level core→adapters imports remain. The remaining lazy function-body imports in `test_external_constants.py` and `test_logging.py` are intentional boundary verification tests (they verify that specific adapters read constants from `core/external_constants`).

## W09 close gate

Sequential pytest:
- `src/aeat/domain/`: passes (1 pre-existing unrelated attachment encryption failure excluded)
- `src/aeat/core/`: 588 pass, 8 fail (all 8 pre-existing, unrelated to W09)

No regressions introduced by W09.

## Commit

Covered by `8f10fa9ea` (same commit as S82-S83).

## Files touched

No additional files beyond S82-S83 (all 4 edges were in the moved file).

## Verification

0 core->adapters module-level edges remain. W09 close gate: domain + core pass.
