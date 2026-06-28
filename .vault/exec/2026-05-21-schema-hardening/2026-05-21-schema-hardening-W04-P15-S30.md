---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S30'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W04.P15.S30`

Blocked the Catalunya generated/pending pair from family-local promotion until
a separate semantic-role correction preserves the real legal family.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W04-P15-S30.md`

## Description

The manual supports a family-local legal boundary, but the current generated
and pending roles are CCAA-generic or inconsistent. The audit therefore blocks
sidecar extraction for IDs `2004` and `2005` until a reviewed registry role
change can use a family-specific base aligned with
`irpf_deduccion_catalunya_cooperativas_agrarias`.

## Tests

No source registry files were edited. The phase is validation-only and is
checked through vault plan/frontmatter validation.
