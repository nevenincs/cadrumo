---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-04'
modified: '2026-05-04'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `phase-0c` `submitted-file-observation`

Implemented registry-backed parsing of AEAT submitted filed-declaration payloads and connected it to live filed-declaration observations.

- Modified: `src/aeat/domain/calculations/registry/_export_parse.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/application/filing/_export.py`
- Modified: `src/aeat/application/filing/test_export.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- Modified: `registry/aeat/modelos/130.toml`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Added a central parser that reads AEAT fixed-width filed/exported payloads through committed registry export layouts. The parser validates record boundaries, encodings, declared line endings, literal fields, fixed field slices, signed money fields, integer and decimal fields, and boolean fields. Parsed casilla values include the registry field locator so live observations can preserve provenance without embedding casilla layouts in Python.

The application export verifier now uses the central parser instead of its own private fixed-width read logic. The declaration-register live reader now captures submitted-file bytes, resolves the matching registry snapshot, parses the submitted file through the export layout, and returns `FiledDeclarationObservation` with `ObservedCasillaValue` entries and extraction coverage.

Submitted-file normalization also verifies the filed payload's modelo, filing year, and period fields against the declaration row before emitting casilla observations. A context mismatch fails before any previous-filing binding can consume the observation.

Modelo 130 casillas now declare reciprocal `export_refs` for their export-layout fields. This is required by the registry resolver and prevents export layouts from silently pointing at casillas that do not claim the same binding.

Extraction profiles now declare accepted artefact kinds and fail-hard semantics. Registry validation rejects a profile whose accepted artefact kinds do not match its surface, and rejects any attempt to use a justificante PDF as casilla data.

## Tests

Focused syntax checks passed for the changed runtime modules.

Focused behaviour tests passed:

- `uv run pytest src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\application\filing\test_export.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py -q`
- `uv run pytest src\aeat\application\filing\test_export.py -q`
- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py -q`
- `uv run pytest src\aeat\domain\calculations\registry\test_registry_schema.py -q`

Static checks passed:

- `uv run ruff check` on the touched runtime and test files.
- `uv run ty check` on the touched runtime files.
- `git diff --check` on the touched runtime, test, TOML, plan, and execution files.
- Static banned-metadata discovery over touched runtime, test, and TOML files returned no hits.

Read-only live verification against the authenticated AEAT session reached the submitted-file capture path for Modelo 130 year 2024 period 4T and produced one observation with three artefacts and 19 parsed casilla observations. The reported submitted-file extraction coverage was 1.000. No casilla values or identity data were printed.
