---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` formula-modelo standardization

Standardized formula-bearing modelo registry ownership and added runtime parity
tests with pytest duration profiling.

- Modified: `registry/aeat/modelos/111.toml`
- Modified: `registry/aeat/modelos/130.toml`
- Modified: `registry/aeat/modelos/131.toml`
- Modified: `registry/aeat/modelos/202.toml`
- Modified: `.vault/audit/2026-05-06-calculation-truth-registry-parity-review.md`
- Created: `src/aeat/domain/calculations/registry/test_formula_modelo_registry_parity.py`
- Created: `src/aeat/domain/calculations/registry/test_modelo_111_registry.py`
- Created: `src/aeat/domain/calculations/registry/test_modelo_130_registry.py`
- Created: `src/aeat/domain/calculations/registry/test_modelo_131_registry.py`

## Description

Modelos 111, 130, and 131 now declare construct ownership for their
formula-bearing revisions. Each construct owns casillas, formulas, legal/source
evidence surfaces, export/extraction references, live/static references,
verification expectations, deadline windows where defined, and workflow
application links.

Modelo 202 construct ownership was also brought into parity after the
generalized formula-modelo guard identified missing review, approval,
reconciliation, and workflow surfaces on its formula-bearing revisions.

The new tests exercise validated snapshots and real registry formula runtime
behavior. They do not define modelo or casilla schemas in test fixtures.

## Tests

Registry validation passed for Modelos 111, 130, 131, and 202.

`ruff`, `ty`, and targeted pytest passed. Serial pytest duration profiling for
the new formula-modelo suite passed with 15 tests in 37.30 seconds. The xdist
run passed with 15 tests in 24.17 seconds. The remaining dominant cost is the
generalized formula parity guard, which validates all formula-bearing registry
revisions and takes about 20-21 seconds.
