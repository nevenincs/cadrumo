---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S02'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P01.S02`

Added read-only grouping for unreadable secure-object attribution.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`

## Description

Added `build_repair_integrity_attribution_report`, which walks raw secure-object rows, attempts decryption only to determine unreadability, and groups unreadable rows by namespace. Namespace attribution now includes classification count groups, singleton/multirow owner semantics, and timestamp ranges derived from the unreadable rows.

The grouping preserves the metadata-only boundary from P01.S01. It records HMAC digests, storage metadata, redacted key context, and conservative origin placeholders, but does not decrypt or serialize payloads or private natural keys.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py`
- `uv run pytest src/aeat/application/test_repair_integrity.py`

The focused test file passed 21 tests, including real SQLite/key-provider coverage for grouped unreadable-row attribution.
