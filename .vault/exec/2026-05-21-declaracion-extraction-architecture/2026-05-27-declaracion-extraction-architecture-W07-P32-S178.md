---
step_id: S178
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W07.P32.S178

Ground Modelo 232 (both revisions) against AEAT-published Diseño de Registro.

## Corpus authority

Source: AEAT-published Diseño de Registro XLSX files (both carry identical DR23201):
- `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_232/files/01-232-orden-hfp-816-2017-ejercicio-2016-y-siguientes-actualizado-15-01-2020-145-kb-xlsx.xlsx`
- `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_232/files/02-232-orden-hfp-816-2017-ejercicios-2016-2017-146-kb-xlsx.xlsx`

DR field descriptions (verbatim, openpyxl extraction):
- DR23200 row 9: `"Ejercicio de devengo (EEEE)"`
- DR23201 row 17: `"2.Devengo - Tipo de Ejercicio"`
- DR23201 row 20: `"2.Devengo - C.N.A.E. actividad principal"`

## Pattern verdicts (both revisions identical)

| casilla_id | old pattern | verdict | new pattern |
|---|---|---|---|
| `decl.ejercicio` | `Ejercicio\s+de\s+devengo` | CONFIRMED — DR23200 row 9 | unchanged |
| `decl.tipo-ejercicio` | `Tipo\s+de\s+ejercicio` | CONFIRMED — DR23201 row 17, case-insensitive | unchanged |
| `decl.cnae` | `C\.N\.A\.E\.?\s+de\s+la\s+actividad\s+principal` | FIXED — DR23201 row 20 reads "C.N.A.E. actividad principal" with no "de la" connector | `C\.N\.A\.E\.?\s+actividad\s+principal` |

## Changes

- Both revision TOMLs: removed `provisional_pending_specimen = true`; added `corpus_round_trip_verified = true`; replaced AMBIGUOUS comment block with DR grounding attribution; fixed `decl.cnae` pattern.
- `_generate.py`: added `_Modelo232Fixture` dataclass, `_MODELO_232_FIXTURES` tuple (2016-0A and 2018-0A), and `_draw_modelo_232` render function using verbatim DR label text.
- Generated `src/aeat/tests/fixtures/justificantes/232/2016-0A.pdf` and `232/2018-0A.pdf`.
- `test_parser_boundary.py`: added `test_parser_extracts_modelo_232_synthetic_fixture_targets` parametrized over both revisions; asserts all three casillas present, `decl.ejercicio` as `Decimal(year)`, `decl.cnae` as `"6201"`.

## Test result

97/97 parser boundary tests pass. 2 new M232 round-trip tests (2016 and 2018 revisions) green.

## Verdict

M232 — GROUNDED (both revisions). `corpus_round_trip_verified = true`.
