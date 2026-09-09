---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a5881c333696d61fb8e203559b6debfcf7ca819859b0e1ab9ef53b21af12b3fe'
step_id: 'S305'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the cast-rationale comment census, its AST matcher and alias restrictions, shared test-inventory exports, copied source fixtures, and detector-only tests; retain configured type checking and useful local explanations.

## Scope

- `cast rationale gate cluster`
- `focused inventory tests`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/tests/test_cast_rationale_inventory.py`
- `M` `src/cadrumo/tests/inventory.py`
- `M` `src/cadrumo/tests/__init__.py`
- `M` `src/cadrumo/tests/test_type_ignore_rationale_inventory.py`
- `M` `dev/tests/test_test_inventory.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `M` `.vault/plan/2026-09-04-reachability-burndown-plan.md`
- `A` `.vault/exec/2026-09-04-reachability-burndown/2026-09-04-reachability-burndown-W05-P12-S305.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/tests/test_type_ignore_rationale_inventory.py dev/tests/test_test_inventory.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The removed gate demanded marker comments on 239 cast calls while the configured type behavior remained outside its judgment. The exact production detector remains red on the wider campaign findings.
