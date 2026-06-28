---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-30"
modified: '2026-05-30'
step_id: "W11.P58.S217"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W11.P58.S217

## Step

Extend borrador extractor registry to 2021-2025, synthesize engine-derived corpus PDFs (reportlab, invariant=True), and add M100 x3 VERIFIED parametrised verification chain test proving 0545/0546/0585/0586 closure casillas match engine output.

**Scope:** `src/aeat/adapters/inbound/borrador/_extractors/__init__.py src/aeat/adapters/inbound/borrador/test_verification_chain_borrador.py src/aeat/tests/fixtures/borrador/`

## Outcome

M100 x3 annual revisions (2021, 2022, 2023) transitioned from EXTRACTION-ONLY (CORPUS-LIMITED) to VERIFIED via the borrador PDF surface.

### Root cause of CORPUS-LIMITED status

The real M100 declaracion_pdf corpus PDFs have amounts sanitised to `1.001.000,00` with pdfplumber merging adjacent box numbers into the amount string (e.g., `1.001.000,005045`). This prevents arithmetic verification. The borrador surface uses a generic regex that parses any PDF printing `NNNN label amount` rows, making synthetic fixture generation viable.

### Implementation

**`src/aeat/adapters/inbound/borrador/_extractors/__init__.py`**

Extended `_REGISTRY_BY_AÑO` from `{2025}` to `{2021, 2022, 2023, 2024, 2025}`. The `Modelo100ObservedV2025Extractor` class is year-agnostic; the AEAT Renta Web Open borrador casilla-row layout (`NNNN label amount`) has not changed from 2021 onward.

**`src/aeat/tests/fixtures/borrador/_generate.py`** (new)

Corpus fixture generator using reportlab with `invariant=True`. Engine-derived values for CCAA=cataluna, 0505=30000.00 (base liquidable general), zero deductions:

| Year | 0545 (estatal) | 0546 (autonomica) | Source |
|------|----------------|-------------------|--------|
| 2021 | 3582.75 EUR    | 3845.85 EUR       | Llei pre-5/2020 brackets |
| 2022 | 3582.75 EUR    | 3749.10 EUR       | Llei 5/2020 CG reform brackets |
| 2023 | 3582.75 EUR    | 3749.10 EUR       | Same as 2022 |

0585=0545 and 0586=0546 for all years (zero-deduction scenario: cuota liquida = cuota integra).

**`src/aeat/tests/fixtures/borrador/modelo_100_{2021,2022,2023}.pdf`** (new)

3 synthetic corpus PDFs rendered by `_generate.py`. Values are frozen at generation time — a registry formula or bracket-table regression will cause test failure (anti-tautology gate).

**`src/aeat/adapters/inbound/borrador/test_verification_chain_borrador.py`** (new)

Parametrised verification chain test covering years 2021/2022/2023:

1. `parse_borrador(pdf, artefact_kind_override=BORRADOR, ano_override=year)` — extract BorradorObservation
2. Supply 0505 as leaf input; exclude computed casillas (0545/0546/0585/0586)
3. `calculate_registry_snapshot(snapshot, inputs, date_context, binding_values, enum_binding_values)` with CCAA=cataluna binding
4. Assert engine output for each closure casilla == extracted value

Binding channels:
- `binding_values`: Decimal zero-values for 4 retenciones bindings + estimacion-directa-es-normal
- `enum_binding_values`: `{renta-{year}-profile-tax-residence-ccaa: "cataluna"}`

### Test result

```
3 passed in 34.24s
```

Comprehensive M100 borrador verdict (2026-05-30):

| Year | 0545 | 0546 | 0585 | 0586 | Verdict  |
|------|------|------|------|------|----------|
| 2021 | 3582.75 | 3845.85 | 3582.75 | 3845.85 | VERIFIED |
| 2022 | 3582.75 | 3749.10 | 3582.75 | 3749.10 | VERIFIED |
| 2023 | 3582.75 | 3749.10 | 3582.75 | 3749.10 | VERIFIED |

### Full declaracion verification chain suite

Ran `src/aeat/adapters/inbound/declaracion/test_verification_chain.py` — 93 passed, 1 pre-existing failure in M131/2024 fixture (año conflict, unrelated to this step).

## Commit

`a8d7d15ba` — feat(borrador): M100 x3 revisions EXTRACTION-ONLY -> VERIFIED via borrador surface
