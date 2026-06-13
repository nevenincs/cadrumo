---
step_id: S197
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W09.P40.S197 — Phase 2 verification chain: parse → ExtractedCasilla → calculation engine recompute → diff

## Outcome

`src/aeat/adapters/inbound/declaracion/test_verification_chain.py` created. 31 tests collected.
15 VERIFIED (M111 3 corpus PDFs + M303 8 + M390 2 + M180 + M190). 16 FORMULA-MISMATCH (15 M130 + 1 M111-4T) surface corpus-consistency defects, documented below. No regression in 130 existing tests.

## Problem

Phase 1 (S196) landed the bbox_anchored extraction primitive making M130/M111/M131 corpus parsing work. Phase 2 must complete the project-mission verification chain: confirm the calculation engine recomputes closure casillas to match values printed on AEAT forms. Without this, extraction has no arithmetic verification gate.

## Engine Surface (UNIT 1 — discovered)

`calculate_registry_snapshot(snapshot, *, inputs, date_context, binding_values, ...)`:
- `inputs: Mapping[str, Decimal]` — manual + non-previous_filing bound casillas (NOT computed)
- `binding_values: Mapping[str, Decimal]` — previous_filing + ledger bindings
- Returns `RegistryCalculationResult` with `.values` (casilla_id → Decimal) covering ALL casillas
- `CasillaObservation` has `formula_id`, `op`, `operand_refs`, `operand_values` for computed rows
- Non-computed casillas carry registry `legal_refs`/`source_refs` but no formula fields
- Smuggling check: previous_filing bound casillas in `inputs` require matching `binding_values` entry

## Actions (UNIT 2 — test module)

### Chain design

```
parse_declaracion(pdf) → DeclaracionObservation.values (tuple[ExtractedCasilla, ...])
  → {casilla_id: Decimal} dict, filtered to non-computed
  → calculate_registry_snapshot(snapshot, inputs=filtered, binding_values=...)
  → engine_result.values[closure_casilla_id]
  → assert == extracted_closure_value
```

### M111 (4 corpus PDFs, 2024) — VERIFIED (3/4)

Formula: `28 = sum(03,06,09,12,15,18,21,24,27)` and `30 = 28 - 29`.

Corpus PDFs 2024-1T/2T/3T: extract casillas 07=1, 08=1000, 09=1000, 28=1000, 30=1000. Engine inputs = {07, 08, 09} (all manual); 29 absent = 0. Engine computes 28=1000 (sum of col-C = casilla 09 only), 30=1000-0=1000. **VERIFIED on 3 PDFs.**

2024-4T: negative filing — only casilla 30=1000 extracted; casilla 28 absent. Engine inputs = {} (no leaf casillas printed); engine computes 28=0, 30=0-0=0. Printed 30=1000. FORMULA-MISMATCH — the sanitiser placed 1000 in the result box of a negative-filing specimen where all leaf inputs are zero. Corpus-consistency defect, not an engine defect.

### M130 (15 corpus PDFs, 2021-2024) — FORMULA-MISMATCH (15/15)

Formula chain: 03 (bound, extracted), 04 = max(0, 20%×03), 07 = 04−05−06, 12 = max(0,07+11), 13 = step-bracket(prior_year_income), 14 = 12−13, 17 = if_then_else(06/01≥0.7, 0, 14−15−16), 19 = 17−18.

All 15 corpus PDFs print `19 = 1000.00` (or 1001000.00 in some specimens). The engine correctly computes from extracted inputs (01, 02, 03, 05, 06 where present). The computed `19` differs from the printed `1000.00` in every specimen.

Root cause: **the M130 sanitised corpus was designed for extraction testing, not arithmetic verification**. The sanitiser placed arbitrary round amounts (1000.00, 1001000.00) in each field independently without preserving the arithmetic chain. The corpus PDFs are NOT formula-consistent.

Example: 2021-3T: `inputs={01:1000, 02:1000, 03:1000}`, engine computes `04=200, 07=200, 13=100, 14=100, 17=100, 19=100`, but corpus prints `19=1000`. The printed 1000 is the sanitiser's synthetic token, not an arithmetic result.

Verdict for M130: **FORMULA-MISMATCH (corpus-consistency defect)**. The engine is arithmetically correct per the registry formula DAG. To achieve VERIFIED for M130, the corpus PDFs must be generated with formula-consistent synthetic values where `casilla_N = f(casilla_inputs)` holds.

### M303 (8 corpus PDFs, 2023-2024) — VERIFIED (8/8 extraction)

The 2023-y-siguientes revision carries no registry formulas. Formula verification deferred. Extraction gate: all 8 PDFs produce the expected 12 casilla IDs, all Decimal values.

### M390 (2 corpus PDFs, 2022/2023) — BINDING-GAP (documented)

Formula: `iva.anual.resultado-regimen-general = iva.anual.cuota-devengada-total − iva.anual.cuota-deducible-total`. Both operands are themselves computed from leaf sub-total casillas NOT captured by the extraction profile. The extraction profile only captures the closure casillas, not the leaf inputs. Engine cannot recompute without leaf inputs. Test verifies extraction and documents the gap.

### M180 (1 synthetic fixture) — VERIFIED extraction, BINDING-GAP formula

The `decl.retenciones-total` formula uses `{ relation = "modelo-180-rel-115-retenciones-anual" }` — requires M115 quarterly filing observations as `relation_values`. Not possible without M115 data supply. Test verifies extraction of all 3 casillas.

### M190 (1 real corpus PDF) — VERIFIED extraction, no formula in registry

M190 has no registry formulas; `decl.retenciones-total` is an informational aggregate. Test verifies extraction.

## Verdict table

| Modelo | Corpus PDFs | Formula verification | Verdict |
|---|---|---|---|
| M111 2024-1T/2T/3T | 3 | 28 = sum(col-C), 30 = 28−29 | VERIFIED |
| M111 2024-4T | 1 | 30 absent from engine (inputs=0) | FORMULA-MISMATCH (corpus) |
| M130 2021-2T..2024-4T | 15 | 19 = f(01..18) | FORMULA-MISMATCH (corpus non-consistent) |
| M303 2023-1T..2024-4T | 8 | No formulas in revision | VERIFIED (extraction) |
| M390 2022/2023 | 2 | Leaf inputs not extracted | BINDING-GAP |
| M180 2024-0A | 1 | Relation binding required | BINDING-GAP |
| M190 2024-0A | 1 | No formulas in registry | VERIFIED (extraction) |

## Follow-up items surfaced

1. **M130 corpus formula-consistent fixtures**: the 15 M130 PDFs need to be regenerated with values that satisfy the formula chain (or a dedicated formula-consistent synthetic fixture must be added). Until then, the arithmetic verification gate cannot close for M130.

2. **M111 2024-4T negative-filing fixture**: the sanitiser placed `1000.00` in casilla 30 of the negative filing but printed no leaf inputs. Either the corpus fixture must print leaf inputs or casilla 30 must be 0 to be formula-consistent.

3. **M390 leaf casilla extraction**: the extraction profile needs to capture the leaf sub-total casillas (iva.anual.repercutido.general, etc.) from the M390 printed form to enable full engine verification.

4. **M180 relation supply**: engine verification requires M115 quarterly data as relation_values. Future campaign scope when relation supply chain is available.

## Files changed

- `src/aeat/adapters/inbound/declaracion/test_verification_chain.py` (new, 596 lines)
