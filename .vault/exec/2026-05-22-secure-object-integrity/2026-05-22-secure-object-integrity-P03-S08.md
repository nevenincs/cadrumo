---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
step_id: 'S08'
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

# `secure-object-integrity` `P03.S08`

Added primary SQL storage route classification.

- Modified: `src/aeat/core/config.py`
- Created: `src/aeat/core/test_storage_route_classification.py`

## Description

Added strict route classification for the effective primary SQL database URL. The classifier distinguishes explicit database URLs from active-bucket SQLite databases and root fallback SQLite databases, preserving bucket id metadata when the URL routes through the active-profile bucket layout.

The classifier is pure core logic and does not yet enforce command refusal. P03.S09 owns routing profile-bound write commands through the root-fallback refusal guard.

Review remediation removed pytest `monkeypatch` from the focused tests and added explicit URL cases that point inside active-bucket and root-fallback path shapes while still classifying as explicit routes.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/core/config.py src/aeat/core/test_storage_route_classification.py`
- `uv run pytest src/aeat/core/test_storage_route_classification.py`

The focused test run passed 6 tests.
