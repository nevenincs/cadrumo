---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S24'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# W02.P09.S24 Modelo 130 lifecycle without copied ids

Scope:
- `src/aeat/entrypoints/cli/test_modelo_work_natural_key.py`

## Description

- Add a real CLI workflow test for Modelo 130 create, calculate, verify, and export.
- Pass only modelo/year/period between lifecycle commands after creation.
- Use real profile creation, real calculation inputs, real verification, and real fichero export.

## Outcome

The basic Modelo 130 CLI workflow no longer requires copied `work_unit_id` or `calculation_revision_id` values between common commands.

## Notes

- The test still captures ids for assertions, but never passes them to later lifecycle commands.
