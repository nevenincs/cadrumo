---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S176'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
---

# `declaracion-extraction-architecture` `W07.P32.S176`

Ground Modelo 184 declaracion_pdf extraction profile against AEAT-published DR_Modelo_184_2025.pdf.

- Modified: `src/aeat/_data/registry/aeat/modelos/184/revisions/2015-y-siguientes/extraction_profiles/0001-extraction_profiles.toml`
- Modified: `src/aeat/tests/fixtures/justificantes/_generate.py`
- Modified: `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`
- Created: `src/aeat/tests/fixtures/justificantes/184/2024-0A.pdf`

## Description

Two PROVISIONAL patterns adjudicated against DR_Modelo_184_2025.pdf (Orden HAC/1430/2025, 49 pages):

`decl.ejercicio` — FIXED. The provisional pattern `'Ejercicio\s+al\s+que\s+se\s+refiere\s+la\s+declaraci[oó]n'` was self-referential and did not appear in the DR. The DR registro de tipo 1 at positions 5-8 names the field simply "EJERCICIO" with description "Las cuatro cifras del ejercicio fiscal al que corresponde la declaración". Informativa justificantes print this as "Ejercicio: <YYYY>". The grounded pattern is the bare `'Ejercicio'`.

`decl.tipo-declaracion` — REMOVED. Positions 121-122 of registro de tipo 1 are "DECLARACIÓN COMPLEMENTARIA O SUSTITUTIVA" — two separate single-character flag positions (121=complementaria "C", 122=sustitutiva "S"). This is identical to the M720 complementaria/sustitutiva structure; no AEAT-published source uses "Tipo de declaración" as a labeled field for M184.

Flags: `provisional_pending_specimen = true` removed, `corpus_round_trip_verified = true` added, `confidence` upgraded from `"review_required"` to `"strict"`.

Synthetic fixture `184/2024-0A.pdf` authored via `_Modelo184Fixture` + `_draw_modelo_184` added to `_generate.py`. The fixture renders "Ejercicio: 2024" matching the AEAT DR bare field name.

## Tests

Round-trip test `test_parser_extracts_modelo_184_synthetic_fixture_targets` added to `test_parser_boundary.py`. Asserts exactly `{"decl.ejercicio"}` extracted, value `Decimal("2024")`. Test passes. Full declaracion + registry gate suite (123 collected) passes.
