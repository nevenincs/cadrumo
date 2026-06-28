---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S37'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W06.P18.S37`

Blocked single-role promotion for the general negative tax-base compensation
grid.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W06-P18-S37.md`

## Description

The table shape is source-grounded, but the registry splits the table across
`is_bin_detalle_compensacion` and `is_compensacion_bases_negativas`. The audit
therefore blocks implementation until an exact-ID inventory and semantic-role
policy decision handles that split.

## Tests

No registry files were edited. The step is validated through vault plan and
frontmatter checks after closure.
