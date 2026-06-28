---
tags:
  - '#plan'
  - '#modelo-export-evidence-parity'
date: '2026-06-03'
modified: '2026-06-03'
tier: L3
related:
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
  - '[[2026-06-03-modelo-export-evidence-parity-research]]'
  - '[[2026-06-03-ledger-google-live-export-plan]]'
---








# `modelo-export-evidence-parity` `ledger-evidence-bundled modelo calculation + export parity` plan

## Wave `W01` - Foundational ledger-evidence record + capture

Extend the snapshot layer with a typed LedgerFilingEvidence record (contributor projections + manual fact basis) pegged to the revision's snapshot fingerprint, captured at verify time, persisted in the encrypted revision envelope with strict roundtrip + no-silent-omission guards.


### Phase `W01.P01` - Evidence domain record + verify-time capture

Pure domain record + application capture + revision peg + roundtrip.

- [x] `W01.P01.S01` - LedgerFilingEvidence domain record: typed contributor projection (tax facts + legal_refs + attachment/doc-link ids) + manual fact-basis entries, pegged to snapshot_fingerprint; `src/aeat/domain/modelos/_ledger_filing_snapshot.py`.
- [x] `W01.P01.S02` - Verify-time capture: project source_transaction_ids + operator casilla inputs into typed evidence (single catalogue load, alongside fingerprint capture); `src/aeat/application/aggregation/_ledger_filing_snapshot.py`.
- [x] `W01.P01.S03` - Peg evidence onto CalculationRevision and wire capture into verify_modelo_revision; `src/aeat/application/modelo/_actions.py`.
- [x] `W01.P01.S04` - Strict encrypted-storage roundtrip + anti-tautology test (every defaultable field non-default; `mutate-then-reload inequality); `src/aeat/domain/modelos/test_ledger_filing_evidence_roundtrip.py`.
- [x] `W01.P01.S05` - Capture guard: bundled evidence contributor set equals the fingerprint snapshot set (no silent omission); `src/aeat/application/aggregation/_ledger_filing_snapshot.py`.

## Wave `W02` - Evidence in the offline export

Add a SheetExportPlan evidence facet + an Evidencia tab in the offline xls + a machine-readable evidence sidecar; refuse exporting a ledger-derived revision that carries neither bundled evidence nor a resolvable reference.

### Phase `W02.P02` - Evidencia surface + export gate

Plan facet, xls Evidencia tab, sidecar, unevidenced-export refusal.

- [x] `W02.P02.S06` - SheetExportPlan evidence facet: per-casilla contributing rows + manual basis as typed plan records; `src/aeat/application/storage/calc_sheets/_records.py`.
- [x] `W02.P02.S07` - Render an Evidencia tab in the offline xls workbook from the evidence facet; `src/aeat/application/ledger/_workbook_export.py`.
- [x] `W02.P02.S08` - Emit a machine-readable evidence sidecar alongside the exported artefact; `src/aeat/application/ledger/_workbook_export.py`.
- [x] `W02.P02.S09` - Refuse exporting a ledger-derived revision that carries neither bundled evidence nor a resolvable reference; `src/aeat/application/modelo/_actions.py`.
- [x] `W02.P02.S10` - Offline export evidence roundtrip test (export -> read back -> evidence reconstitutes the casilla basis); `src/aeat/entrypoints/cli/test_modelo_export_evidence.py`.

## Wave `W03` - Uniform workbook UX + official-parity gate

Typed presentation facets (number formats by data_type, section-header styling, explicit labelled start/final anchors) rendered identically offline and online, plus a registry-grounded parity gate (casilla set, numbering, segmento, section order, live-formula presence).

### Phase `W03.P03` - Presentation facets

Number formats, section headers, start/final anchors as typed plan facets.

- [x] `W03.P03.S11` - Number-format plan facet by CasillaDefinition.data_type (money/integer/percentage); `src/aeat/application/storage/calc_sheets/_records.py`.
- [x] `W03.P03.S12` - Section-header styling facet derived from CasillaDefinition.section; `src/aeat/application/storage/calc_sheets/_engine.py`.
- [x] `W03.P03.S13` - Explicit labelled start (Entradas opening) and final (resultado/cuota) anchor cells; `src/aeat/application/storage/calc_sheets/_engine.py`.

### Phase `W03.P04` - Official-parity gate

Registry-grounded structural parity + live-formula + offline/online conformance.

- [x] `W03.P04.S14` - Parity gate: exported casilla set equals completeness-manifest required set (number + segmento) and section order follows registry declaration; `src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py`.
- [x] `W03.P04.S15` - Assert every computed casilla carries a live spreadsheet formula; `src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py`.
- [x] `W03.P04.S16` - Offline/online renderer conformance: one plan renders structurally identical xls + Sheets grids; `src/aeat/application/storage/calc_sheets/test_modelo_export_parity.py`.

## Wave `W04` - Per-modelo coverage rollout

Enroll each supported ledger-fed modelo (M303/M390, M130, M100, M200, ...) into evidence-bundling + parity, with an honest per-modelo coverage report (no implied parity beyond what the completeness manifest backs).

### Phase `W04.P05` - Supported-modelo enrolment

Per-modelo evidence + parity coverage with honest reporting.

- [x] `W04.P05.S17` - Enroll M303 + M390 (IVA) into evidence-bundling + parity; `src/aeat/application/storage/calc_sheets/`.
- [x] `W04.P05.S18` - Enroll M130 (pagos fraccionados actividad) into evidence-bundling + parity; `src/aeat/application/storage/calc_sheets/`.
- [x] `W04.P05.S19` - Enroll M100 (renta) into evidence-bundling + parity; `src/aeat/application/storage/calc_sheets/`.
- [x] `W04.P05.S20` - Enroll M200 (sociedades) into evidence-bundling + parity; `src/aeat/application/storage/calc_sheets/`.
- [x] `W04.P05.S21` - Honest per-modelo coverage report (parity/evidence status; `no implied parity beyond manifest backing); `src/aeat/application/storage/calc_sheets/`.

## Wave `W05` - Offline/online export parity

The online Sheets export renders formatting + start/final + Evidencia identically to offline; an offline/online evidence-identical assertion locks parity. The live network push itself remains tracked in the ledger-google-live-export follow-up plan.

### Phase `W05.P06` - Sheets parity with offline

Online renders identically; evidence-identical assertion; live push deferred to follow-up.

- [x] `W05.P06.S22` - Sheets apply renders number formats + start/final + Evidencia identically to the offline xls; `src/aeat/adapters/outbound/google/_calc_sheets_apply.py`.
- [x] `W05.P06.S23` - Offline/online evidence-identical assertion (same revision -> byte-equal evidence surface); `src/aeat/adapters/outbound/google/`.
- [x] `W05.P06.S24` - Reference the live network push to the ledger-google-live-export follow-up plan (no live write here); `src/aeat/application/storage/calc_sheets/`.

## Description


## Steps







## Parallelization


## Verification

