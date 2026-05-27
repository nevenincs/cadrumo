---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
step_id: 'S12'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path
     (e.g., S03 at L1, P02.S03 at L2, W01.P02.S03 at L3 / L4). The
     step_id frontmatter field below carries the canonical identifier;
     the heading restates the display path as a reading hint. -->

# `secure-object-integrity` `P04.S12`

Added readable-row secure-object envelope contract validation against owning repository classification and schema boundaries.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`
- Created: `.vault/audit/2026-05-22-secure-object-integrity-P04-S12-review.md`

## Description

The repair backend now has a metadata-only envelope validation report that scans raw secure-object rows, skips undecryptable rows for attribution, and validates readable rows against the owning namespace contract. The contract map is built from production namespace owners and records expected row classification, maximum supported schema version, contract kind, and typed envelope payload where the owner persists an `Envelope`.

The report emits opaque row ids and key digests only. It flags row-level classification drift, row schema versions newer than the owner supports, invalid typed envelope payloads, inner envelope classification drift, inner envelope schema drift, and unknown owner contracts. It does not expose payload bytes or natural object keys.

Tests now cover clean readable rows, multiple readable contract-drift modes, unreadable-row deferral to attribution, strict report count invariants, and a guard proving the envelope contract map covers every active production namespace discovered by the S11 inventory helper.

## Tests

Focused gates passed:

- `uv run ruff check src/aeat/application/repair_integrity.py src/aeat/application/test_repair_integrity.py`
- `uv run pytest src/aeat/application/test_repair_integrity.py -q`

Mandatory scoped review found no critical or high blockers.

Review audit: `2026-05-22-secure-object-integrity-P04-S12-review`.
