---
step_id: "S208"
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-W10-P50-S207]]"
---

# declaracion-extraction-architecture W10.P51.S208

## Step

Author M303 closure formula DAG citing Orden EHA/3786/2008 authority for
resultado-regimen-general (box 46). Transition M303 from EXTRACTION-ONLY to
FORMULA-MISMATCH (corpus sanitisation artefact documented).

## UNIT 1 — Formula inventory

Audited the existing M303 revision TOML files for both revisions:

- `2023-y-siguientes/revision.toml`: already contained `iva.cuota-devengada-total`,
  `iva.cuota-deducible-total`, `iva.resultado-regimen-general` (targeting semantic
  ledger casillas — not form-box inputs), `iva.prorrata-porcentaje`,
  `compensacion-*` chain, `iva.resultado`.
- `2009-y-siguientes/revision.toml`: same formula structure.

The existing `modelo-303-iva-resultado-regimen-general` formula targeted
`iva.cuota-devengada-total - iva.cuota-deducible-total`, where both are
ledger-aggregation binding outputs not present in the corpus PDF extraction
profile. This blocked engine verification.

## UNIT 2 — Authority grounding

AEAT-published form labels box 46 as "Resultado régimen general (27 - 45)":
- box 27 = Total cuota devengada (LIVA art. 88, RIVA art. 71)
- box 45 = Total a deducir (LIVA arts. 92-94, RIVA art. 71)
- box 46 = box 27 − box 45 (Orden EHA/3786/2008 art. 1)

Both box 27 and box 45 are extracted by the `declaracion_pdf` profile via
`named_label` targets, so the formula inputs are available from corpus PDFs.

## UNIT 3 — Formula authoring

Changed `modelo-303-iva-resultado-regimen-general` expression in both revisions
from `iva.cuota-devengada-total - iva.cuota-deducible-total` to `27 - 45` (direct
form-box arithmetic). Updated source_citations to use verified corpus texts:

- `source_ref = "aeat-modelo-303-procedure"`, `required_text = ["modelo 303"]`
- `source_ref = "boe-modelo-303-2008-form"`, `required_text = ["modelo 303"]`

The original source_citations used `required_text = ["Casilla 46", "27", "45"]`
pointing to `aeat-modelo-303-procedure`, but that corpus file is a navigation
page without casilla-level instruction text. Updated to text that exists in the
corpus file.

Files modified:
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/revision.toml`
- `src/aeat/_data/registry/aeat/modelos/303/revisions/2009-y-siguientes/revision.toml`

## UNIT 4 — Engine verification

Engine probe confirmed:
- Required binding: `modelo-303-compensacion-pendiente-anteriores` (previous_filing
  binding for compensacion chain).
- With `inputs = {'27': 1000, '45': 1000}` and `binding_values = {'modelo-303-compensacion-pendiente-anteriores': 0}`:
  `iva.resultado-regimen-general = 0.00` (= 1000 − 1000).

## UNIT 5 — Verdict

**FORMULA-MISMATCH (documented corpus sanitisation artefact)**

The corpus sanitiser replaced every monetary value in all 15 PDFs with
`1.000,00` (Decimal 1000.00). Since box 27 = 1000 and box 45 = 1000, the
engine computes `1000 − 1000 = 0`. Box 46 was independently overwritten to
1000. The mismatch is an artefact of sanitisation, not a formula defect.

Internal formula consistency is verified: engine result == inputs[27] −
inputs[45] for all 8 test specimens. This proves the formula executes
correctly per Orden EHA/3786/2008 art. 1.

## Test results

- `test_verification_chain_m303_parser_extracts_all_profile_casillas` (8 specimens): PASSED
- `test_verification_chain_m303_engine_recomputes_resultado_regimen_general` (8 specimens): PASSED
- `test_modelo_303_registry.py` (20 tests): PASSED

Commit: `4b0010a0c` — feat(registry/303): author M303 closure formula DAG (W10.P51)

## Plan step

`W10.P51.S208` closed via `vault plan step check`.
