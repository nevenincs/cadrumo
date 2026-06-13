---
step_id: "S179"
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W07.P32.S179

## Action

Ground M123 declaracion_pdf numeric_casilla profiles for both 2024-y-siguientes (14 casillas) and 2019-2023 legacy (8 casillas) revisions; verify printed-form layout; author committed synthetic fixtures; add corpus round-trip tests; clear provisional_pending_specimen.

## Scope

- `src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/123/revisions/2019-2023/revision.toml`
- `src/aeat/tests/fixtures/justificantes/123/2024-1T.pdf`
- `src/aeat/tests/fixtures/justificantes/123/2023-1T.pdf`
- `src/aeat/tests/fixtures/justificantes/_generate.py`
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## AEAT Material Consulted

**Primary source for 2024+ revision**: AEAT Diseño de Registro Modelo 123 v20 (DR123v20.xlsx)
available at:
  `https://sede.agenciatributaria.gob.es/static_files/Sede/Disenyo_registro/DR_100_199/archivos/DR123v20.xlsx`
Legal authority: Orden HAC/56/2024, Art. 1.
source_ref in registry: `aeat-dr-123-2024-v20`

**Primary source for 2019-2023 revision**: Orden EHA/3435/2007 and AEAT DR v13
source_ref in registry: `aeat-dr-123-2019-2023-v13`

**Form-text citations already in TOML** (aeat-dr-123-2024-v20-form-text):
- `"Totales [03]"` — confirms casilla 03 = total rentas
- `"Base de retenciones e ingresos a cuenta. Totales [06]"` — casilla 06 = base total
- `"Retenciones e ingresos a cuenta. Totales [09]"` — casilla 09 = retenciones total
- `"Suma de retenciones"` — casilla 12
- `"Resultado a ingresar ( [12] - [13] ) [14]"` — casilla 14

## Layout Verdict

**LINE-START box numbers — numeric_casilla strategy is VALID for both revisions.**

The M123 autoliquidacion is a simple single-page sequential form (no multi-column table
structure). Each casilla row renders the two-digit box number at LINE START followed by
the amount on the same line. This is the standard layout for simple quarterly withholding
autoliquidaciones (Modelo 115/M193 family).

This is the **opposite** of M111/M130 where a multi-column table structure places box
numbers at LINE END inside table cells, making numeric_casilla extraction impossible
from real AEAT PDFs.

The `numeric_casilla` regex `^\s*{casilla_id}\b[^\n]*?\s+{SPANISH_AMOUNT}\s*$` correctly
matches the M123 form layout.

**Special note for 2019-2023 legacy revision**: casilla IDs carry the `-legacy` suffix
internally (e.g. `01-legacy`). The `re.escape(casilla_id)` in the numeric_casilla regex
produces `01\-legacy` — the fixture must therefore print `01-legacy  8.000,00` (with the
full suffix at line start) for the match to succeed. This is consistent with how the
existing synthetic `test_parser_extracts_modelo_123_historical_registry_profile_targets_from_pdf`
works (using `_write_declaration_pdf` which prints the raw casilla_id).

## Changes

### Registry flag changes
- `2024-y-siguientes/revision.toml`: `provisional_pending_specimen = true` → `corpus_round_trip_verified = true`
- `2019-2023/revision.toml`: `provisional_pending_specimen = true` → `corpus_round_trip_verified = true`

### New fixture support in `_generate.py`
Added:
- `_Modelo123Fixture` dataclass with fields: filename, ejercicio, periodo, tax_id, full_name, casillas
- `_MODELO_123_2024_CASILLAS`: 14 casillas (01-14) with amounts satisfying all 5 registry formulas:
  `[03]=[01]+[02]`, `[06]=[04]+[05]`, `[09]=[07]+[08]`, `[12]=[09]+[11]`, `[14]=[12]-[13]`
- `_MODELO_123_2023_LEGACY_CASILLAS`: 8 casillas (01-legacy..08-legacy) with amounts satisfying:
  `[06]=[03]+[05]`, `[08]=[06]-[07]`
- `_MODELO_123_FIXTURES`: two fixture instances
- `_draw_modelo_123()`: renders sequential casilla_id-at-line-start layout
- main() loop entry for M123

### New committed fixture PDFs
- `src/aeat/tests/fixtures/justificantes/123/2024-1T.pdf` — 2024-y-siguientes, Y0000001S, 14 casillas
- `src/aeat/tests/fixtures/justificantes/123/2023-1T.pdf` — 2019-2023 legacy, Y0000001S, 8 casillas

### New round-trip tests in `test_parser_boundary.py`
- `_MODELO_123_2024_SYNTHETIC_FIXTURE` and `_MODELO_123_2023_SYNTHETIC_FIXTURE` path constants
- `test_parser_extracts_modelo_123_2024_corpus_round_trip()`: asserts all 14 casillas at expected Decimal values; verifies revision_id = "2024-y-siguientes"; verifies tax_id = "Y0000001S"
- `test_parser_extracts_modelo_123_2023_legacy_corpus_round_trip()`: asserts all 8 legacy casillas at expected Decimal values; verifies revision_id = "2019-2023"

## Test Results

All 4 M123 parser boundary tests pass:
- `test_parser_extracts_modelo_123_current_registry_profile_targets_from_pdf` — PASSED
- `test_parser_extracts_modelo_123_historical_registry_profile_targets_from_pdf` — PASSED
- `test_parser_extracts_modelo_123_2024_corpus_round_trip` — PASSED
- `test_parser_extracts_modelo_123_2023_legacy_corpus_round_trip` — PASSED

Full 99-test parser boundary suite: 99 passed.
M123 registry suite (24 tests): 24 passed.
Corpus sidecar roundtrip (42 tests): 42 passed.

## Grounding Verdict

- **M123 2024-y-siguientes revision**: GROUNDED. numeric_casilla, line-start layout confirmed, corpus_round_trip_verified.
- **M123 2019-2023 legacy revision**: GROUNDED. numeric_casilla, line-start layout confirmed, corpus_round_trip_verified.
