---
tags:
  - '#plan'
  - '#export-parity'
date: '2026-09-26'
tier: L1
related:
  - '[[2026-09-26-export-parity-adr]]'
  - '[[2026-09-26-export-parity-audit]]'
  - '[[2026-09-07-tuimodelo-export-destinations-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
  - '[[2026-06-03-modelo-export-visual-design-adr]]'
  - '[[2026-09-26-export-parity-calculation-report-adr]]'
  - '[[2026-09-26-export-parity-calculation-summary-pdf-adr]]'
modified: '2026-09-27'
body_schema: body-v2
body_hash: 'sha256:a536cd5f50a52517a2e5d5c89096c432f49fcc52159cc655f192b92d1dbe1505'
---

# `export-parity` plan

## Description

Approved 2026-09-26 by the operator's instruction to audit TUI and CLI export, seed a multi-year synthetic secure store, and treat every discovered gap as owned work; the operator's same-day answers decided the development software identity, testing both cross-year carry lanes, and a calculation-report PDF.

Decision coverage: the development identity is decided in `2026-09-26-export-parity-adr`; destinations, the offline workbook and parity with the online workbook are decided in the accepted destinations, workbook-parity and visual-design records. The CSV casilla table and the calculation-report PDF are decided in `2026-09-26-export-parity-calculation-report-adr`. Registry corrections follow the registry authority flow with grounded evidence.

The live working ledger is the gitignored campaign scratch home; durable findings are appended to `2026-09-26-export-parity-audit`.

## Steps

- [x] `S01` - Stamp envelope-prefixed exports with the graded development software identity so Modelo 303 and 390 export on both surfaces; `src/cadrumo/domain/filing/**, src/cadrumo/application/modelo/**, src/cadrumo/entrypoints/**, docs sequences`.
- [x] `S02` - Make the canonical export parser read filing envelopes and AEAT zero-filled absent slots so every rendered file round-trips; `src/cadrumo/domain/calculations/registry/export_parse.py, fixed_width_codec.py, schema_exports.py`.
- [ ] `S03` - Seed the multi-year synthetic store (profile, ledger, evidence, assets, withholding, modelos 2022-2025) through the public CLI and seal it; `dev/acceptance/export_parity/**`.
- [ ] `S04` - Run the ledger completeness gate over the seeded store and record every unresolved data class as a finding before delegating lanes; `dev/acceptance/export_parity/**`.
- [ ] `S05` - Research, then source Modelo 100 retenciones soportadas per casilla from their legal sources (payer certificates, the ledger's issued-invoice client withholding, the taxpayer's own pagos fraccionados, AEAT datos fiscales through the product's live pull), covering the employee-plus-autonomo case and removing the declarant-as-payer prefills; implemented only after the operator approves the proposed decision (operator direction 2026-09-27); `.vault/research/**, .vault/adr/**, src/cadrumo/_data/registry/aeat/modelos/100/**, src/cadrumo/application/**`.; `.vault/research/**, .vault/adr/**, src/cadrumo/_data/registry/aeat/modelos/100/**, src/cadrumo/application/**`.
- [ ] `S06` - Author the activity-asset amortization parameters on a 2022 baseline, keying only the genuine yearly divergences (2023 DA18 accelerated amortization, 2024 free depreciation) through the dev/registry tooling, so every supported year's asset charges resolve (operator direction 2026-09-27); `src/cadrumo/_data/registry/aeat/**`.; `src/cadrumo/_data/registry/aeat/**`.
- [ ] `S17` - Let an in-year asset purchase recorded in the ledger keep its IVA deduction while its Renta and Modelo 130 expense comes only from the asset register's claim, without a competing depreciation treatment; `src/cadrumo/application/**, src/cadrumo/_data/registry/aeat/**`.; `src/cadrumo/application/**, src/cadrumo/_data/registry/aeat/**`.
- [ ] `S16` - Give exempt and out-of-scope inputs (exempt premiums, RETA quotas) a grounded IVA treatment that needs no deduction kind, and a supported write path for a bien de inversion's investment asset identity, so 303/390 calculate over a complete autonomo ledger; `src/cadrumo/domain/iva/**, src/cadrumo/application/**, src/cadrumo/_data/registry/aeat/**`.; `src/cadrumo/domain/iva/**, src/cadrumo/application/**, src/cadrumo/_data/registry/aeat/**`.
- [ ] `S15` - Refuse or block filing grade for an annual withholding summary (190/180/193) with no per-perceptor detail when the ledger holds evidence of practised withholding, grounded in the Modelo 190 order and RIRPF art. 108; `src/cadrumo/application/**, src/cadrumo/domain/modelos/**`.; `src/cadrumo/application/**, src/cadrumo/domain/modelos/**`.
- [ ] `S14` - Author the withholding recognition rules on a 2022 baseline in place of the hard-coded 2025-only year gate, grounded in RIRPF art. 78 (operator direction 2026-09-27); `src/cadrumo/application/aggregation/**, src/cadrumo/_data/registry/aeat/**`.; `src/cadrumo/application/aggregation/**, src/cadrumo/_data/registry/aeat/**`.
- [ ] `S13` - Audit the registry for conformance with delta keying against a baseline, filing-year keying and temporal projection using the dev/registry tooling, then rectify every nonconformity per modelo with one writer, starting with Modelo 100's 2022/2023 coverage (operator direction 2026-09-27); `src/cadrumo/_data/registry/aeat/**, scratch/export-parity/reports/**`.; `src/cadrumo/_data/registry/aeat/**, scratch/export-parity/reports/**`.
- [x] `S07` - Introduce the typed export destination contract and refuse to overwrite an existing export file; `src/cadrumo/application/modelo/**, src/cadrumo/entrypoints/**`.
- [x] `S08` - Wire the offline XLSX workbook destination from the shared calc-sheets plan; `src/cadrumo/adapters/outbound/**, src/cadrumo/application/storage/calc_sheets/**, src/cadrumo/entrypoints/**`.
- [ ] `S09` - Build the typed calculation-report builder with traceability facts and the CSV destination, and wire it to the CLI and TUI; the PDF moves to its own designed artefact (operator direction 2026-09-26); `src/cadrumo/application/**, src/cadrumo/entrypoints/**`.; `src/cadrumo/application/**, src/cadrumo/entrypoints/**`.
- [ ] `S12` - Design the calculation-summary PDF as its own artefact (human-readable and machine-readable, embedded data, calculation certification, metadata hash identifiers traceable to the encrypted store), record it as a proposed ADR amending the calculation-report decision, and implement it only after operator acceptance; `.vault/research/**, .vault/adr/**, src/cadrumo/application/**, src/cadrumo/adapters/outbound/**, src/cadrumo/entrypoints/**`.; `.vault/research/**, .vault/adr/**, src/cadrumo/application/**, src/cadrumo/adapters/outbound/**, src/cadrumo/entrypoints/**`.
- [ ] `S10` - Give the TUI export the widened public result so it states evidence status, completeness and identity grade; `src/cadrumo/application/modelo/operation_definitions.py, src/cadrumo/entrypoints/tui/**`.
- [ ] `S11` - Run CLI and TUI parity lanes per modelo family and year for every format, including both cross-year carry lanes, and render the export matrix; `scratch/export-parity/**, dev/acceptance/export_parity/**`.

## Parallelization

S05 and S06 edit different Modelo 100 families and may run in parallel with S07 and S08; each has one writer. S09 follows S07. S11 lanes run in parallel on independent copies of the sealed store; only the orchestrator writes the finding ledger and commits.

## Verification

Each Step's owning tests with `-m "unit or integration"`, `ruff` and `ty` on changed files, `just check-types`, docs sequences through their generator, and registry Steps through the dev/registry checks. The campaign closes when every modelo in the exit condition exports in every format on both surfaces, byte-identical across surfaces and parsing to the oracle, or each remaining gap is a recorded, operator-acknowledged limitation.
