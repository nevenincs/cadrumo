---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S47'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W08.P23.S47`

Promoted Anexo C carryforward axes only as basket-preserving exact-ID
candidates.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W08-P23-S47.md`

## Description

The audit allows `origin_year` and `carryforward_state` extraction only while
preserving the current legal basket and dictionary section. It blocks any
cross-basket merge by repeated `pendiente`, `aplicado`, or future-pending
captions.

## Tests

No registry files were edited. Verification is through vault plan and
frontmatter checks after closure.
