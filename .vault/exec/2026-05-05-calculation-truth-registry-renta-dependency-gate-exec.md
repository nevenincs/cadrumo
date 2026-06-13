---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-modelo-100-renta-source-dependency-reference]]'
---



# `calculation-truth-registry` `phase-4r` `renta-dependency-gate`

Implemented the Modelo 100 dependency-classification gate described by the
ADR and the Renta source-dependency reference.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`
- Modified: `registry/aeat/modelos/100.toml`

## Description

The registry now permits `factual_evidence` dependency classifications without
declaring calculation relations. Direct annual-settlement dependencies still
must declare relation coverage, and explicit `non_dependency` classifications
must remain detached from target constructs and relation refs.

Modelo 100 ejercicio 2025 now classifies the direct annual-settlement sources
already represented by relations, the evidence-only sources listed in the Renta
source-dependency reference, and the explicit non-dependencies for corporate,
related-party, and foreign-asset modelos.

The evidence-only closure is now reflected in the May 3 plan for Modelos 303,
390, 347, 349, 369, 840, 036, and 037. The non-dependency closure is also
reflected for Modelos 202, 200, 232, and 720.

The validator now fails a revision when a relation source lacks a dependency
classification, when a relation source is marked as a non-dependency, when a
classification omits relation coverage for its source, or when multiple
classifications attempt to own the same source modelo.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_100_parity_tapes.py src\aeat\domain\calculations\registry\test_parity_tapes.py -q`
  passed.
- `uv run ruff check src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `uv run ty check src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py`
  passed.
- `git diff --check` passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_contract.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_contract.py -q`
  passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_modelo_100_registry.py src\aeat\domain\calculations\registry\test_modelo_202_registry.py src\aeat\domain\calculations\registry\test_modelo_232_registry.py src\aeat\domain\calculations\registry\test_modelo_349_registry.py src\aeat\domain\calculations\registry\test_cross_dependency_contract.py src\aeat\domain\calculations\registry\test_formula_runtime.py src\aeat\domain\calculations\registry\test_cross_dependency_calculations.py -q`
  passed.
