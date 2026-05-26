---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- PHASE SUMMARY:
     This file rolls up every <Step Record> belonging to one Phase
     of the originating plan. Each Step (S##) in the Phase produces
     one <Step Record> in `.vault/exec/`; this summary aggregates
     them, lists modified / created files across the Phase, and
     reports verification status. -->

# `schema-hardening` `P06` summary

Completed the next registry hardening substrate after the validator split.

- Modified: `src/aeat/domain/calculations/registry/_validate_references.py`
- Modified: `src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
- Modified: `.vault/plan/2026-05-22-schema-hardening-plan.md`
- Modified: `.vault/audit/2026-05-26-schema-hardening-code-review.md`
- Created: `src/aeat/domain/calculations/registry/_validate_reference_sections.py`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P06-S16.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P06-S17.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P06-S18.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P06-S19.md`

## Description

P06 reduced the largest remaining reference-validator helper by extracting
section-specific walkers, tightened generic loader and fragment-discovery
regression gates, audited the loader for per-modelo branching, and selected
M131 as the next fragmentation target from tracked file-size and revision-count
evidence.

The loader contract remains generic: M100, M200, and M303 are covered through
fragment-directory revisions, M131 is covered through revision-file sources,
and M130 remains a single-file source without requiring model-specific loader
logic.

## Tests

Ruff passed for the touched Python modules. Focused pytest gates passed for
referential integrity, selector shapes, and loader directory mode. Vault plan
checks, schema-hardening frontmatter checks, and schema-hardening body-link
checks passed.

The S17 review found one MEDIUM issue in the initial fragment inventory test;
that issue was fixed and re-reviewed as resolved before commit.
