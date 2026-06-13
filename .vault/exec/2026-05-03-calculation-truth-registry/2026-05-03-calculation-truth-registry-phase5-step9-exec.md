---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

# Phase 5 Step 9 Execution

Deleted the hardcoded VAT-to-Modelo-303 casilla bridge:

- Removed `src/aeat/domain/vat/_modelo_303_mapping.py`.
- Removed `src/aeat/domain/vat/test_modelo_303_mapping.py`.
- Removed public exports for `MODELO_303_CASILLA_MAPPING`,
  `Modelo303Contribution`, `CasillaRole`, and
  `lookup_modelo_303_contribution`.
- Added an import-contract deletion gate proving the private bridge file and
  test file are physically absent, the private module cannot resolve through
  import machinery, and the public VAT package does not expose the bridge
  names.

Rationale:

- VAT classification and rate lookup remain generic legal substrate.
- Modelo-specific projection from VAT categories to casillas is filing truth and
  must be supplied by validated registry definitions, not Python domain code.

Verification:

- `uv run --no-sync ruff check src\aeat\domain\vat tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check src\aeat\domain\vat tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\domain\vat`

Result: ruff passed, ty passed, and the focused pytest slice passed with
87 tests.

Residual risk:

- The retained VAT catalogue still contains high-level Modelo 303 filing
  guidance and `declares_in_modelos` metadata, but the category-to-casilla
  projection is deleted. Registry-backed Modelo 303 binding remains future
  work.
