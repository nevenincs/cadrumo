---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
step_id: 'S06'
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

# `secure-object-integrity` `P02.S06`

Classified every hygiene violation surfaced by the ephemeral-key guard.

- Modified: `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`

## Description

Converted the guard's pending file list into an explicit path-to-classification inventory. Every current file-level hygiene exception is classified as requiring explicit repository injection or an autouse temporary database fixture. The guard still fails on any new unclassified file, and an additional test proves every pending classification is allowed and points to an existing source file.

This step classifies the backlog without broad repairs across unrelated feature surfaces. Follow-on work can burn down the inventory by converting individual files to explicit repository injection or shared isolation helpers.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
- `uv run pytest src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`

The focused guard run passed 2 tests.
