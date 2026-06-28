---
tags:
  - '#exec'
  - '#iva-compensation-chain'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-iva-compensation-chain-audit-research]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
---

# `iva-compensation-chain` execution summary

## Scope

Executed the accepted ADR and L2 plan for the IVA compensation chain. The implementation updates the previous-filing resolver, the relation-to-binding materialization bridge, Modelo 303 compensation fields, Modelo 390 annual compensation fields, legal/source catalogue grounding, and regression tests.

## Changes

- Added direct previous-filing support for singular `source_output` selectors with `source_period_offset_from_target`.
- Added relation target-binding materialization for active resolved relations.
- Aligned local relation prefill with canonical relation source requirements.
- Updated Modelo 303 from the legacy `67`/`71` compensation shape to current `110`/`78`/`87`/`69` plus internal generated and carry-forward balance outputs.
- Added Modelo 390 `97` and `662` compensation reconciliation fields from Modelo 303 observations.
- Persisted missing legal references for LIVA arts. 115 and 116, RIVA arts. 29 and 30, and the AEAT 303 2026 record-design source.

## Verification

Passing:

- `uv run pytest src/aeat/domain/calculations/registry/test_selector_shape.py src/aeat/domain/calculations/registry/test_modelo_303_registry.py src/aeat/domain/calculations/registry/test_modelo_390_registry.py src/aeat/domain/calculations/registry/test_relation_offset.py src/aeat/domain/calculations/registry/test_modelo_chain_resolution.py`
- Source and legal catalogue verification through `verify_source_catalogue` and `verify_legal_catalogue`.

Residual known failures outside this remediation:

- `uv run pytest src/aeat/domain/calculations/registry/test_cross_dependency_contract.py` still fails on pre-existing Modelo 130 same-model previous-period relation contracts.
- `uv run pytest src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py` passes 21 tests and has one remaining failure on the same Modelo 130 previous-quarter copy relation requiring more than one observation.
