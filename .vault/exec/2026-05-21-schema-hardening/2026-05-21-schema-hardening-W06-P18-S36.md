---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S36'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W06.P18.S36`

Recorded the official Modelo 200 manual source for the general negative
tax-base compensation table.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W06-P18-S36.md`

## Description

The lookup tied the table to the manual's page 15 instructions for `Detalle de
la compensación de bases imponibles`, including the three official columns and
the exclusions for cooperatives, fiscal groups, and the Canary Islands shipping
regime.

## Tests

Validated by extracting official manual text from `manual-sociedades-2024.pdf`
and parsing the Modelo 200 TOML rows for the related BIN roles.
