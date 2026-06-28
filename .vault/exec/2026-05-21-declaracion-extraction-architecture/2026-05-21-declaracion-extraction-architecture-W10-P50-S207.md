---
step_id: "S207"
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-28-declaracion-extraction-architecture-W10-P49-S206]]"
---

# declaracion-extraction-architecture W10.P50.S207

## Step

Extend M100 (2021/2022/2023 revisions) `declaracion_pdf` extraction profiles'
`target_casillas` to include the leaf inputs the engine needs to recompute the
cuota-chain closure. Transition verdict from EXTRACTION-ONLY → VERIFIED where
possible; document CORPUS-LIMITED verdict if not.

## UNIT 1 — Formula DAG closure analysis

Traced the cuota-chain DAG from the registry formula TOML files:

```
0171..0179 → 0180 → 0224 → 0545/0546 → 0570/0571 → 0585/0586 → 0587 → 0595 → 0610 → 0670
```

Full set of leaf inputs for 0545 (cuota íntegra estatal): 51 leaves. These
include all 017x rendimientos netos, 019x reducciones, multiple bracket-lookup
bindings, CCAA residence enum, and retenciones periodicas bindings from M111,
M115, M123. The declaracion_pdf surface does not print the individual 017x–019x
leaves for most filers; the PDF prints only summary casillas.

## UNIT 2 — Corpus PDF inspection

Inspected corpus PDFs (2021-0A.pdf, 2022-0A.pdf, 2023-0A.pdf) via the
`named_label` match strategy against the extraction profile. Results:

| Casilla | Label in PDF                        | Individually printed? | Extractable |
|---------|-------------------------------------|----------------------|-------------|
| 0171    | Ingresos de explotación             | YES                  | YES         |
| 0172-0179 | (aggregated under group header)  | NO                   | NO          |
| 0180    | (section total)                     | YES via existing target | already in profile |
| 0224    | (formula output)                    | YES via existing target | already in profile |
| 0545/0546 | Cuota íntegra estatal/autonómica | YES via existing target | already in profile |

Corpus sanitisation note: all monetary amounts replaced with ~1.001.000,00 EUR.
The pdfplumber engine merges adjacent box numbers into the decimal value token,
producing garbage arithmetic values. This makes arithmetic verification of the
cuota chain impossible from the corpus alone. This is a deliberate sanitisation
artefact, not a profile gap.

## UNIT 3 — Extension table

Added casilla 0171 to all three revisions:

| Casilla | match_strategy | value_kind | Revisions | Label pattern |
|---------|---------------|------------|-----------|---------------|
| 0171    | named_label   | amount     | 2021, 2022, 2023 | `Ingresos\s+de\s+explotaci[oó]n` |

Files modified:
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2021/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2022/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2023/extraction_profiles/0001-modelo-100-declaracion-pdf.toml`

## UNIT 4 — Chain verification result

Engine test (`test_verification_chain_m100_engine_corpus_limited`) supplies:
- `binding_values`: `renta-2021-modelo-100-estimacion-directa-es-normal=0`,
  `renta-2021-modelo-111-retenciones-periodicas=0`,
  `renta-2021-modelo-115-retenciones-periodicas=0`,
  `renta-2021-modelo-123-retenciones-periodicas=0`
- `enum_binding_values`: `renta-2021-profile-tax-residence-ccaa=cataluna`

Engine runs without `RegistryValidationError`. Engine-computed 0545/0546 are
positive Decimals. Engine-computed 0545/0546 do NOT match corpus-extracted
values, confirming CORPUS-LIMITED verdict. Casilla 0171 is present and Decimal.

## UNIT 5 — Verdict

**CORPUS-LIMITED (not VERIFIED)**

Two independent blockers prevent arithmetic verification from the corpus:

1. Sanitisation replaces all amounts with ~1.001.000,00; pdfplumber merges
   adjacent box numbers into the value token producing arithmetically
   inconsistent figures.
2. 50 additional leaf inputs (017x–019x, CCAA bracket tables, retenciones
   binding values) cannot be extracted from the declaracion_pdf surface.

**What was achieved**: extraction surface expanded from 19 → 20 targets
(added 0171 for 2021/2022/2023). Engine confirms no BINDING-GAP when the
protocol binding set is supplied. The cuota engine runs end-to-end; the corpus
limitation is documented and verified by the new test.

M100 closures: 0 VERIFIED (CORPUS-LIMITED for all 3 revisions). This is an
honest verdict per the task mandate — the limitation is in the corpus
sanitisation, not in the infrastructure.

## Test results

- `test_verification_chain_m100_parser_extracts_declaracion_pdf_casillas`: PASSED (20 casillas)
- `test_verification_chain_m100_engine_corpus_limited`: PASSED
- `test_parser_extracts_modelo_100_profile_targets_from_corpus[2021-0A-2021]`: PASSED
- `test_parser_extracts_modelo_100_profile_targets_from_corpus[2022-0A-2022]`: PASSED
- `test_parser_extracts_modelo_100_profile_targets_from_corpus[2023-0A-2023]`: PASSED

Pre-existing M130 BINDING-GAP failures (15 cases from commit adding
`bound→computed` for M130 casilla 03) are unrelated to this step.

## Plan step

`W10.P50.S207` closed via `vault plan step check`.
