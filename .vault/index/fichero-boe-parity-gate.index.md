---
generated: true
tags:
  - '#index'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - '[[2026-07-01-fichero-boe-parity-gate-P01-S01]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P01-S02]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P01-S03]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P02-S04]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P02-S05]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P02-S06]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P02-S07]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P03-S08]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P03-S11]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P04-S15]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P04-S17]]'
  - '[[2026-07-01-fichero-boe-parity-gate-P04-S18]]'
  - '[[2026-07-01-fichero-boe-parity-gate-adr]]'
  - '[[2026-07-01-fichero-boe-parity-gate-plan]]'
  - '[[2026-07-01-fichero-boe-parity-gate-research]]'
  - '[[2026-07-02-fichero-boe-parity-gate-audit]]'
---

# `fichero-boe-parity-gate` feature index

Auto-generated index of all documents tagged with `#fichero-boe-parity-gate`.

## Documents

### adr

- `2026-07-01-fichero-boe-parity-gate-adr` - `fichero-boe-parity-gate` adr: `automatic casilla-completeness parity gate on the fichero-BOE export` | (**status:** `accepted`)

### audit

- `2026-07-02-fichero-boe-parity-gate-audit` - `fichero-boe-parity-gate` audit: `fichero-BOE parity gate execution status`

### exec

- `2026-07-01-fichero-boe-parity-gate-P01-S01` - Add a completeness_manifest field to RegistryModeloSubview
- `2026-07-01-fichero-boe-parity-gate-P01-S02` - Populate completeness_manifest in _subview_from_snapshot from snapshot.revision.completeness_manifest
- `2026-07-01-fichero-boe-parity-gate-P01-S03` - Roundtrip-test that the export subview carries the revision completeness manifest
- `2026-07-01-fichero-boe-parity-gate-P02-S04` - Widen the rendered casilla-set derivation to enumerate every casilla-bearing field kind that reaches disk
- `2026-07-01-fichero-boe-parity-gate-P02-S05` - Add a helper for the manifest required set restricted to casillas representable in an applicable non-suppressed record, carrying number, segmento and record-order metadata
- `2026-07-01-fichero-boe-parity-gate-P02-S06` - Unit-test the rendered-set enumeration across CASILLA, BINDING-row and COMPUTED field kinds
- `2026-07-01-fichero-boe-parity-gate-P02-S07` - Unit-test the applicable-required restriction drops disposition-suppressed casillas
- `2026-07-01-fichero-boe-parity-gate-P03-S08` - Insert a pre-write presence assertion in export_draft that required-applicable casillas are a subset of the on-disk rendered set, raising a hard FilingExportError before write_bytes
- `2026-07-01-fichero-boe-parity-gate-P03-S11` - Make the panic loud and explicit by enumerating every drifted casilla with expected-versus-actual number, segmento, order and presence in the error
- `2026-07-01-fichero-boe-parity-gate-P04-S15` - Add an offline fichero-BOE parity test asserting required-applicable casillas reach disk across export-capable covered modelos
- `2026-07-01-fichero-boe-parity-gate-P04-S17` - Add a disposition-suppressed case proving the applicable restriction prevents a false panic on a non-refund draft
- `2026-07-01-fichero-boe-parity-gate-P04-S18` - Add an anti-tautology drift case mutating a rendered field number or order and asserting the gate panics

### plan

- `2026-07-01-fichero-boe-parity-gate-plan` - `fichero-boe-parity-gate` plan

### research

- `2026-07-01-fichero-boe-parity-gate-research` - `fichero-boe-parity-gate` research: `fichero-BOE casilla-completeness parity gate`
