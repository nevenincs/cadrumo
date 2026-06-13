---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-30'
modified: '2026-05-30'
step_id: S214
related:
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# declaracion-extraction-architecture W10.P55.S214 — test_parser.py fixture-test parity for 13 new corpus modelos

## Step

Add per-modelo test_parser.py entries (via full justificante receipt trailers
in the corpus PDFs) for 13 modelos added by prior campaign steps without
parallel `TestRealCorpusParses` support: M036/M115/M123/M131/M180/M184/M193/
M232/M347/M349/M369/M720/M840.

## Root Cause Analysis

W10.P54 surfaced 16 pre-existing `TestRealCorpusParses` failures.
`TestRealCorpusParses` auto-discovers every PDF under `justificantes/`
subdirectories and calls `parse_justificante()` on each. The 16 failing PDFs
were declaracion-only synthetic fixtures — `_generate.py` produced them
without a justificante receipt trailer (no CSV token, no presentation
timestamp, no AEAT URL). The parser raises `JustificanteCsvNotFoundError`
for every PDF lacking those three fields.

The fix location was `_generate.py` (add receipt trailers to the 13 draw
functions), not the test itself. The test was correct: any PDF committed
under `justificantes/` is expected to be a complete justificante receipt.

Secondary issues discovered during implementation:

- **M036**: `_extract_period_and_ejercicio()` could not locate a year because
  the M036 draw function emitted neither a `Periodo:` label nor an
  `Ejercicio:` label. Added `Ejercicio: {ejercicio}` to `_draw_modelo_036()`
  so the period-fallback path finds the year.
- **M131**: The fixture had `ejercicio="2026"` but the filename stem is
  `2024-1T`, so `ejercicio_expected="2024"`. Changed to `ejercicio="2024"`.
  (The verification chain and parser boundary tests use explicit
  `año_override=2026` and are unaffected.)
- **New sidecar pairs picked up by `test_corpus_sidecar_roundtrip.py`**: 8 of
  the 16 new/regenerated PDFs are annual or censal modelos where the parser
  returns the ejercicio year as period (no `Periodo:` label). Added 8 entries
  to `_PERIOD_EQUALS_EJERCICIO` and raised the corpus pair count guard from
  `>= 40` to `>= 55`.

## UNIT 1 — Failure Inventory

| Modelo | Period | Failure Mode |
|--------|--------|--------------|
| 036 | 2025-0A | JustificanteCsvNotFoundError |
| 036 | 2025-alta | JustificanteCsvNotFoundError |
| 115 | 2024-1T | JustificanteCsvNotFoundError |
| 123 | 2023-1T | JustificanteCsvNotFoundError |
| 123 | 2024-1T | JustificanteCsvNotFoundError |
| 131 | 2024-1T | JustificanteCsvNotFoundError |
| 180 | 2024-0A | JustificanteCsvNotFoundError |
| 184 | 2024-0A | JustificanteCsvNotFoundError |
| 193 | 2024-0A | JustificanteCsvNotFoundError |
| 232 | 2016-0A | JustificanteCsvNotFoundError |
| 232 | 2018-0A | JustificanteCsvNotFoundError |
| 347 | 2024-0A | JustificanteCsvNotFoundError |
| 349 | 2024-1T | JustificanteCsvNotFoundError |
| 369 | 2024-1T | JustificanteCsvNotFoundError |
| 720 | 2024-0A | JustificanteCsvNotFoundError |
| 840 | 2024-0A | JustificanteCsvNotFoundError |

## UNIT 3 — Expected Values Source

| Modelo | Period | expected_csv | expected_ejercicio | expected_period | Source |
|--------|--------|-------------|-------------------|----------------|--------|
| 036 | 2025-0A | SANITIZED0362025 | 2025 | 2025 | _generate.py SANITIZED token; period=ejercicio (censal, no Periodo label) |
| 036 | 2025-alta | SANITIZED0362025 | 2025 | 2025 | same |
| 115 | 2024-1T | SANITIZED1152024 | 2024 | 1T | _generate.py SANITIZED token |
| 123 | 2023-1T | SANITIZED1232023 | 2023 | 1T | _generate.py SANITIZED token |
| 123 | 2024-1T | SANITIZED1232024 | 2024 | 1T | _generate.py SANITIZED token |
| 131 | 2024-1T | SANITIZED1312024 | 2024 | 1T | _generate.py SANITIZED token |
| 180 | 2024-0A | SANITIZED1802024 | 2024 | 0A | _generate.py SANITIZED token; M180 prints Periodo: 0A explicitly |
| 184 | 2024-0A | SANITIZED1842024 | 2024 | 2024 | _generate.py SANITIZED token; period=ejercicio (annual, no Periodo label) |
| 193 | 2024-0A | SANITIZED1932024 | 2024 | 0A | _generate.py SANITIZED token; M193 prints Periodo: 0A explicitly |
| 232 | 2016-0A | SANITIZED2322016 | 2016 | 2016 | _generate.py SANITIZED token; period=ejercicio (annual, no Periodo label) |
| 232 | 2018-0A | SANITIZED2322018 | 2018 | 2018 | same |
| 347 | 2024-0A | SANITIZED3472024 | 2024 | 2024 | _generate.py SANITIZED token; period=ejercicio (annual, no Periodo label) |
| 349 | 2024-1T | SANITIZED3492024 | 2024 | 1T | _generate.py SANITIZED token |
| 369 | 2024-1T | SANITIZED3692024 | 2024 | 1T | _generate.py SANITIZED token |
| 720 | 2024-0A | SANITIZED7202024 | 2024 | 2024 | _generate.py SANITIZED token; period=ejercicio (annual, no Periodo label) |
| 840 | 2024-0A | SANITIZED8402024 | 2024 | 2024 | _generate.py SANITIZED token; period=ejercicio (annual, no Periodo label) |

## Changes

### `src/aeat/tests/fixtures/justificantes/_generate.py`

- Added `import hashlib, json`.
- Added `ejercicio: str` and `presented_at` fields to `_Modelo036Fixture`.
- Added `Ejercicio: {fixture.ejercicio}` line to `_draw_modelo_036()`.
- Changed M131 fixture `ejercicio` from `"2026"` to `"2024"`.
- Added justificante receipt trailer (CSV, timestamp, AEAT URL) to all 13
  draw functions: `_draw_modelo_036`, `_draw_modelo_115`, `_draw_modelo_123`,
  `_draw_modelo_131`, `_draw_modelo_180`, `_draw_modelo_184`,
  `_draw_modelo_193`, `_draw_modelo_232`, `_draw_modelo_347`,
  `_draw_modelo_349`, `_draw_modelo_369`, `_draw_modelo_720`,
  `_draw_modelo_840`.
- Added `_write_sidecar(pdf_path, modelo, ejercicio, tax_id)` helper that
  emits the sanitiser-manifest JSON sidecar next to each PDF.
- Updated `main()` to call `_write_sidecar` after each of the 13 PDF saves.

### 16 PDF fixtures regenerated + 16 new JSON sidecars created

- `src/aeat/tests/fixtures/justificantes/036/2025-0A.pdf` + `.json` (new PDF)
- `src/aeat/tests/fixtures/justificantes/036/2025-alta.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/115/2024-1T.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/123/2023-1T.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/123/2024-1T.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/131/2024-1T.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/180/2024-0A.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/184/2024-0A.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/193/2024-0A.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/232/2016-0A.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/232/2018-0A.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/347/2024-0A.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/349/2024-1T.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/369/2024-1T.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/720/2024-0A.pdf` + `.json`
- `src/aeat/tests/fixtures/justificantes/840/2024-0A.pdf` + `.json`

### `src/aeat/adapters/inbound/justificante/test_corpus_sidecar_roundtrip.py`

- Extended `_PERIOD_EQUALS_EJERCICIO` with 8 new entries: `("036","2025-0A")`,
  `("036","2025-alta")`, `("184","2024-0A")`, `("232","2016-0A")`,
  `("232","2018-0A")`, `("347","2024-0A")`, `("720","2024-0A")`,
  `("840","2024-0A")`.
- Raised `test_corpus_pair_count` guard from `>= 40` to `>= 55`.

### `src/aeat/adapters/inbound/justificante/test_parser.py`

- Added `("180","2024-0A")` and `("193","2024-0A")` to `explicit_annual_fixtures`
  (these PDFs print `Periodo: 0A` explicitly).
- Added M036 special case: `if fixture.parent.name == "036": return ejercicio`
  (M036 uses event codes not calendar period codes).

## Verification

- `test_parser.py`: 77/77 pass (was 61/77 before this step; 16 new passes).
- `test_corpus_sidecar_roundtrip.py`: 58/58 pass (was 42/42; 16 new sidecar pairs).
- All justificante adapter tests: 168/168 pass.
- Declaracion adapter regression check: exit 0 (no regressions).

## Commit

`f514c8be3` — fix(justificante): add receipt trailers + sidecars for 13 new corpus modelos (W10.P55)
