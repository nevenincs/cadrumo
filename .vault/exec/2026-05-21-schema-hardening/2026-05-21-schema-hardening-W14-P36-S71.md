---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S71'
related:
  - '[[2026-05-21-schema-hardening-plan]]'
---

# `schema-hardening` `W14.P36.S71`

Probed the remaining warning suppressors for hidden Modelo 100 and Modelo 200
singleton exposure.

- Modified: `.vault/audit/2026-05-21-schema-hardening-semantic-role-sidecar-audit.md`
- Created: `.vault/exec/2026-05-21-schema-hardening/2026-05-21-schema-hardening-W14-P36-S71.md`

## Description

The corpus probe simulated disabling each helper against the current Modelo
100 and Modelo 200 registry. The exact W08-W13 helpers have no independent new
warning exposure. Disabling the correction suffix guard would expose 151
expected Modelo 200 correction warnings, disabling `axis_token_group` would
expose 17 warnings, and disabling `optional_or_numeric_token_strip` would
expose 36 warnings.

## Tests

Ran an inline `uv run python` corpus probe using the committed registry loader
and the real semantic-role validator helpers.
