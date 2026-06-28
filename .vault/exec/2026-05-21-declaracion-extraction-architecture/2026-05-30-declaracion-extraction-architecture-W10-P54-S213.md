---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-30'
modified: '2026-05-30'
step_id: S213
related:
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# declaracion-extraction-architecture W10.P54.S213 — justificante corpus fixture CSV embedding

## Step

Extend justificante extractor regex tiers to cover 32 currently-failing
`test_corpus_sidecar_roundtrip.py` cases across Modelo 130 (15 specimens),
Modelo 303 (15 specimens), and Modelo 390 2022-0A + 2023-0A (2 specimens).

## Root Cause Analysis

Investigation revealed the failures were not extractor tier gaps. The
existing `_CSV_LABEL_RE` tier already matches `Codigo Seguro de Verificacion:
VALUE`. The real cause was a **generator/sidecar mismatch**: synthetic corpus
fixture PDFs for M130, M303, and M390 (produced by `_generate.py`) were built
without embedding the `SANITIZED{modelo}{ejercicio}` CSV token. Their sidecar
JSON manifests had been imported from real sanitised PDFs that do carry the
token. The parser raised `JustificanteCsvNotFoundError` for every one of the
32 cases because no CSV was present in the PDF text layer.

Secondary: M390/2022-0A and M390/2023-0A were listed in
`_PERIOD_EQUALS_EJERCICIO` (period = ejercicio for annual fixtures lacking an
explicit period label). After regeneration those PDFs explicitly print
`Periodo: 0A`, making the period label present — so the parser correctly
returns `"0A"` rather than the year, but both test files expected the year.

## Changes

### `src/aeat/tests/fixtures/justificantes/_generate.py`

Added a receipt block at the end of three corpus draw functions
(`_draw_modelo_303_corpus`, `_draw_modelo_130_corpus`,
`_draw_modelo_390_corpus`). Each block appends:

```
Codigo Seguro de Verificacion: SANITIZED{modelo}{ejercicio}
Fecha y hora de presentacion: {presented_at}
https://sede.agenciatributaria.gob.es
```

The `csv` and `presented_at` fields were added to the three corpus fixture
dataclasses (`_Modelo303CorpusFixture`, `_Modelo130CorpusFixture`,
`_Modelo390CorpusFixture`) with sensible defaults, keeping the fixture
definitions backward-compatible.

### 32 PDF fixtures regenerated (binary)

- `src/aeat/tests/fixtures/justificantes/130/2021-2T.pdf` — `2024-4T.pdf` (15 files)
- `src/aeat/tests/fixtures/justificantes/303/2021-2T.pdf` — `2024-4T.pdf` (15 files)
- `src/aeat/tests/fixtures/justificantes/390/2022-0A.pdf` and `2023-0A.pdf` (2 files)

### `src/aeat/adapters/inbound/justificante/test_corpus_sidecar_roundtrip.py`

Removed `("390", "2022-0A")` and `("390", "2023-0A")` from
`_PERIOD_EQUALS_EJERCICIO`. These two fixtures now print `Periodo: 0A`
explicitly; the expected period is `"0A"`, not the ejercicio year.

### `src/aeat/adapters/inbound/justificante/test_parser.py`

Added `("390", "2022-0A")` and `("390", "2023-0A")` to
`explicit_annual_fixtures` in `_observed_period_expected()`. Aligns the
`TestRealCorpusParses` period expectations with the regenerated PDF content.

## Verification

- `test_corpus_sidecar_roundtrip.py`: 42/42 pass (was 10/42).
- `test_parser.py::TestRealCorpusParses[390/2022-0A]` and `[390/2023-0A]`: pass.
- 16 remaining `TestRealCorpusParses` failures are pre-existing (M036, M115,
  M123, M131, M180, M184, M193, M232, M347, M349, M369, M720, M840); none
  involve files touched by this step.
- Ruff: 7 pre-existing errors in `_generate.py` (RUF002/RUF003 EN DASH,
  E501 long line 1836); none introduced by this change (confirmed by
  `git show HEAD:_generate.py | ruff check`).

## Commit

`1e74435f7` — fixtures(justificante): embed CSV/timestamp/URL in M130/M303/M390 corpus PDFs (W10.P54)
