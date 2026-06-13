---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase0b` `step32`

Implemented the first authority-tier verification layer in the central registry.

- Modified: `registry/aeat/legal/irpf.toml`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/_citation_blocklist.py`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/_workbook_parity.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_workbook_parity.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Registry legal and source catalogue records now carry explicit evidence tiers.
The committed Modelo 130 BOE legal reference is legal authority. The committed
Modelo 130 AEAT record-design XLS source is layout authority.

Workbook discovery and conversion reports now state the evidence tier they
satisfy and the tiers they cannot satisfy. Formula-form workbooks are executable
parity evidence, record-design and unsupported binary XLS artefacts are layout
authority, static/validation workbooks are official source guidance, and failed
or unreadable artefacts satisfy no tier.

Binary XLS conversion is implemented through LibreOffice in isolated storage.
The committed corpus is not mutated. The conversion report preserves the
original XLS path, byte count, and SHA-256, then classifies the converted XLSX
content by evidence tier.

Validator checks now reject formula workbook parity unless the referenced source
is executable parity evidence, reject executable parity sources for non-formula
workbook coverage, require export layouts to carry layout-authority source
evidence, and require formula legal references to be legal authority.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_catalogue_verification.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_workbook_parity.py -q`
- `uv run pytest src/aeat/domain/calculations/registry src/aeat/application/filing/test_schema_completeness.py src/aeat/application/filing/test_filing.py src/aeat/application/filing/test_import.py src/aeat/application/filing/test_export.py -q`
- `uv run ruff check src/aeat/domain/calculations/registry registry/aeat/legal/irpf.toml`
- `uv run ty check src/aeat/domain/calculations/registry`
- Corpus workbook verification: 72 artefacts, 47 record-design XLSX, 25 binary XLS, zero failed scans, all classified as layout authority.
- Full binary XLS conversion audit: 25 converted, zero failed, all classified as record-design layout and layout authority.
