---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S38'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W06.P19.S38`

Recorded the official Modelo 200 manual source for cooperative negative-quota
compensation.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W06-P19-S38.md`

## Description

The lookup tied `is_cooperativa_compensacion_cuotas` to the cooperative-only
negative-quota compensation concept under Ley 20/1990 and recorded the visible
year/state axes from the registry labels.

## Tests

Validated by extracting official manual text from `manual-sociedades-2024.pdf`
and parsing the Modelo 200 TOML rows for the cooperative compensation role.
