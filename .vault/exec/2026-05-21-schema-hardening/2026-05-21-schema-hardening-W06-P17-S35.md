---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-07-31'
body_hash: 'sha256:9b7f6c8ac85621f08ce6e9376bac2d4ee84f894a347578e024bf7cd5df941de7'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W06.P17.S35`

Promoted the financial-expense carryforward grid as a future exact-ID
table-axis candidate.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W06-P17-S35.md`

## Description

The audit promotes this candidate only with the legal branch axis preserved:
`Por límite 16.5 y 83 LIS` and `Resto` are not interchangeable. Total rows are
also excluded from generation-year treatment.

## Tests

No registry files were edited. The step is validated through vault plan and
frontmatter checks after closure.
