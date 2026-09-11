---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:ff6dc3ce4fbf56f95ed89eb6a44e4aca955ad385a60c00fa2dab4e4fb70a2f48'
step_id: 'S42'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

# [S | sonnet-high] Verify during the pilot that the temporal-coverage design-authority refusal pin still passes untouched. The decision asserts it does not weaken that refusal; the assertion is cheap to check and expensive to be wrong about, since a live test carries it. Proof: the pin passes before and after the pilot migration, quoted with its result.

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Changes

- `verify:` `pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_184_registry.py::test_modelo_184_raw_boe_design_eras_are_hash_pinned_and_explicitly_not_mapped` before the pilot (staged dry run, recorded in S17) -> `pass` (5 of 5)
- `verify:` the same pin after the live 303 migration was applied -> `pass` (5 of 5, untouched)
