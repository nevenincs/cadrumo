---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:bbe76ec09c8f00aeac04df14f33b7a560b60c19b868dd273aafa12cf630fe547'
step_id: 'S309'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the positional-translation AST census and its hard-coded exception-class and factory-name exclusions; retain deferred translation behavior at the CadrumoError and renderer boundaries.

## Scope

- `locale positional translation inventory`
- `focused error rendering tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_locale_tr_positional_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S309.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/errors/tests/test_envelope.py src/cadrumo/core/errors/tests/test_error_message_never_blank.py src/cadrumo/entrypoints/cli/tests/test_language_flag_override.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Deferred translation remains proven by 15 focused error-envelope and language-selection tests. The deleted scanner classified exceptions by hard-coded names rather than behavior; the exact production detector remains red on the wider campaign findings.
