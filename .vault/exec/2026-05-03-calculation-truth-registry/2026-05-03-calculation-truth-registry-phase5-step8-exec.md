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

# Phase 5 Step 8 Execution

Deleted the committed generated fichero-BOE Python layouts and the Python source
generator that emitted them:

- Removed `_generate.py`.
- Removed `modelo_130_2024.py`, `modelo_130_2025.py`, `modelo_303_2024.py`,
  `modelo_303_2024_preview.py`, and `modelo_303_2025.py`.
- Removed model-layout tests and golden tests that validated those committed
  generated modules.
- Removed `_test_fixtures.py`, which still carried modelo-specific export
  fixture truth inside the runtime package.
- Kept only shared primitive runtime files in `_formats`: `__init__.py`,
  `_deserialise.py`, `_ingest.py`, `_record_spec.py`, and `_serialise.py`.
- Updated docs/comments to describe registry-backed layouts rather than
  committed per-modelo Python modules.
- Tightened import-contract gates so the retained runtime file set is exact and
  no deleted generator provenance markers remain in runtime sources.

Verification:

- `uv run --no-sync ruff check src\aeat\adapters\outbound\aeat\export\_formats src\aeat\application\filing\_export.py tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check src\aeat\adapters\outbound\aeat\export\_formats src\aeat\application\filing\_export.py tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\adapters\outbound\aeat\export\_formats`

Result: ruff passed, ty passed, and the focused pytest slice passed with
131 tests.

Residual risk:

- Shared serializer/deserializer primitive behavior remains covered, but
  registry-backed export-layout completeness is still future work. The old
  generated modules no longer provide any export-layout authority.
