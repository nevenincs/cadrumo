---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S212'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# `declaracion-extraction-architecture` W10.P53.S212 — M390 corpus regeneration with formula-consistent values

## Step

Regenerate 2 M390 corpus fixture PDFs (`src/aeat/tests/fixtures/justificantes/390/2022-0A.pdf`,
`2023-0A.pdf`) with formula-consistent casilla values so `iva.anual.resultado-regimen-general`
(box 65) transitions from FORMULA-MISMATCH to VERIFIED. Mirror the M130 task #71 pattern
(W10.P45.S202) and M303 task #82 pattern (W10.P52.S209). Flip `verification_source` from
`real_aeat_corpus_pdf` to `synthetic_from_aeat_published_text` in the M390 extraction profile.

## Execution

### UNIT 1 — Root-cause audit

The 2 existing M390 corpus PDFs (2022-0A, 2023-0A) were real AEAT-generated PDFs (sanitised
by the corpus sanitiser). All monetary values had been uniformly replaced with `1.000,00`.
The extraction profile (W10.P46.S203) had added bbox_anchored leaf casilla targets (boxes
02/04/06/26/49), so the extractor correctly captured all five leaf inputs as `1.000,00`. The
verification chain test then:

- Supplied leaf inputs: `repercutido.general=1000, soportado.interiores=1000`, zeros for rest.
- Engine computed: `cuota-devengada-total(47) = 1000`, `cuota-deducible-total(64) = 1000`.
- Engine computed: `resultado-regimen-general(65) = 1000 - 1000 = 0`.
- Extracted printed box 65: `1000.00` (sanitiser-overwritten value).
- Result: FORMULA-MISMATCH — engine output 0 ≠ printed 1000.

This was an artefact of the uniform-1000 sanitisation, not a registry defect.

### UNIT 2 — M390 formula DAG

Registry source:
`src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/formulas/0001-formulas.toml`

Three formulas (Orden EHA/3111/2009 art. 1, ley-37-1992 art. 88/90/91/92):
- `cuota-devengada-total (47)` = `repercutido.general(06) + repercutido.reducido(04) + repercutido.super-reducido(02) + autorepercutido.intracomunitaria(26)`
- `cuota-deducible-total (64)` = `soportado.interiores(49) + autorepercutido.intracomunitaria(26)`
- `resultado-regimen-general (65)` = `cuota-devengada-total(47) - cuota-deducible-total(64)`

Simple-case (no reduced/super-reduced, no intracomunitaria): `c04=c02=c26=0`.

### UNIT 3 — Implementation

Added to `src/aeat/tests/fixtures/justificantes/_generate.py`:

- `_Modelo390CorpusFixture` — frozen dataclass with fields `filename, ejercicio, tax_id,
  c06, c04, c02, c26, c49, c47, c64, c65`.
- `_compute_m390_closure(c06, c04, c02, c26, c49)` — returns `(c47, c64, c65)` per formula
  DAG, all values `quantize(Decimal("0.01"))`.
- `_m390_fixture(filename, ejercicio, tax_id, c06, c49)` — convenience constructor for
  simple-case specimens (c04=c02=c26=0), calls `_compute_m390_closure` once.
- `_MODELO_390_CORPUS_FIXTURES` — 2 fixtures (2022-0A, 2023-0A).
- `_draw_modelo_390_corpus(c, fixture)` — renders:
  - Five bbox_anchored leaf casillas at `x=414` (within anchor 407–425), values at `x=480`.
    Boxes 06/04/02/26/49 all printed (including zero-value ones).
  - Three named_label computed casillas with profile-verbatim label text:
    `"Total cuotas IVA y recargo de equivalencia"` (box 47),
    `"Suma de deducciones"` (box 64),
    `"Resultado regimen general (47 - 64)"` (box 65).
  - `NIF: <tax_id>` header so `_TAX_ID_RE` succeeds.
  - `invariant=True` Canvas for byte-deterministic output.
- Generation loop added to `main()` after M303 corpus loop.

Updated `verification_source` in extraction profile TOML:
`src/aeat/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/extraction_profiles/0001-extraction_profiles.toml`
`real_aeat_corpus_pdf` → `synthetic_from_aeat_published_text`.

### UNIT 4 — Leaf-input scheme per specimen

| Specimen | c06 (21%) | c49 (deducible) | c47 (devengada) | c64 (deducible) | c65 (resultado) |
|----------|-----------|-----------------|-----------------|-----------------|-----------------|
| 2022-0A  | 10500.00  | 8400.00         | 10500.00        | 8400.00         | 2100.00         |
| 2023-0A  | 12600.00  | 9800.00         | 12600.00        | 9800.00         | 2800.00         |

Boxes 02/04/26: 0.00 in both fixtures (no reduced-rate/intracomunitaria activities).
Compensation casillas (97/662): not printed (no carry-forward in simple-case fixtures).

### UNIT 5 — Test updates

Updated `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`:

- `test_parser_extracts_modelo_390_profile_targets_from_corpus`: replaced uniform
  `Decimal("1000.00")` loop with per-specimen `_EXPECTED` dict containing all 8 casilla IDs
  (5 bbox leaf + 3 named_label computed). Key set assertion updated: 8 casillas now (was 7,
  no longer includes compensacion-ultimo-periodo-97 and compensacion-generada-ejercicio-no-97
  since synthetic fixtures do not print those; gains repercutido.reducido and
  repercutido.super-reducido and autorepercutido.intracomunitaria which were blank in real PDFs).

Updated `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`:

- `test_verification_chain_m390_engine_recomputes_cuota_devengada_deducible`:
  - Docstring: verdict updated from FORMULA-MISMATCH to VERIFIED for all three casillas.
  - Replaced the conditional FORMULA-MISMATCH documentation block (lines 940-955) with
    hard VERIFIED-FAIL assertions:
    `engine_resultado is not None`, `extracted_resultado isinstance Decimal`,
    `engine_resultado == extracted_resultado`.

### UNIT 6 — Verification chain result

```
uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/test_verification_chain.py -k "m390" -v --tb=long
```

```
test_verification_chain_m390_engine_recomputes_cuota_devengada_deducible[2022-0A-2022] PASSED
test_verification_chain_m390_engine_recomputes_cuota_devengada_deducible[2023-0A-2023] PASSED
2 passed in 24.60s
```

All three closure casillas VERIFIED for both specimens:
- `iva.anual.cuota-devengada-total` (box 47): VERIFIED ✓
- `iva.anual.cuota-deducible-total` (box 64): VERIFIED ✓
- `iva.anual.resultado-regimen-general` (box 65): VERIFIED ✓ (was FORMULA-MISMATCH)

### UNIT 7 — Determinism check

Two consecutive generator runs produced identical PDF bytes for both specimens
(git diff unchanged between runs). `invariant=True` + deterministic `_compute_m390_closure`
arithmetic ensure stable output.

### UNIT 8 — Regression check

```
uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/test_verification_chain.py
  src/aeat/adapters/inbound/declaracion/test_parser_boundary.py -q --tb=short
```

161 passed (excluding pre-existing M036 fixture-missing failure unrelated to this step).

## Commit

`54756d1cf` — fix(m390): regen corpus fixtures with formula-consistent values — resultado-regimen-general VERIFIED

## Honest verdict

Both M390 specimens (2022-0A, 2023-0A) regenerated with formula-consistent values.
`iva.anual.resultado-regimen-general` transitions FORMULA-MISMATCH → VERIFIED.
`verification_source` correctly reflects `synthetic_from_aeat_published_text`.
The complete M390 formula chain (cuota-devengada-total, cuota-deducible-total,
resultado-regimen-general) is now VERIFIED against the extraction engine.
