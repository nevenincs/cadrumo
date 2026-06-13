---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S40'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W07.P20.S40`

Recorded the official Modelo 200 manual source for the general donations
deduction grid.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W07-P20-S40.md`

## Description

The lookup tied `is_deduccion_donativos_general` to the manual's Ley 49/2002
general donations table and recorded the manual-supported state, reiteration,
subtotal, total, and marked-period axes.

## Tests

Validated by extracting official manual text from `manual-sociedades-2024.pdf`
and parsing the Modelo 200 TOML rows for the general donations role.
