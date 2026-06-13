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

# Phase 5 Step 7 Execution

Deleted the legacy Python formula/ruleset authority package and its import-contract
tests:

- Removed `src/aeat/domain/formulas`.
- Removed `tests/import_contract/domain/formulas`.
- Removed formula-dependent export tests that paired deleted rulesets with
  generated export schemas.
- Removed the Modelo 130 extractor symmetry assertion that imported
  `ALL_RULESETS`.
- Updated import-contract gates so `aeat.domain.formulas` is a deleted root
  module and must not resolve through Python import machinery.
- Removed stale formula/ruleset references from export comments, generated API
  docs, the DR303 fixture note, inbound declaration docs, casilla docs, VAT
  mapping docs, and core error docs.

Verification:

- `uv run --no-sync ruff check tests\import_contract\test_adr_layout_import_smoke.py tests\import_contract\test_registry_deletion_gates.py src\aeat\adapters\inbound\declaracion\test_modelo_130_v2025.py src\aeat\adapters\inbound\declaracion\__init__.py src\aeat\adapters\outbound\aeat\export\_formats\modelo_130_2025.py src\aeat\adapters\outbound\aeat\export\_formats\modelo_303_2024.py src\aeat\adapters\outbound\aeat\export\_formats\modelo_303_2025.py src\aeat\adapters\outbound\aeat\export\_formats\_record_spec.py src\aeat\core\errors\__init__.py src\aeat\domain\casillas\models.py src\aeat\domain\vat\_modelo_303_mapping.py`
- `uv run --no-sync ty check tests\import_contract\test_adr_layout_import_smoke.py tests\import_contract\test_registry_deletion_gates.py src\aeat\adapters\inbound\declaracion\test_modelo_130_v2025.py src\aeat\adapters\outbound\aeat\export\_formats src\aeat\core\errors\__init__.py src\aeat\domain\casillas\models.py src\aeat\domain\vat\_modelo_303_mapping.py`
- `uv run --no-sync pytest tests\import_contract\test_adr_layout_import_smoke.py tests\import_contract\test_registry_deletion_gates.py src\aeat\adapters\inbound\declaracion\test_modelo_130_v2025.py src\aeat\adapters\outbound\aeat\export\_formats`

Result: ruff passed, ty passed, and the focused pytest slice passed with
394 tests.

Residual risk:

- The removed formula-dependent export/schema alignment tests do not yet have
  a registry-backed replacement. Current coverage proves deletion, fail-closed
  behavior, and serializer behavior, but registry-to-export completeness must
  be restored from the canonical registry rather than the deleted rulesets.
