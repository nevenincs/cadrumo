---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S42'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W07.P21.S42`

Recorded the official Modelo 200 manual source for the Canarias investment
deduction grid.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W07-P21-S42.md`

## Description

The lookup tied the grid to the manual's `Deducciones inversión en Canarias con
límites incrementados` table and recorded the visible subfamily, state, year,
and La Palma/La Gomera/El Hierro markers from registry labels.

## Tests

Validated by extracting official manual text from `manual-sociedades-2024.pdf`
and parsing the Modelo 200 TOML rows for the Canarias investment roles.
