---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
step_id: 'S03'
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

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path
     (e.g., S03 at L1, P02.S03 at L2, W01.P02.S03 at L3 / L4). The
     step_id frontmatter field below carries the canonical identifier;
     the heading restates the display path as a reading hint. -->

# `schema-hardening` `P01.S03`

Selected the Modelo 200 maintenance-employment correction family as the first
implementation candidate and blocked the remaining optional/numeric families
pending manual source lookup.

- Modified: `.vault/audit/2026-05-22-schema-hardening-audit.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P01-S03.md`

## Description

The selected candidate is a compact 12-row grid where labels distinguish
`RDL 6/2010` from `RDL 13/2010` while sharing `DT 13a.2 LIS`. The audit records
that generic `con`/`sin` normalization is too broad and must not be treated as
a harmless axis globally.

## Tests

Validation was source-visible classification review only. No production code was
changed in this step.
