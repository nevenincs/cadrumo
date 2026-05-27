---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
step_id: 'S07'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `schema-hardening` `P02.S07`

Looked up cadastral and miscellaneous optional-token families and recorded that
they remain blocked from generic normalization.

- Modified: `.vault/audit/2026-05-22-schema-hardening-audit.md`
- Created: `.vault/exec/2026-05-22-schema-hardening/2026-05-22-schema-hardening-P02-S07.md`

## Description

Cadastral slot numbers, prize valuation second blocks, agricultural objective
estimation rows, Madrid parent/detail housing fields, and Anexo B `aav` rows all
map to source-visible structure. None is approved for global optional-token or
numeric-token suppression in this slice.

## Tests

Validation was manual lookup against committed registry labels and prior audit
records. No production code was changed in this step.
