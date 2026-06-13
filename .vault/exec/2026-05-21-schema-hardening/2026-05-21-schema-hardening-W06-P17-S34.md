---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S34'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W06.P17.S34`

Recorded the official Modelo 200 manual source for the financial-expense
pending-deduction grid.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W06-P17-S34.md`

## Description

The lookup tied `is_gastos_financieros_pendiente_deducir` rows to the manual's
financial-expense limitation table under art. 16 LIS. The audit records the
manual-supported year, state, limit-branch, and total-row axes.

## Tests

Validated by extracting official manual text from `manual-sociedades-2024.pdf`
and parsing the Modelo 200 TOML rows for the current broad role.
