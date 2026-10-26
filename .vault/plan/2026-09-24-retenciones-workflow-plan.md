---
tags:
  - '#plan'
  - '#retenciones-workflow'
date: '2026-09-24'
tier: L1
related:
  - '[[2026-09-21-retenciones-workflow-observation-payment-contract-adr]]'
  - '[[2026-09-23-retenciones-workflow-evidence-capture-scope-adr]]'
modified: '2026-09-24'
body_schema: body-v2
body_hash: 'sha256:4444c741d2bb3b55eeb5424f769cb1c43eeda07cc4af574aa745b0193058be9b'
---

# `retenciones-workflow` plan

Carry Modelo 193 pending-payment and settled-prior-accrual rows from capital withholding into the 2025 export through the one aggregation mechanism.

## Description

Approved 2026-09-24. Basis: the operator's standing authorisation to make changes in this lane, and the coordinator's recorded ordering of the retenciones targets (payroll capture, then capital capture, then the Modelo 193 export); payroll and capital capture have landed.

The phase materialiser in `src/cadrumo/application/aggregation/m193_phase_materialization.py` produces pending and settled-prior-accrual rows but nothing consumes them: the 193 perceptor rows read only the manual 193 window (`withholding_source.py`), captured capital allocations land only in the Modelo 123 quarterly window, and the declarant totals copy Modelo 123 casillas instead of summing the type-2 rows. The 2025 design (HAC/1430/2025, bundled record design pp. 5-7 and 24-26) counts type-2 records, sums them for the declarant totals, and carries the PENDIENTE flag at position 117 and the accrual year at 118-121.

Decision coverage: the observation-payment-contract ADR settles the phase model (keys A, B and D; pending in the accrual year, settled in the payment year) and the evidence-capture-scope ADR settles that the export is wired through the canonical aggregation mechanism with no second summation path. No new decision is needed. Scope stays within those ADRs: pending rows remain limited to 2025 accruals, and extending them to later accrual years needs an ADR amendment first.

S01 and S02 are code; S03 is registry authoring and ships through the coordinator's republish queue; S04 proves the whole path; S05 keeps the filing-export block in place until the official design settles whether the payment-year settled row repeats the withholding amounts, because repeating them would count a withholding already paid through Modelo 123.

S05 outcome, 2026-09-24: not settled, so the block stays. RIRPF art. 94.1 settles that capital withholding arises at exigibility (or earlier payment) and art. 108.1 that it is declared in that period's Modelo 123, so it is declared in the accrual year. The 2025 record design requires full amounts in the accrual-year pendiente record (pp. 24-25) and sums every type-2 record into the declarant totals without exception (pp. 5-7), but states nothing about the amount fields of the payment-year record beyond reporting the recipient (p. 25) and the accrual year at 118-121 (p. 26). No AEAT note or INFORMA entry addresses it, and a search of the DGT binding and general rulings (eight queries, including the pendiente mechanism, the 999999999 placeholder and the accrual-year field) found none either: the nearest, V1292-05 and V4152-16, concern dividend attribution at exigibility and withholding on redistributed unclaimed dividends. The materialiser keeps the literal-design amounts with `filing_export_supported=False`, and S06 makes the open question visible on every settled row. The cited articles were re-read by anchor in the bundled RD 439/2007 extraction (`#a78`, `#a94`, `#a108`), whose units align with their headings; an earlier report of a one-heading offset was a misreading and was withdrawn.

## Steps

- [x] `S01` - add a per perceptor, clave, pending flag and accrual year row grouping plus a type-2 record count and base and withholding sum facts to the withholding bindings; `src/cadrumo/domain/calculations/registry/withholding_bindings.py`.
- [x] `S02` - compose the Modelo 193 annual source from the manual window and materialised pending and settled phase rows read from Modelo 123 retenciones, refusing allocation collisions and emitting contributor provenance; `src/cadrumo/application/aggregation/withholding_source.py`.
- [x] `S03` - rebind the 2025 declarant totals to the type-2 record count and row sums and the perceptor rows to the new grouping, keeping the Modelo 123 relation as a reconciliation check, then queue the republish; `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2025-y-siguientes/revision.toml`.
- [ ] `S04` - prove multi-source rows, exclusions, missing-store advisories, pull and calculate parity and 2025 export byte parity for one pending and one settled row; `src/cadrumo/application/aggregation/tests`.
- [x] `S05` - ground whether the payment-year settled row repeats the withholding amounts, and lift the filing-export block only when the official design settles it; `src/cadrumo/application/aggregation/m193_phase_materialization.py`.
- [x] `S06` - attach a structured advisory naming modelo 193, the base and withholding fields and the missing-authority reason to every settled-prior-accrual row, so the unresolved payment-year amounts reach the handoff instead of reading as settled; `src/cadrumo/application/aggregation/m193_phase_materialization.py`.
- [ ] `S07` - fail closed for a monthly withholding filer: when the canonical obligation schedule makes the filer's Modelo 111 or 123 monthly, refuse capture into a quarterly window and have the 190 and 193 annual sources return a structured refusal naming the modelo, the monthly periods and the reason instead of a quarterly-only total, proven with a monthly filer; `src/cadrumo/application/aggregation/withholding_source.py and the three capture producers`.
- [ ] `S08` - support monthly withholding filers end to end: place captured withholding in the filer's monthly window through the canonical period vocabulary and schedule, read monthly and quarterly windows in the 190 and 193 annual sources, and remove the S07 refusal; `src/cadrumo/application/aggregation and the retencion observations adapter`.
- [x] `S09` - refuse Modelo 193 export at the export boundary while its calculated revision carries a settled-prior-accrual row, with a typed reason and no command action, because the phase row's filing-export flag is read by nothing and so blocks nothing; `src/cadrumo/application/modelo/export.py`.
- [ ] `S10` - refuse local work file for a Modelo 193 revision carrying a settled row with the export gate's check, and add a non-blocking verify finding so the operator learns before exporting or filing; `src/cadrumo/application/modelo filing and verification actions`.
- [ ] `S11` - persist the accrual year on each calculation source reference as an additive optional field so the 193 gates detect settled rows exactly, falling back to the conservative accrual-year rule for revisions without it; `src/cadrumo/domain/modelos calculation revision source references`.

## Parallelization

S01 and S02 can proceed in parallel on disjoint files. S03 depends on S01's grouping and facts existing in code, and its runtime effect waits for the republish. S04 depends on S01 through S03 being published. S05 is independent research and can run at any time, but its code change lands last.

## Verification

- The Modelo 193 calculation for 2025 includes a pending row in its accrual year and a settled row in its payment year from captured capital withholding, through the real resolver and published authority, with no second summation path.
- The declarant's perceptor total equals the type-2 record count and its base and withholding totals equal the type-2 row sums.
- Exclusion cases hold: key C, a same-year payment and a 2026 accrual never produce phase rows; a missing store keeps its advisory.
- Pull and calculate agree, and the 2025 export matches the official record structure byte for byte at positions 117 and 118-121 on 500-byte records.
- Filing export stays blocked unless S05 grounds the settled row's amounts in the official design.
