---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-29'
modified: '2026-08-29'
body_schema: 'body-v2'
body_hash: 'sha256:c961b8fa88e45de8c5e789c899f62fc3b2618ae175918f62d3121bde76769651'
step_id: 'S21'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Retire the four independent redeclarations of the dotted namespaced-id grammar in favour of the public canonical constant, and rule on whether its defining module should be public

## Scope

- `src/cadrumo/`

## Changes

- `M` `src/cadrumo/application/modelo/_work_lifecycle.py`
- `M` `src/cadrumo/application/workflow/run_models.py`
- `M` `src/cadrumo/core/_action_argument_resolution.py`
- `M` `src/cadrumo/core/_precondition_action_invariants.py`
- `M` `src/cadrumo/core/identifier_grammar.py`
- `M` `src/cadrumo/core/json_contract.py`
- `M` `src/cadrumo/domain/modelos/_verification_report.py`
- `M` `src/cadrumo/entrypoints/cli/_modelo_aux_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_cli_payload_constraint_authority.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/core/tests/test_json_contract_envelope.py src/cadrumo/domain/modelos/tests` -> `pass`
