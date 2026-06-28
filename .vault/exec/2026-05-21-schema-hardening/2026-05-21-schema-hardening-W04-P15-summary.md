---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W04.P15` summary

Completed the Catalunya generated/pending source-lookup phase.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Modified: `.vault/audit/2026-05-21-schema-hardening-review.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W04-P15-S29.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W04-P15-S30.md`

## Description

The phase tied IDs `2004` and `2005` to the Renta 2025 manual deduction for
Catalunya investment in agricultural and housing cooperative societies, then
blocked promotion because the current generated/pending roles do not preserve
the family-specific base.

## Tests

Validated by reading the registry TOML rows, extracting the Renta 2025 manual
text with `pdftotext`, closing S29 and S30 with the vault plan CLI, and running
plan/frontmatter checks.
