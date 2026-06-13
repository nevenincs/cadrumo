---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W05.P18.S128'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# declaracion-extraction-architecture W05.P18.S128

Authored the Modelo 390 (IVA annual summary) `declaracion_pdf` extraction
profile covering the 5 named_label closure casillas confirmed in the hybrid
corpus PDFs, and added parametrised round-trip tests against the 2022 and
2023 Spanish-language fixtures.

- Modified: `src/aeat/_data/registry/aeat/modelos/390.toml`
- Modified: `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Corpus confirmation

All 3 corpus PDFs (`2021-0A.pdf`, `2022-0A.pdf`, `2023-0A.pdf`) are hybrid
documents: AEAT receipt header on page 1, full printed declaración-resumen
anual form from page 2 onwards with apartados, casilla box numbers, printed
labels, and declared values. Confirmed with pdfplumber text extraction.

The 2021 specimen is in English (non-standard AEAT account language setting).
The 2022 and 2023 specimens are in Spanish.

## Slug → box mapping

| casilla_id | box | printed label |
|---|---|---|
| `iva.anual.cuota-devengada-total` | 47 | `Total cuotas IVA y recargo de equivalencia` |
| `iva.anual.cuota-deducible-total` | 64 | `Suma de deducciones` |
| `iva.anual.resultado-regimen-general` | 65 | `Resultado régimen general (47 - 64)` |
| `iva.anual.compensacion-ultimo-periodo-97` | 97 | `{ A compensar` |
| `iva.anual.compensacion-generada-ejercicio-no-97` | 662 | `Cuotas pendientes de compensación generadas en el ejercicio` |

All 5 casillas carry `1.000,00` adjacent to the printed label in the 2022 and
2023 corpus specimens. The 2021 English PDF uses English-language labels
(`Total deductions`, `Result of the general system`, `{To offset`, etc.) and
also lacks a box-47 value; it is intentionally excluded from the round-trip
test parametrisation.

## Profile design

- `surface = "declaracion_pdf"`, `accepted_artefact_kinds = ["declaration_pdf"]`
- `match_strategy = "named_label"` for all 5 targets
- `confidence = "strict"`, `min_coverage = "1"`, `failure_semantics = "fail_hard"`
- Construct `modelo-390-iva-resumen-anual` updated to include the profile in
  its `extraction_profiles` closure array.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py src/aeat/adapters/inbound/declaracion/ -x -q`
  — 53 passed (including 2 new parametrised M390 round-trip tests)
- `uv run --no-sync ruff check src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`
  — All checks passed
