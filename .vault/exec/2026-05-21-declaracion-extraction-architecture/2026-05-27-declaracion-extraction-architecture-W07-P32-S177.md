---
step_id: "S177"
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W07.P32.S177

## Action

Ground M347 declaracion_pdf: fix decl.ejercicio pattern to Ejercicio: (AEAT DR field EJERCICIO positions 5-8 Orden HAC/1431/2025), remove decl.tipo-declaracion (positions 121-122 are two separate single-char flags identical to M720), flip provisional_pending_specimen to corpus_round_trip_verified, author synthetic fixture 347/2024-0A.pdf and round-trip test.

## Scope

- `src/aeat/_data/registry/aeat/modelos/347.toml`
- `src/aeat/tests/fixtures/justificantes/347/2024-0A.pdf`
- `src/aeat/tests/fixtures/justificantes/_generate.py`
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Findings

**Primary source**: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_347/files/01-347-ejercicio-2025-y-siguientes-modificados-por-orden-hac-1431-2025-de-3-de-diciembre-332-kb.pdf`
page 1, TIPO DE REGISTRO 1, positions 5-8.

### decl.ejercicio

AEAT field at positions 5-8: **EJERCICIO** — "Las cuatro cifras del ejercicio fiscal al que corresponde la declaración."

The PROVISIONAL pattern `'Ejercicio\s+al\s+que\s+se\s+refiere\s+la\s+declaraci[oó]n'` was a self-reference to the registry casilla label. It does not appear in any AEAT-published M347 printed-form text. The corpus DR field name is simply "EJERCICIO". The short-form label `"Ejercicio:"` is used consistently across all annual informative model justificantes in the corpus (M349, M180, M369).

Verdict: **FIXED** — pattern changed from PROVISIONAL self-reference to `'Ejercicio:'` (corpus-grounded short form).

### decl.tipo-declaracion

M347 record-type-1 positions 121-122 are **two separate single-character flag fields**:
- Position 121: `"C"` if declaración complementaria
- Position 122: `"S"` if declaración sustitutiva

This is structurally identical to M720 positions 121-122 (same two-flag layout, same Orden pattern). These flags are not a single `label: value` pair; they cannot be extracted by the named_label strategy from a printed-form PDF.

Verdict: **REMOVED** from target_casillas — same reasoning as M720 (two separate flags, not a label+value pair). The `decl.tipo-declaracion` casilla definition remains in the registry as a valid casilla; it is absent from target_casillas only.

### Extraction profile flag state

- `provisional_pending_specimen = true` → removed (field defaults to false)
- `corpus_round_trip_verified = true` → set

## Changes

- `347.toml`: replaced PROVISIONAL comment block with corpus-grounding citation; changed `decl.ejercicio` label_pattern from `'Ejercicio\s+al\s+que\s+se\s+refiere\s+la\s+declaraci[oó]n'` to `'Ejercicio:'`; removed `decl.tipo-declaracion` from target_casillas; set `corpus_round_trip_verified = true`; removed `provisional_pending_specimen = true`.
- `_generate.py`: added `_Modelo347Fixture` dataclass, `_MODELO_347_FIXTURES` tuple, `_draw_modelo_347()` function, and main-loop entry.
- `347/2024-0A.pdf`: synthetic fixture generated (ejercicio=2024, NIF=Y0000001S).
- `test_parser_boundary.py`: added `_MODELO_347_SYNTHETIC_FIXTURE` path constant and `test_parser_extracts_modelo_347_synthetic_fixture_targets()` round-trip test.

## Test result

`test_parser_extracts_modelo_347_synthetic_fixture_targets` — PASSED (37.08s)
Full `test_parser_boundary.py` suite (95 tests) — PASSED (669.97s, 0 failures)
