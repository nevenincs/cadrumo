---
tags:
  - '#exec'
  - '#arch-remediation-registry-format'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S01'
related:
  - "[[2026-07-02-arch-remediation-registry-format-plan]]"
---

# Author the parameterised compiled-schema equality harness that captures each inline revision pre-migration ModeloRevision and asserts model equality against the post-migration fragmented shape

## Scope

- `src/aeat/domain/calculations/registry/tests/test_inline_fragment_equality.py`

## Description

- Author `test_inline_fragment_equality.py` parameterised over committed baseline fixtures under `_inline_fragment_baselines/`.
- Capture, per migratable revision, the pre-migration compiled `ModeloRevision` as `model_dump(mode="json")` written to a reviewable baseline fixture, verified deterministic across two loads.
- The gate reloads each revision from the live registry tree (post-migration fragmented shape) and asserts the compiled dump equals the committed pre-migration baseline, proving zero semantic drift across the authoring-surface move.
- Mark the module `[pytest.mark.unit, pytest.mark.hex_domain]` matching the sibling loader tests.

## Files

- `src/aeat/domain/calculations/registry/tests/test_inline_fragment_equality.py`
- `src/aeat/domain/calculations/registry/tests/_inline_fragment_baselines/231-2021-y-siguientes.json`
- `src/aeat/domain/calculations/registry/tests/_inline_fragment_baselines/361-2010-y-siguientes.json`
- `src/aeat/domain/calculations/registry/tests/_inline_fragment_baselines/369-esquema-exterior.json`
- `src/aeat/domain/calculations/registry/tests/_inline_fragment_baselines/369-esquema-importacion.json`
- `src/aeat/domain/calculations/registry/tests/_inline_fragment_baselines/369-esquema-union.json`
- `src/aeat/domain/calculations/registry/tests/_inline_fragment_baselines/303-2009-y-siguientes.json`

## Outcome

Harness green at the pre-migration state (7 passed): baselines match the current inline load, so the gate is armed to catch any drift introduced by the subsequent migrations. Baselines captured for the six revisions migratable at HEAD; the eight peer-WIP-blocked revisions get baselines when their trees are clean.

## Notes

The harness and its baselines are transient migration infrastructure, deleted by P03.S17 once every inline revision has converged. Baseline fixtures live under the test folder (wheel-excluded), not `src/aeat/_data`, so they do not touch the bundled-data size budget.
