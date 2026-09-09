---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:e3394db4a727cb5f9c8799e5269f8414c899a4ac8ac45a0adfb74cd49b117bfa'
step_id: 'S47'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

# Run both dead-code audits at the Wave 2 handoff

## Scope

- `dev/audit/dead_code.py and dev/audit/unreachable_code.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/convenio.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/legal_parameters.py`
- `M` `src/cadrumo/domain/calculations/registry/facts/modelo_projections.py`
- `M` `src/cadrumo/domain/categories/registry.py`
- `M` `src/cadrumo/domain/deadlines/festivos.py`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W02-P09-S47.md`
- `verify:` `just audit-dead-code` -> `pass`
- `verify:` `just audit-unreachable-code` -> `fail`

## Notes

The final exact reachability search reports no Wave 2 provider finding and zero unreachable shipped modules. The repository-wide command still reports 480 unused symbols outside this campaign.
