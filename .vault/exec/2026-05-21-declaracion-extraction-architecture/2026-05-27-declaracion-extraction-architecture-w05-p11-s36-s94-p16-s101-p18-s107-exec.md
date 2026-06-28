---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S36'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-22-declaracion-extraction-architecture-W05-P11-S36]]'
  - '[[2026-05-26-declaracion-extraction-architecture-W05-P18-S122]]'
---

# W05.P11.S36 + S94 + W05.P16.S101 + W05.P18.S107 - M036 grounding, fixture, round-trip

## Outcome

M036 declaracion_pdf profile PARTIALLY GROUNDED. `decl.event-kind` pattern FIXED from
AEAT-published Anexo 3 instructions. `decl.vigencia-2025` removed from extraction targets
(informational registry marker, no corresponding printed-form field). Round-trip test passing.

## URL fetch results (2026-05-27)

- URL 3 (Anexo 3 hub): 9911 chars fetched — navigation hub only, subpages contain field content
- URL 4 (paper presentation): 31002 chars fetched — describes electronic-form paper-print workflow, no printed-form field labels
- Subpage `cumplimentacion-modelo/pagina-1.html`: 16836 chars fetched — CRITICAL CONTENT
- URL 2 (DR036 v43 XLSX): not fetched — corpus already has DR036v43 as `01-036-diseno-de-registro...xlsx` (source_url matches)
- URL 1 (Diseños index): confirmed DR036v43.xlsx present at expected URL

## Per-pattern verdicts

### decl.event-kind — FIXED

Previous pattern: `'Tipo\s+de\s+declaraci[oó]n\s+censal'`
Finding: "Tipo de declaración censal" does NOT appear anywhere in AEAT-published M036 instructions.
This was a self-reference to the casilla registry label field, not a printed-form label.

AEAT-published evidence from pagina-1.html (h3 element, verbatim):
  `<h3>Causas de presentación de la declaración</h3>`
  Table thead: TIPO | CASILLA | CAUSA DE PRESENTACIÓN
  TIPO column values: ALTA / MODIFICACIÓN / BAJA

New pattern: `'Causas\s+de\s+presentaci[oó]n\s+de\s+la\s+declaraci[oó]n'`
Status: CONFIRMED from AEAT-published `instrucciones-cumplimentacion-pagina-1.html`

### decl.vigencia-2025 — AMBIGUOUS / REMOVED from extraction targets

Previous pattern: `'Vigencia\s+normativa\s+desde'`
Finding: "Vigencia" appears ZERO times across all 5+ AEAT M036 pages fetched.
This phrase originates from the diseño de registro header ("Vigencia normativa desde
3 de febrero de 2025"), not from any printed-form field label.
Casilla is input_kind="informational" — it records the registry validity date, not
a taxpayer-entered or printed field.
Decision: remove from target_casillas; retain casilla in registry as validity marker.

## Changes made

- `src/aeat/_data/registry/aeat/modelos/036.toml`:
  - `decl.event-kind` label_pattern: `Tipo\s+de\s+declaraci[oó]n\s+censal` → `Causas\s+de\s+presentaci[oó]n\s+de\s+la\s+declaraci[oó]n`
  - `decl.vigencia-2025` removed from `target_casillas`
  - `verification_expectations.computed_casillas`: `["decl.event-kind", "decl.vigencia-2025"]` → `["decl.event-kind"]`
  - `period_selector.periods` and `filing_schedules.periods`: `["alta","modificacion","baja"]` → `["ALTA","MODIFICACION","BAJA"]` (parser normalises to uppercase)
  - `provisional_pending_specimen` removed (was `true`); `corpus_round_trip_verified = true` added

- `src/aeat/tests/fixtures/justificantes/_generate.py`: `_Modelo036Fixture` + `_draw_modelo_036` + generation loop added

- `src/aeat/tests/fixtures/justificantes/036/2025-0A.pdf`: synthesized fixture using AEAT-published heading label

- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`: `test_parser_extracts_modelo_036_synthetic_fixture_targets` added

- `src/aeat/domain/calculations/registry/test_provisional_specimen_gate.py`: `test_gate_fires_via_production_path` updated from M036 (which now has fixture + rt_verified) to M184 (no fixture, provisional=True)

- Corpus files added to `src/aeat/_data/corpus/aeat_official/instructions/modelo_036/files/`:
  - `anexo-03-instrucciones-modelo-036.html`
  - `presentacion-papel-modelo-036.html`
  - `instrucciones-cumplimentacion-pagina-1.html` (primary grounding source)

## Test results

- `test_parser_extracts_modelo_036_synthetic_fixture_targets`: PASSED
- `test_provisional_specimen_gate.py` (7 tests): all PASSED
- `test_corpus_round_trip_gate.py` (4 tests): all PASSED
- `test_modelo_parity_coverage.py` (1 test): PASSED

## Bottom line

M036 transitions PROVISIONAL → PARTIALLY GROUNDED:
- `decl.event-kind`: FIXED — grounded from AEAT Anexo 3 instructions PAGINA 1 h3 heading
- `decl.vigencia-2025`: REMOVED from extraction targets — not a printed-form field
- Fixture authored, round-trip test passing, `corpus_round_trip_verified = true`
