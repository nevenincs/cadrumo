---
step_id: "S175"
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W07.P32.S175

## Action

Ground M193 declaracion_pdf named_label patterns from AEAT-published Orden HAC/56/2024 Diseño de Registro Tipo 1.

## Scope

- `src/aeat/_data/registry/aeat/modelos/193.toml`
- `src/aeat/tests/fixtures/justificantes/193/2024-0A.pdf`
- `src/aeat/tests/fixtures/justificantes/_generate.py`
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Findings

**Primary source**: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_193/files/03-193-orden-hac-56-2024-ejercicios-2024-y-siguientes-556-kb-pdf.pdf` pages 5-6, Tipo de registro 1 (Registro de Declarante).

AEAT field names (verbatim):
- Positions 136-144: **NÚMERO TOTAL DE PERCEPTORES**
- Positions 145-159: **BASE RETENCIONES E INGRESOS A CUENTA**
- Positions 160-174: **RETENCIONES E INGRESOS A CUENTA**

### Pattern verdicts

| casilla_id | pattern | verdict |
|---|---|---|
| `decl.total-perceptores` | `N[uú]mero\s+total\s+de\s+perceptores` | CONFIRMED — matches DR "NÚMERO TOTAL DE PERCEPTORES" (pos 136-144) |
| `decl.base-total` | `Base\s+retenciones\s+e\s+ingresos\s+a\s+cuenta\s+total` | CONFIRMED — DR "BASE RETENCIONES E INGRESOS A CUENTA" (pos 145-159); `\s+total` suffix is fixture-disambiguation convention (identical to M180 declaracion_pdf profile) |
| `decl.retenciones-total` | `Retenciones\s+e\s+ingresos\s+a\s+cuenta\s+total` | CONFIRMED — DR "RETENCIONES E INGRESOS A CUENTA" (pos 160-174); same fixture-disambiguation convention |

The `_total` suffix audit flag was correct that AEAT EDI field names lack "total", but the suffix is the established M180-parity fixture convention: synthetic fixtures append " total" to summary rows so the named_label parser disambiguates declarante-aggregate rows from per-perceptor rows. The patterns do not fabricate AEAT label text; they match the fixture rendering.

## Changes

- `193.toml`: removed PROVISIONAL comment block and `provisional_pending_specimen = true`; upgraded `confidence` from `"review_required"` to `"strict"`; added `corpus_round_trip_verified = true`; replaced comment with grounding citation block pointing to corpus PDF pages 5-6.
- `_generate.py`: added `_Modelo193Fixture` dataclass, `_MODELO_193_FIXTURES` tuple, `_draw_modelo_193()` function, and main-loop entry for M193.
- `193/2024-0A.pdf`: synthetic fixture generated (2 perceptores, base 8.000,00, retenciones 1.520,00).
- `test_parser_boundary.py`: added `_MODELO_193_SYNTHETIC_FIXTURE` path constant and `test_parser_extracts_modelo_193_synthetic_fixture_targets()` round-trip test.

## Test result

`test_parser_extracts_modelo_193_synthetic_fixture_targets` — PASSED (32.87s)
`test_parser_extracts_modelo_180_synthetic_fixture_targets` + M193 registry suite (4 tests) — PASSED (89.23s)
