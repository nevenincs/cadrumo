---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:074482da304f815996ab99eccfebac037888ac4bbc9bac91423954d888ea4c14'
step_id: 'S227'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Withdraw the wholly unreachable Impuesto sobre Sociedades compensation prototype, its two dormant error registrations, and its synthetic per-cohort model suite; preserve the accepted Modelo 200 BIN carry and total-continuity mechanisms at their live registry, binding, and verification owners, which neither name nor consume the redundant cohort representation.

## Scope

- `IS compensation domain prototype and tests`
- `central error registry`
- `accepted Modelo 200 BIN continuity decision and live calculation/binding ownership`
- `exact reachability signal`
- `focused gates`
- `cadence reference`
- `Step Record`
- `and independent code review.`

## Changes

- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `D` `src/cadrumo/domain/is_compensation/__init__.py`
- `D` `src/cadrumo/domain/is_compensation/bin_carry_forward.py`
- `D` `src/cadrumo/domain/is_compensation/errors.py`
- `D` `src/cadrumo/domain/is_compensation/tests/__init__.py`
- `D` `src/cadrumo/domain/is_compensation/tests/test_bin_carry_forward.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/errors/registry/_application_part2.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s227-direct src/cadrumo/core/errors/tests/test_registry.py src/cadrumo/core/errors/tests/test_registry_enforcement.py src/cadrumo/core/errors/tests/test_error_base_binding_order.py src/cadrumo/core/errors/tests/test_error_message_never_blank.py src/cadrumo/application/calculations/tests/test_modelo_200_bin_carry_forward_continuity.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

The exact audit exits 1 on the remaining backlog, as designed. This step reduced unreachable modules from 54 to 51 and orphaned test modules from 5 to 4 while leaving the 306 reachable-module unused-symbol findings unchanged. The accepted BIN continuity mechanism remains live in registry bindings and application calculation tests; the deleted package had no consumer outside its own synthetic test and two error-registry strings.
