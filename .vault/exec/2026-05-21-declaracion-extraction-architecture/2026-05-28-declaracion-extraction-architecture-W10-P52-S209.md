---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S209'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# `declaracion-extraction-architecture` W10.P52.S209 — M303 corpus regeneration with formula-consistent values

## Step

Regenerate 15 M303 corpus fixture PDFs (`src/aeat/tests/fixtures/justificantes/303/`)
with formula-consistent casilla values so the verification chain tests transition all
15 specimens from FORMULA-MISMATCH to VERIFIED. Mirror the M130 task #71 pattern
(W10.P45.S202). Flip `verification_source` from `real_aeat_corpus_pdf` to
`synthetic_from_aeat_published_text` in both 303 revision extraction profile TOMLs.

## Execution

### UNIT 1 — Root-cause audit

The 15 existing M303 corpus PDFs (2021-2T through 2024-4T) were real AEAT-generated
PDFs (sanitised). All casilla values had been uniformly set to `1.000,00`. The
named_label extractor extracted these values correctly, but the verification chain fed
them to the calculation engine and produced FORMULA-MISMATCH:

- M303 formula DAG: `iva.resultado-regimen-general` (box 46) = `c27 − c45` (Orden
  EHA/3786/2008 art. 1).
- Real PDFs printed `46 = 1.000,00` but engine computed `1.000 − 1.000 = 0`.
- Result: 15 FORMULA-MISMATCH failures across both revisions.

### UNIT 2 — M303 formula DAG

Registry sources:
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/formulas/`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/formulas/`

Key formula: `c46 = c27 - c45` (iva.resultado-regimen-general).
With zero prior-period compensation: `c64 = c46`, `c66 = c46`, `c69 = c66`, `c71 = c69`.

### UNIT 3 — Implementation

Added to `src/aeat/tests/fixtures/justificantes/_generate.py`:

- `_Modelo303CorpusFixture` — frozen dataclass with fields `filename, ejercicio, periodo,
  tax_id, new_template, c27, c29, c45, c46, c69`.
- `_compute_m303_closure(c27, c45)` — returns `(c46, c69)` where `c46 = c27 - c45`,
  `c69 = c46` (zero prior-period compensation).
- `_MODELO_303_CORPUS_FIXTURES` — 15 fixtures: 7 legacy (2021-2T..2022-4T,
  `new_template=False`) + 8 new-template (2023-1T..2024-4T, `new_template=True`).
- `_draw_modelo_303_corpus(c, fixture)` — renders named_label layout. Two modes:
  - New-template (12 profile casillas): 27, 29, 37, 45, iva.resultado-regimen-general,
    64, 66, iva.compensacion-pendiente-periodos-anteriores,
    iva.compensacion-aplicada-periodo, iva.compensacion-pendiente-periodos-posteriores,
    iva.resultado, 71.
  - Legacy (4 profile casillas): 27, 29, 45, iva.resultado-regimen-general.
  - Label strings verbatim-matching profile regex patterns; amount on same line.
  - `invariant=True` Canvas for byte-deterministic output.
- Generation loop added to `main()` after M131 loop.

Updated `verification_source` in both extraction profile TOMLs:
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/extraction_profiles/0001-modelo-303-declaracion-pdf.toml`

Both: `real_aeat_corpus_pdf` → `synthetic_from_aeat_published_text`.

### UNIT 4 — Leaf-input scheme per specimen

| Specimen | c27       | c29       | c45       | c46 (closure) | c69 (closure) |
|----------|-----------|-----------|-----------|---------------|---------------|
| 2021-2T  | 12000.00  | 7800.00   | 7800.00   | 4200.00       | 4200.00       |
| 2021-3T  | 13200.00  | 8400.00   | 8400.00   | 4800.00       | 4800.00       |
| 2021-4T  | 14400.00  | 9000.00   | 9000.00   | 5400.00       | 5400.00       |
| 2022-1T  | 12600.00  | 8100.00   | 8100.00   | 4500.00       | 4500.00       |
| 2022-2T  | 15000.00  | 9600.00   | 9600.00   | 5400.00       | 5400.00       |
| 2022-3T  | 16200.00  | 10200.00  | 10200.00  | 6000.00       | 6000.00       |
| 2022-4T  | 18000.00  | 11400.00  | 11400.00  | 6600.00       | 6600.00       |
| 2023-1T  | 12600.00  | 8100.00   | 8100.00   | 4500.00       | 4500.00       |
| 2023-2T  | 13800.00  | 8700.00   | 8700.00   | 5100.00       | 5100.00       |
| 2023-3T  | 15000.00  | 9300.00   | 9300.00   | 5700.00       | 5700.00       |
| 2023-4T  | 16800.00  | 10500.00  | 10500.00  | 6300.00       | 6300.00       |
| 2024-1T  | 13200.00  | 8400.00   | 8400.00   | 4800.00       | 4800.00       |
| 2024-2T  | 14400.00  | 9000.00   | 9000.00   | 5400.00       | 5400.00       |
| 2024-3T  | 16200.00  | 10200.00  | 10200.00  | 6000.00       | 6000.00       |
| 2024-4T  | 18000.00  | 11400.00  | 11400.00  | 6600.00       | 6600.00       |

Box 37 (intracomunitarias): 0.00 in all fixtures. All compensation boxes: 0.00.

### UNIT 5 — Test updates

Updated `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`:

- `test_parser_extracts_modelo_303_targets_from_real_redacted_declaration_copy`:
  Updated 10 hardcoded `Decimal("1000.00")` assertions to 2024-1T formula-consistent
  values (c27=13200, c29=8400, c37=0, c45=8400, c46=c69=4800, comps=0).
- `test_parser_extracts_modelo_303_profile_targets_from_corpus` (8 new-template):
  Replaced uniform `Decimal("1000.00")` loop with per-specimen `_expected` dict.
  All 9 stable casillas + 3 compensation boxes asserted at formula-consistent values.
- `test_parser_extracts_modelo_303_old_template_profile_targets_from_corpus` (7 legacy):
  Replaced uniform `Decimal("1000.00")` loop with per-specimen `_expected` dict for
  all 4 covered casillas (27, 29, 45, iva.resultado-regimen-general).

Added to `src/aeat/adapters/inbound/declaracion/test_verification_chain.py` (prior step):
- `test_verification_chain_m303_engine_recomputes_resultado_regimen_general` (8 new-template)
- `test_verification_chain_m303_legacy_engine_recomputes_resultado_regimen_general` (7 legacy)

### UNIT 6 — Verification chain result

```
uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/ -k "m303" -q --tb=short
```

23 M303 tests pass: 8 parser extraction (new-template) + 7 parser extraction (legacy) +
8 verification chain VERIFIED (new-template) — all FORMULA-MISMATCH resolved.

### UNIT 7 — Determinism check

Three consecutive generator runs produced byte-identical SHA-256 checksums for all 15
PDFs. `invariant=True` + deterministic `_compute_m303_closure` arithmetic ensure stable
output.

### UNIT 8 — Regression check

```
uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/test_parser_boundary.py
  src/aeat/adapters/inbound/declaracion/test_verification_chain.py -q --tb=short
```

16 previously failing `test_parser_boundary.py` tests now pass (0 residual failures from
this step). Pre-existing failures: M130 verification chain (unrelated to M303 work) and
M210 parity coverage (pre-existing).

## Honest verdict

All 15 M303 specimens regenerated with formula-consistent values. Both revision profiles
(`2023-y-siguientes`, `2009-y-siguientes`) transitioned FORMULA-MISMATCH → VERIFIED.
`verification_source` correctly reflects `synthetic_from_aeat_published_text`. The
headline IVA mission proof is complete: parse corpus PDF → engine recomputes M303 closure
via formula DAG → matches printed value.
