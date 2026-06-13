---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---

# `calculation-truth-registry` `wave5` `step7`

Modelo 131 DPA/DID export schema foundation.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/_export_parse.py`
- Modified: `src/aeat/application/filing/_export.py`
- Modified: `src/aeat/application/filing/__init__.py`
- Modified: `src/aeat/application/filing/test_filing.py`
- Modified: `src/aeat/application/filing/test_testing_registry.py`
- Modified: `src/aeat/domain/filing/_schema.py`
- Modified: `src/aeat/domain/filing/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Created: `src/aeat/domain/calculations/registry/_record_design.py`
- Created: `src/aeat/domain/calculations/registry/test_record_design.py`
- Modified: `registry/aeat/modelos/131.toml`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The registry export field schema now supports structured binding-backed fields.
This is required for Modelo 131 DPA activity-detail and DID direct-debit
records because those fields are official record-design structures, not flat
liquidacion casillas.

A read-only official record-design workbook inspector was added for AEAT XLSX
sources. It extracts sheet names, field positions, lengths, type codes,
validation text, content text, and total record lengths from the official
workbook rows. The inspector is used only for audit and verification; it does
not generate registry authority.

Focused tests now prove that the current Modelo 131 record design exposes DPA
and DID sheets, that the 2019-2023 workbook lacks those sheets, and that
structured export field bindings are validated by the registry validator.

The current Modelo 131 registry now defines the non-reserved 2026 DPA
activity-detail fields and DID IBAN field as layout-authority-backed bindings.
The binding selectors carry the official sheet, offset, length, and field data
type. The registry still exposes no Modelo 131 export layout; this avoids
presenting partial filing-grade export support before DPA/DID serialization,
direct-debit guards, and roundtrip verification are complete.

The filing draft boundary now persists registry binding values separately from
flat casilla values. Binding values can be scalar or repeated row-indexed
values, so table-shaped modelo data can remain table-shaped while casillas stay
as filing-grade totals or calculated outputs. The generic export renderer now
reads binding values from approved drafts and supports binding-row repeated
records for future official DPA/DID export layouts. Export parse-back also
understands binding-row repeated records, so future roundtrip verification is
not limited to one physical record per registry record definition.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_record_design.py src\aeat\domain\calculations\registry\test_registry_schema.py -q`
- `uv run pytest src\aeat\domain\calculations\registry\test_record_design.py src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\domain\calculations\registry\test_catalogue_verification.py -q`
- `uv run pytest src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_testing_registry.py -q`
- `uv run pytest src\aeat\application\filing\test_export.py -q`
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json`
- `uv run ruff check src\aeat\domain\calculations\registry\_record_design.py src\aeat\domain\calculations\registry\test_record_design.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\_export_parse.py src\aeat\application\filing\_export.py src\aeat\domain\calculations\registry\test_registry_schema.py`
- `uv run ty check src\aeat\domain\calculations\registry\_record_design.py src\aeat\domain\calculations\registry\test_record_design.py src\aeat\domain\calculations\registry\_schema.py src\aeat\domain\calculations\registry\_validate.py src\aeat\domain\calculations\registry\_export_parse.py src\aeat\application\filing\_export.py src\aeat\domain\calculations\registry\test_registry_schema.py`
