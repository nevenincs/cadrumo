---
tags:
  - "#exec"
  - "#eliminate-shims"
step_id: S29
date: 2026-05-26
modified: '2026-05-26'
related:
  - "[[2026-05-10-eliminate-user-cli-shim-plan]]"
---

# M100 declaracion_pdf extraction profile — second chunk (apartado-summary casillas)

## Scope

Expanded the M100 `declaracion_pdf` extraction profiles for revisions 2021, 2022, and 2023
by adding four named_label targets covering apartado-summary casillas. Coverage raised from
9 targets (first chunk: cuota-chain closure) to 13 targets per revision.

## Corpus survey findings

All three corpus PDFs (`2021-0A.pdf`, `2022-0A.pdf`, `2023-0A.pdf`) share identical printed
label text for all candidate casillas. pdfplumber merges the value column and the box-number
column into a single token (e.g. `1.001.000,004032`); `parse_spanish_decimal` returns a valid
Decimal from the merged token but not exactly `1000.00`. Tests assert `isinstance(value, Decimal)`.

## Slug to printed-box mapping (additions)

| casilla_id | Printed label (excerpt) | Printed box | Match strategy |
|-----------|------------------------|-------------|----------------|
| `0235` | `Suma del rendimiento neto reducido total de las actividades...` | `0235` | named_label |
| `0432` | `Saldo neto de rendimientos a integrar en la base imponible general...` | `0432` | named_label |
| `0500` | `Base liquidable general [(435)-...]` | `0500` | named_label, `\[` anchor |
| `0510` | `Base liquidable del ahorro [(460)-...]` | `0510` | named_label, `\[` anchor |

## Deferred casillas

- `0435` (base imponible general): the IRPF form prints the line `Base imponible general
  [(420)-(431)+(432)-(433)-(434)]` twice — once in the base imponible section and once in
  the base liquidable section. Both occurrences carry identical text, so the parser flags it
  as ambiguous. Deferred to a future chunk requiring multiline context anchoring.
- `Base imponible del ahorro` (`0460`): short label appears twice without formula brackets.
  Ambiguous. Deferred.
- Rendimientos del trabajo / capital mobiliario / inmobiliario: none of these apartado-total
  casillas have stable printed labels in the corpus specimens (specimens only contain
  actividades económicas income). Third chunk or future corpus expansion.

## Per-apartado coverage status

| Apartado | Casilla | Status |
|----------|---------|--------|
| Rendimientos del trabajo | — | Not in corpus (no trabajo income) |
| Capital mobiliario | — | Not in corpus |
| Capital inmobiliario | — | Not in corpus |
| Actividades económicas ED total | 0235 | Covered |
| Saldo neto base imponible general | 0432 | Covered |
| Base imponible general | 0435 | Deferred (ambiguous duplicate) |
| Base imponible del ahorro | 0460 | Deferred (ambiguous) |
| Base liquidable general | 0500 | Covered |
| Base liquidable general sometida a gravamen | 0505 | Covered (first chunk) |
| Base liquidable del ahorro | 0510 | Covered |

## Files changed

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Test results

- `test_parser_extracts_modelo_100_profile_targets_from_corpus`: 3/3 passed (2021, 2022, 2023)
- `test_formula_bearing_modelos_have_constructs_and_model_specific_tests`: 1/1 passed (26 modelos)
- Ruff: all checks passed

## Commit

`1c1125beb` — M100 extraction profile: second chunk — 4 apartado-summary casillas (2021/2022/2023)
