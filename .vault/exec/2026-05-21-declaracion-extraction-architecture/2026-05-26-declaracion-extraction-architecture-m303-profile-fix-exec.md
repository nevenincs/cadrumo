---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S22-reopened'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# declaracion-extraction-architecture M303 profile fix (reopened #22)

Re-opens #22 after W03 executor wrongly concluded BLOCKED. Inspected the 15
corpus PDFs directly and confirmed they are hybrid documents: AEAT receipt
header on page 0, full printed Modelo 303 declaración form on pages 1+. The
printed form includes apartados, box numbers, labels, and declared values —
exactly the structure the W02 `named_label` primitive was built for.

## Corpus inspection findings

PDFs `2021-2T.pdf` through `2024-4T.pdf` in
`src/aeat/tests/fixtures/justificantes/303/`:

- **2021-2T through 2022-4T (7 PDFs)**: fail on tax-id extraction — the
  sanitiser placed `NIF Presentador:` and `Y0000001S` on separate lines in
  these specimens; the parser regex requires them on the same line. This is a
  corpus-layout artefact, NOT a structural absence of the printed form. The
  printed M303 declaración form is fully present on page 1 of every specimen.

- **2023-1T through 2024-4T (8 PDFs)**: parse successfully with the profile.
  `NIF Presentador: Y0000001S` appears on one line in these specimens and the
  tax-id regex matches.

The form labels are consistent across years. The 2024-3T/4T form revision
extended the autoliquidación result formula from `(66+77-78+68)` to
`(66+77-78+68+108)` — the existing `iva.resultado` pattern was hard-coded to
the older formula and therefore missed the 2024-3T/4T specimens.

## Semantic-slug → printed-box mapping (new or changed entries)

| Slug / casilla_id                         | Form box | Printed label (anchor)                                               |
|-------------------------------------------|----------|----------------------------------------------------------------------|
| `27`                                      | 27       | Total cuota devengada (…)                                            |
| `45`                                      | 45       | Total a deducir (…)                                                  |
| `iva.resultado-regimen-general`           | 46       | Resultado régimen general (27 - 45)                                  |
| `64`                                      | 64       | Suma de resultados (46 + 58 + 76)                                    |
| `66`                                      | 66       | Atribuible a la Administración del Estado                            |
| `iva.compensacion-pendiente-periodos-anteriores` | 110 | Cuotas a compensar pendientes de periodos anteriores              |
| `iva.compensacion-aplicada-periodo` (**NEW**) | 78  | Cuotas a compensar de periodos anteriores aplicadas en este periodo  |
| `iva.compensacion-pendiente-periodos-posteriores` | 87 | Cuotas a compensar de periodos previos pendientes … (110 - 78)   |
| `iva.resultado` (**FIXED**)               | 69       | Resultado de la autoliquidación (66[^)]*)                            |
| `71`                                      | 71       | Resultado (69 - 70 + 109)                                            |

## Changes made

**`src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`**

- Added `iva.compensacion-aplicada-periodo` (box 78) `named_label` target;
  anchors on `Cuotas\s+a\s+compensar\s+de\s+periodos\s+anteriores\s+aplicadas\s+en\s+este\s+periodo`.
- Fixed `iva.resultado` label_pattern: changed `\(66\s*\+\s*77\s*-\s*78\s*\+\s*68\)` to
  `\(66[^\)]*\)` to match both the 2023 form `(66+77-78+68)` and the 2024 form
  `(66+77-78+68+108)` variants.
- Profile now targets 10 casillas (was 9).

**`src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`**

- Updated existing `test_parser_extracts_modelo_303_targets_from_real_redacted_declaration_copy`
  to assert the new 10-casilla key set and per-casilla values grounded in the
  printed form text.
- Added `test_parser_extracts_modelo_303_profile_targets_from_corpus` (8-specimen
  parametrised test covering 2023-1T through 2024-4T). Ground truth for 7 stable
  casillas derived from direct PDF text inspection (`1.000,00` confirmed adjacent to
  label in every specimen). Three compensation casillas (78, 87, 110) are asserted
  as valid `Decimal` only due to sanitiser placement variation across specimens.

## Test results

```
src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py .
src/aeat/adapters/inbound/declaracion/test_parser_boundary.py ..........
src/aeat/adapters/inbound/declaracion/test_parser_boundary.py .........
36 passed
```

All 26 modelos load valid. 8/15 corpus PDFs parse successfully (the 7 2021-2022
specimens fail on tax-id extraction — a pre-existing parser limitation unrelated
to the profile). ruff clean.

## Commit

`291bdf3b2` — #22 M303 declaracion_pdf: add casilla 78 + fix iva.resultado for 2024 form variant
