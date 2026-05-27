---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
step_id: 'S02'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path
     (e.g., S03 at L1, P02.S03 at L2, W01.P02.S03 at L3 / L4). The
     step_id frontmatter field below carries the canonical identifier;
     the heading restates the display path as a reading hint. -->

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
