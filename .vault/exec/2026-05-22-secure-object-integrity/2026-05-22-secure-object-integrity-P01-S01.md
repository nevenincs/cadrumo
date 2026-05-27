---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
step_id: 'S01'
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

# `secure-object-integrity` `P01.S01`

Added strict attribution report models for unreadable secure-object rows.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`

## Description

Added frozen, strict, extra-forbid Pydantic models for metadata-only unreadable-row attribution. The new models cover one unreadable row, one impacted namespace, and the top-level attribution report. The namespace and report models validate that unreadable row counts and report totals remain internally consistent.

The models intentionally carry only safe metadata: namespace, digest, storage classification, schema version, timestamps, non-secret owner semantics, origin labels, and redacted context fields. They do not expose decrypted payloads or private natural keys. Review remediation added model-boundary redaction checks for context fields and timestamp range consistency checks for namespace summaries.

## Tests

Focused validation passed:

- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py`
- `uv run pytest src/aeat/application/test_repair_integrity.py`

The focused test file passed 19 tests, including the new attribution model invariant and review-remediation tests.
