---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S06'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P02.S06 - legacy root registry authority baseline

Scope: add a frozen registry authority access baseline for the legacy modelo CLI root.

## Description

- Add a static architecture guard for direct `resources().modelos.authority` reads in `_modelo.py`.
- Add a call-count guard for direct `RegistryQueryService` construction in `_modelo.py`.
- Preserve the current baseline while preventing new registry authority bypasses in the CLI root.

## Outcome

`test_legacy_modelo_root_does_not_add_registry_authority_reads` now freezes the direct registry authority read budget at two occurrences and direct `RegistryQueryService` construction at one call. Future extraction work can lower these budgets as authority reads move into application services.

## Notes

Verification: `uv run --no-sync pytest src/aeat/entrypoints/cli/test_architecture_boundaries.py -q` passed.
