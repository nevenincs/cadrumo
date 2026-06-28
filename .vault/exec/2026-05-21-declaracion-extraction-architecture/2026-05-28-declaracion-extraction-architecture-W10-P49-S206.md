---
step_id: S206
date: 2026-05-28
modified: '2026-05-28'
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - "[[2026-05-28-declaracion-extraction-architecture-W10-P48-S205]]"
---

# declaracion-extraction-architecture W10.P49.S206 — verification chain extension

## Objective

Extend `test_verification_chain.py` coverage now that Phase 2 gaps have closed:
M130 corpus regenerated (W10.P45), M390 binding gap fixed (W10.P46), M180
cross-modelo relation verified (W10.P47), M111 2024-4T NEGATIVA handled (W10.P48).

Survey all GROUNDED modelos not yet in the chain, classify readiness, implement
tests, and update the module docstring with the comprehensive per-modelo verdict table.

## UNIT 1 — Readiness survey

| Modelo | Revision | Formulas | declaracion_pdf profile | Fixture | Verdict |
|--------|----------|----------|------------------------|---------|---------|
| M100 | 2021/2022/2023 | yes (complex cuota-chain) | yes (19 casillas) | 3 real PDFs | EXTRACTION-ONLY — profile captures mid-chain computed casillas; leaf inputs (017x series) absent from profile |
| M115 | 2019-y-siguientes | yes (03=percent(02,rate); 05=03-04) | yes (5 casillas) | 1 synthetic PDF | CHAIN-READY |
| M123 | 2019-2023 | yes (06-legacy=03+05; 08-legacy=06-07) | yes (8 casillas) | 1 synthetic PDF | CHAIN-READY |
| M123 | 2024-y-siguientes | yes (03=01+02; 06=04+05; 09=07+08; 12=10+11; 14=12-13) | yes (14 casillas) | 1 synthetic PDF | CHAIN-READY |
| M131 | 2026 | yes (07=02+04+06; 10=07-08-09; 13=10-11-12; 15=13-14) | yes (15 casillas) | 1 synthetic PDF (mislabeled 2024-1T.pdf) | CHAIN-READY + previous_filing binding for casilla 11 |
| M184 | 2015-y-siguientes | none | yes (decl.ejercicio only) | 1 synthetic PDF | EXTRACTION-ONLY |
| M193 | 2024-y-siguientes | yes (cross-modelo M123→M193 relation) | yes (3 casillas) | 1 synthetic PDF | NEEDS-CROSS-MODELO-RELATION |
| M347 | 2008-y-siguientes | none | yes (decl.ejercicio only) | 1 synthetic PDF | EXTRACTION-ONLY |
| M349 | 2020-y-siguientes | none | yes (4 summary casillas) | 1 synthetic PDF | EXTRACTION-ONLY |
| M369 | esquema-union | none | yes (decl.ejercicio + decl.periodo) | 1 synthetic PDF | EXTRACTION-ONLY |
| M720 | 2013-y-siguientes | none | yes (decl.ejercicio only) | 1 synthetic PDF | EXTRACTION-ONLY |
| M840 | 2003-y-siguientes | none | yes (decl.tipo-declaracion + decl.ejercicio) | 1 synthetic PDF | EXTRACTION-ONLY |
| M036 | 2025-02-03-y-siguientes | none | yes | 1 synthetic PDF (2025-0A.pdf) | NOT-CHAIN-READY — registry has no revision for year=2025 period=0A |

## UNIT 2 — Test case additions

### CHAIN-READY tests added

`test_verification_chain_m115_engine_recomputes_retenciones_and_resultado`
- Fixture: `justificantes/115/2024-1T.pdf`
- Inputs: casillas 01 (perceptores), 02 (base), 04 (anteriores)
- Closure: 03 = percent(02, irpf.urban_rental_withholding_rate), 05 = 03 - 04
- Verdict: VERIFIED

`test_verification_chain_m123_engine_recomputes_closure_casillas` (parametrized × 2)
- 2023-1T (2019-2023 revision): closure 06-legacy=03+05, 08-legacy=06-07 — VERIFIED
- 2024-1T (2024-y-siguientes): closure 03=01+02, 06=04+05, 09=07+08, 12=10+11, 14=12-13 — VERIFIED

`test_verification_chain_m131_engine_recomputes_closure_casillas`
- Fixture: `justificantes/131/2024-1T.pdf` (encodes year 2026)
- Binding: modelo-131-2026-resultados-negativos-anteriores = 0 (casilla 11 is previous_filing bound)
- Closure: 07=02+04+06, 10=07-08-09, 13=10-11-12, 15=13-14 — VERIFIED

### NEEDS-CROSS-MODELO-RELATION tests added

`test_verification_chain_m193_parser_extracts_declaracion_pdf_casillas`
- Extraction structure verified: {decl.total-perceptores, decl.base-total, decl.retenciones-total}

`test_verification_chain_m193_engine_recomputes_closure_casillas_from_m123_relation_values`
- Pattern: identical to M180→M115 (W10.P47)
- M123 quarterly observations (4Q, 2024): 03=[2,0,0,0], 06=[2000×4], 09=[380×4]
- sum(03)=2, sum(06)=8000, sum(09)=1520 matches M193 fixture printed values
- Verdict: VERIFIED

### EXTRACTION-ONLY tests added

7 tests covering M100 (3-year loop), M349, M184, M347, M720, M840, M369.
Each verifies: parse succeeds, expected casilla set extracted, all values are Decimal (or str where applicable).

## UNIT 3 — Module docstring updated

Comprehensive per-modelo verdict table added to module docstring with:
- 15 rows (M100, M111, M115, M123, M130, M131, M180, M184, M190, M193, M303, M347, M349, M369, M390, M720, M840)
- Follow-up tasks documented: M100 leaf profile extension, M036 revision gap, M303 formula coverage

## UNIT 4 — Test results

```
test_verification_chain.py 45 passed (161s)
src/aeat/adapters/inbound/declaracion/ 160 passed (333s)
```

Pre-existing 32 tests all green. 13 new tests all green.

## Defects surfaced

- **M036 NOT-CHAIN-READY**: The fixture `justificantes/036/2025-0A.pdf` cannot be parsed
  because the registry has no revision matching `year=2025 period=0A`. The revision
  `2025-02-03-y-siguientes` exists but appears not to satisfy the period selector for `0A`.
  Needs investigation: either extend the revision selector or correct the fixture year.
  No test added (would fail at parse step with a registry resolution error, not an
  extraction gap).

- **M100 EXTRACTION-ONLY residual**: M100 has rich formula coverage (182+ formulas) but
  the declaracion_pdf profile only captures mid-chain and closure casillas, not the deep
  leaf inputs (017x series for actividades-económicas). The parser test passes; the
  formula chain cannot be closed from the current profile.

## ADR amendment

Appended `## 2026-05-28 amendment` block to
`.vault/adr/2026-05-21-declaracion-extraction-architecture-adr.md`
with the comprehensive per-modelo verdict table.

## Commit

`0a64250eb` — test(declaracion-verification-chain): W10.P49.S206 extend chain coverage
