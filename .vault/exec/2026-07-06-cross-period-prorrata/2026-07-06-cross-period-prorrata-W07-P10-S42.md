---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:44c261382bf5b6c7c153d64d1dad556200eae71d141a88d682d116fcaadc2fdd'
step_id: 'S42'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add a typed prorrata_regularizacion selector contract and selector-registry construction gate so the source is a legal DataBindingDefinition.source before any TOML binding is declared

## Scope

- `src/aeat/domain/calculations/registry/_bindings.py`
- `src/aeat/domain/calculations/registry/tests/test_selector_shape.py`

## Description

- Re-read the cross-period prorrata ADR, the source-kind deferral ADR, the current W07 plan rows, and the existing selector-dispatch tests before editing.
- Ran the required RAG grounding for the binding selector registry and confirmed the established strict-selector plus dispatch-table pattern in `_bindings.py`.
- Added a strict `prorrata_regularizacion` selector model for the existing `BindingSourceKind.PRORRATA_REGULARIZACION` member.
- Registered the selector through the construction-time selector registry and the build-time validator dispatch table using the existing selector-only validator convention.
- Added source-casilla/modelo accessor support so future registry rows expose the canonical Modelo 303 annual prorrata inputs through the same typed helpers as previous-filing, relation-prefill, and annual-compensation sources.
- Added selector-shape regressions proving the canonical Modelo 303 casilla-44 shape constructs, hydrates, serializes, and validates, while partial, quarter-only, wrong-modelo, and wrong-output selectors are refused at construction.

## Outcome

- S42 is complete: `prorrata_regularizacion` is now a legal typed `DataBindingDefinition.source` family before any TOML binding is declared.
- No registry TOML binding, resolver enrollment, deferred-source disposition, or source-kind taxonomy carve-out was changed; those remain ordered under W07.P10.S43 through W07.P12.S47.

## Notes

- Verification passed: `uv run --no-sync ruff check src\aeat\domain\calculations\registry\_bindings.py src\aeat\domain\calculations\registry\tests\test_selector_shape.py`.
- Verification passed: `uv run --no-sync pytest -q src\aeat\domain\calculations\registry\tests\test_selector_shape.py -n 0` (28 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\domain\calculations\registry\tests\test_binding_build_validation.py src\aeat\domain\calculations\registry\tests\test_binding_aggregation.py -n 0` (25 passed).
- Verification passed: `uv run --no-sync pytest -q src\aeat\domain\calculations\registry\tests\test_binding_source_kind_taxonomy.py src\aeat\application\modelo\tests\test_binding_source_kind_mesh_parity.py src\aeat\application\aggregation\tests\test_source_kind_enrollment_status.py src\aeat\domain\calculations\registry\tests\test_source_enrollment.py -n 0` (28 passed).
- Verification passed: `uv run --no-sync vaultspec-core vault check frontmatter --feature cross-period-prorrata`.
- Verification passed: `uv run --no-sync vaultspec-core vault check features --feature cross-period-prorrata`.
