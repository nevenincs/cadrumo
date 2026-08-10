---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:94fe42c80b3b8debceb28913af29603b01cb36da1928bc172f0b96923682849e'
step_id: 'S10'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Prove strict action-model validation, catalogue uniqueness, binding sufficiency, and terminal outcomes

## Scope

- `src/cadrumo/application/operator_actions/tests/test_models.py`

## Description

- Exercise strict action and catalogue identifiers through production Pydantic constructors.
- Exercise duplicate evidence, binding, missing-name, catalogue-action, and catalogue-argument rejection paths.
- Exercise resolved and missing action arguments, all closed no-recovery outcomes, action/no-recovery XOR, and invalid conditionality branches.
- Assert deterministic serialization and that all seven current declarations exclude external, database, and raw-command authority.
- Close the independent S10 review findings with direct production-constructor regressions only; defer live result/input-schema resolution to S14.

## Outcome

The application-only contract suite now protects the complete S10 model and
catalogue invariants. The runtime tests neither import entrypoint schema
builders nor implement a test-side resolver. No production code changed.

## Verification

`uv run --no-sync pytest src/cadrumo/application/operator_actions/tests -n0`

`39 passed in 0.90s`

`uv run --no-sync ruff check src/cadrumo/application/operator_actions/tests/test_models.py src/cadrumo/application/operator_actions/tests/test_catalogue.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/application/operator_actions/tests/test_models.py src/cadrumo/application/operator_actions/tests/test_catalogue.py`

`0 errors, 0 warnings, 0 notes`

## Notes

The S10 audit initially found missing direct regressions for verdict duplicate
members, closed-outcome consistency, and identifier fields. Those findings
were closed before this record. S14 remains the owner of live command/input
schema resolution and catalogue-to-runtime binding resolution.
