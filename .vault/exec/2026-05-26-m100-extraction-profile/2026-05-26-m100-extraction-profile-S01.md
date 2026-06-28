---
step_id: "S01"
tags:
  - "#exec"
  - "#m100-extraction-profile"
date: 2026-05-26
modified: '2026-05-26'
related:
  - '[[2026-05-22-restructure-execution-P01-S01]]'
---

# M100 IRPF declaracion_pdf extraction profile — chunk 1

## Objective

Author the first chunk of the M100 declaracion_pdf extraction profile covering
cuota-chain closure casillas (9 of ~20 total anchors needed for full M100 coverage).
Register extractor application_links for revisions 2021, 2022, 2023.
Deliver non-tautological round-trip tests against the sanitised corpus PDFs.

## Artefacts produced

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/application_links/0010-modelo-100-2021-extractor.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/application_links/0010-modelo-100-2022-extractor.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/application_links/0011-modelo-100-2023-extractor.toml`
- `src/aeat/adapters/inbound/declaracion/__init__.py` (export `TemplateNotDetectedError`)
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py` (3 new round-trip tests)

## Casillas covered

| Casilla | Label (abbreviated)                          | Pattern anchor         |
|---------|----------------------------------------------|------------------------|
| 0505    | Base liquidable general sometida a gravamen  | `\s*\[` suffix         |
| 0545    | Cuota integra estatal                        | `\s*\[` suffix         |
| 0546    | Cuota integra autonomica                     | `\s*\[` suffix         |
| 0585    | Cuota liquida estatal incrementada           | plain suffix           |
| 0586    | Cuota liquida autonomica incrementada        | `\s*\[` suffix (excl. CCAA row 0671) |
| 0587    | Cuota liquida incrementada total             | plain suffix           |
| 0595    | Cuota resultante de la autoliquidacion       | plain suffix           |
| 0610    | Cuota diferencial                            | `\s*\[` suffix         |
| 0670    | Resultado de la declaracion                  | negative lookahead for "complementaria" |

## Deferred casillas

- 0570 / 0571 (cuota liquida estatal/autonomica pre-incrementada): both body and summary
  pages carry identical short labels in the 2023 corpus with no formula-bracket anchor
  available. A follow-up chunk will resolve this with a revised disambiguation strategy.

## Test results

All 3 parametrised round-trip tests pass:
- `test_parser_extracts_modelo_100_profile_targets_from_corpus[2021-0A-2021]` PASSED
- `test_parser_extracts_modelo_100_profile_targets_from_corpus[2022-0A-2022]` PASSED
- `test_parser_extracts_modelo_100_profile_targets_from_corpus[2023-0A-2023]` PASSED

## Pre-existing issues noted (not introduced by this step)

- M303 layout conflict (`303.toml` vs `303/` directory) blocks `load_registry_tree` for the
  full modelos scan. Not in scope of this step.
- M100 global catalogue gap: `ley-35-2006` legal refs and `aeat-dr-100-*` source refs are
  absent from the shared catalogue. This is pre-existing across all M100 application links
  and was present before this step.
- `test_parser_extracts_modelo_303_targets_from_real_redacted_declaration_copy` fails due to
  `casilla_id` max-length constraint on `iva.compensacion-pendiente-periodos-anteriores`.
  Pre-existing, not introduced here.

## Commit

`cfe620d6e` — M100 IRPF: declaracion_pdf extraction profile chunk 1 - cuota-chain closure casillas (2021-2023)
