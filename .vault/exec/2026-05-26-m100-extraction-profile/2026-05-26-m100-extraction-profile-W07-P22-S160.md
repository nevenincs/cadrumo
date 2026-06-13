---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
step_id: W07.P22.S160
date: 2026-05-26
modified: '2026-05-26'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-26-m100-extraction-profile-S29]]"
---

# M100 declaracion_pdf extraction profile — third chunk (actividades-económicas ED detail)

## Scope

Expanded the M100 `declaracion_pdf` extraction profiles for revisions 2021, 2022, and 2023
by adding six named_label targets covering the actividades económicas estimación directa
computation pipeline. Coverage raised from 13 targets (second chunk) to 19 targets per revision.

## Corpus survey findings

All three corpus PDFs (`2021-0A.pdf`, `2022-0A.pdf`, `2023-0A.pdf`) share identical printed
label text for all six candidate casillas. Each label appears exactly once per corpus document
(confirmed by full text-extraction inspection). pdfplumber merges the value column and the
box-number column into a single token; `parse_spanish_decimal` returns a valid Decimal.

Key disambiguation notes:
- `0224` (rendimiento neto) and `0226` (rendimiento neto reducido) share a label prefix.
  `0224` anchors on `Rendimiento\s+neto\s+\[` (bracket immediately follows "neto");
  `0226` anchors on `Rendimiento\s+neto\s+reducido\s*\[` (word "reducido" present). Safe.
- `0231` (suma de rendimientos netos reducidos) vs `0235` (suma del rendimiento neto reducido
  total): patterns differ at "de rendimientos netos" vs "del rendimiento neto reducido total".
- `0218` label ends with period ("Suma de gastos fiscalmente deducibles."); pattern uses
  `Suma\s+de\s+gastos\s+fiscalmente\s+deducibles` (no period required, not ambiguous).

## Slug to printed-box mapping (additions)

| casilla_id | Printed label (excerpt) | Stability | Match strategy |
|-----------|------------------------|-----------|----------------|
| `0180` | `Total ingresos computables [(171)a(179)].` | 2021/2022/2023 | named_label, `\[` anchor |
| `0218` | `Suma de gastos fiscalmente deducibles.` | 2021/2022/2023 | named_label |
| `0223` | `Total gastos deducibles, modalidad simplificada [(218)+(222)].` | 2021/2022/2023 | named_label |
| `0224` | `Rendimiento neto [(180)-(220) ó (180)-(223)].` | 2021/2022/2023 | named_label, `\[` anchor |
| `0226` | `Rendimiento neto reducido [(224)-(225)].` | 2021/2022/2023 | named_label, `\[` anchor |
| `0231` | `Suma de rendimientos netos reducidos` | 2021/2022/2023 | named_label |

Registry cross-reference confirmed for all three revision years:
2021 — files `0171-0180.toml`, `0206-0218.toml`, `0211-0223.toml`, `0001-0224.toml`,
`0213-0226.toml`, `0218-0231.toml`. Casilla IDs are stable across 2021/2022/2023.

## Deferred casillas

- `0460` (base imponible del ahorro): short label `Base imponible del ahorro` appears twice
  per corpus (once in base imponible section, once in base liquidable section) without a
  formula bracket to distinguish. Ambiguous. Deferred.
- `0435` (base imponible general): same dual-occurrence problem. Deferred (pre-existing).
- `0171` (ingresos de explotación): single activity in corpus but label is not uniquely
  anchored — "Ingresos de explotación." could theoretically repeat with multiple activities.
  Also its printed value is adjacent to casilla 1071 (pdfplumber merge), not 0171/0180.
  Deferred pending multi-activity corpus.
- Mínimo personal y familiar casillas (0511/0512/0519/0520 etc.): the printed labels use
  different text than the registry casilla labels and the corpus shows 5 "Mínimo personal y
  familiar..." lines; disambiguating requires the specific sub-label variant ("para calcular el
  gravamen estatal" vs "de la base liquidable general para calcular..."). These could be
  addressed in a future chunk.

## Full per-apartado coverage after this chunk

| Apartado | Casilla | Status |
|----------|---------|--------|
| Actividades económicas ED — ingresos computables | 0180 | Covered (new) |
| Actividades económicas ED — gastos deducibles previo | 0218 | Covered (new) |
| Actividades económicas ED — total gastos simplificada | 0223 | Covered (new) |
| Actividades económicas ED — rendimiento neto | 0224 | Covered (new) |
| Actividades económicas ED — rendimiento neto reducido | 0226 | Covered (new) |
| Actividades económicas ED — suma rdto neto reducido | 0231 | Covered (new) |
| Actividades económicas ED total | 0235 | Covered (chunk 2) |
| Saldo neto base imponible general | 0432 | Covered (chunk 2) |
| Base imponible general | 0435 | Deferred (ambiguous duplicate) |
| Base imponible del ahorro | 0460 | Deferred (ambiguous) |
| Base liquidable general | 0500 | Covered (chunk 2) |
| Base liquidable general sometida a gravamen | 0505 | Covered (chunk 1) |
| Base liquidable del ahorro | 0510 | Covered (chunk 2) |
| Cuota íntegra estatal | 0545 | Covered (chunk 1) |
| Cuota íntegra autonómica | 0546 | Covered (chunk 1) |
| Cuota líquida estatal incrementada | 0585 | Covered (chunk 1) |
| Cuota líquida autonómica incrementada | 0586 | Covered (chunk 1) |
| Cuota líquida incrementada total | 0587 | Covered (chunk 1) |
| Cuota resultante de la autoliquidación | 0595 | Covered (chunk 1) |
| Cuota diferencial | 0610 | Covered (chunk 1) |
| Resultado de la declaración | 0670 | Covered (chunk 1) |

## Files changed

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Test results

- `test_parser_extracts_modelo_100_profile_targets_from_corpus[2021-0A]`: passed
- `test_parser_extracts_modelo_100_profile_targets_from_corpus[2022-0A]`: passed
- `test_parser_extracts_modelo_100_profile_targets_from_corpus[2023-0A]`: passed
- `test_modelo_parity_coverage` (26 modelos valid): passed
- Full inbound declaracion suite: 63/63 passed
- Ruff: all checks passed

## Commit

`611bd7d06` — M100 extraction profile third chunk: 6 actividades-económicas ED detail casillas
