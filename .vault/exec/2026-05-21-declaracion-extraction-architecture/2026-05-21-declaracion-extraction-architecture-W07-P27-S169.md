---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: 2026-05-26
modified: '2026-05-26'
step_id: "S169"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W07.P27.S169

Ground M840 declaracion_pdf label_patterns against AEAT corpus form PDF; fix provisional patterns to corpus-published labels; author sanitized synthetic fixture; add corpus_round_trip_verified=true; add round-trip test asserting both casillas extract.

## Corpus survey

File: `src/aeat/_data/corpus/aeat_official/forms/modelo_840/files/01-840-modelo-declaracion-iae-alta-variacion-baja-pdf.pdf`

pdfplumber extracts the following from Apartado II (page 1):

```
14Ejercicio:
15Declaración de:
Alta  Variación
...
```

The casilla-number prefix is fused to the label text in the pdfplumber output. Values are in detached fill-in boxes, not on the label line.

## Verdict per pattern

- `decl.tipo-declaracion`: **FIXED** — PROVISIONAL pattern `Tipo\s+de\s+declaraci[oó]n\s+\(alta\s*/\s*variaci[oó]n\s*/\s*baja\)` does not appear anywhere on the form. AEAT-published label is `15Declaración de:`. New pattern: `15\s*Declaraci[oó]n\s+de:`
- `decl.ejercicio`: **FIXED** — PROVISIONAL pattern `Ejercicio\s+fiscal\s+al\s+que\s+se\s+refiere\s+la\s+declaraci[oó]n` does not appear on the form. AEAT-published label is `14Ejercicio:`. New pattern: `14\s*Ejercicio:`

## Synthetic fixture

Path: `src/aeat/tests/fixtures/justificantes/840/2024-0A.pdf`

Labels derived from corpus-published form layout. Sanitized values: `tax_id=Y0000001S`, `ejercicio=2024`, `tipo_declaracion=Alta`. Generator entry added to `_generate.py` as `_Modelo840Fixture` + `_draw_modelo_840`.

## Profile flag state

- `provisional_pending_specimen`: removed (was `true`)
- `corpus_round_trip_verified`: set to `true`

## Round-trip test

`test_parser_extracts_modelo_840_synthetic_fixture_targets` in `test_parser_boundary.py` — asserts both casillas present, `decl.ejercicio == Decimal("2024")`, `decl.tipo-declaracion` is non-None.

## Test results

113 tests collected; all passed. ruff clean.

## Commit

`a3468fc0f` — `#42 M840: ground declaracion_pdf label_patterns against AEAT corpus form PDF`
