---
tags:
  - '#exec'
  - '#registry-edition-authoring'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:2b0d6ad27f4711f62133b3117b96711de0adc6939f4ba59a7f0b7c6fa4c3dd2f'
step_id: 'S42'
related:
  - "[[2026-09-09-registry-edition-authoring-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# [S | sonnet-high] Verify during the pilot that the temporal-coverage design-authority refusal pin still passes untouched. The decision asserts it does not weaken that refusal; the assertion is cheap to check and expensive to be wrong about, since a live test carries it. Proof: the pin passes before and after the pilot migration, quoted with its result.

## Scope

- `src/cadrumo/domain/calculations/registry/tests`

## Changes

- `verify:` `pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_184_registry.py::test_modelo_184_raw_boe_design_eras_are_hash_pinned_and_explicitly_not_mapped` before the pilot (staged dry run, recorded in S17) -> `pass` (5 of 5)
- `verify:` the same pin after the live 303 migration was applied -> `pass` (5 of 5, untouched)
