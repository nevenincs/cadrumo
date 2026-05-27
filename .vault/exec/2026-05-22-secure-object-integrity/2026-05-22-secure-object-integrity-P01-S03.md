---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
step_id: 'S03'
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

# `secure-object-integrity` `P01.S03`

Exposed unreadable-row attribution through the config repair integrity CLI surface.

- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py`

## Description

Added `aeat config repair integrity attribution` as a read-only sibling to the existing `objects` and `registry` integrity subverbs. The command resolves the active profile bucket, emits an explicit no-active-profile metadata-only report on a cold root, and otherwise renders the grouped attribution report from the application layer in both text and JSON formats.

The text renderer prints namespace summaries, classification counts, and row metadata already validated by the strict attribution models. It does not add payload decryption or mutation paths.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py`
- `uv run pytest src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/application/test_repair_integrity.py`

The focused test run passed 34 tests, including the new bootstrap-exempt coverage for `config repair integrity attribution`.
