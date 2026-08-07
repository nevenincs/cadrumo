---
generated: true
tags:
  - '#index'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1d6e9ce4dda88eb29b8fefc5e025a96dcb3e13eb2084d72ce0414f1314de1872'
related:
  - '[[2026-08-07-aeat-liabilities-sanciones-P01-S01]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P01-S02]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P01-S03]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P02-S04]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P02-S05]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P02-S06]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P02-S07]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P03-S08]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P03-S09]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-adr]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-plan]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-research]]'
---

# `aeat-liabilities-sanciones` feature index

Auto-generated index of all documents tagged with `#aeat-liabilities-sanciones`.

## Documents

### adr

- `2026-08-07-aeat-liabilities-sanciones-adr` - `aeat-liabilities-sanciones` adr: `Deudas y sanciones: read-only liability register, never a calculation input` | (**status:** `accepted`)

### exec

- `2026-08-07-aeat-liabilities-sanciones-P01-S01` - Add the closed ObjetoTributario StrEnum (interes de demora, recargo de apremio, sancion, liquidacion, other) to core, never reused or widened from PostFilingEventKind, verified by a new unit test asserting the closed member set
- `2026-08-07-aeat-liabilities-sanciones-P01-S02` - Add the closed Direccion StrEnum (owed, refundable) to core as its own typed axis rather than a sign, mirroring the ledger contract amount-is-magnitude convention, verified by a unit test
- `2026-08-07-aeat-liabilities-sanciones-P01-S03` - Add the Deuda adapter schema model in a new _deudas.py module mirroring Expediente placement and STRICT_FROZEN_CONFIG, with clave_liquidacion, objeto_tributario, importe_pendiente as a non-negative Decimal, direccion, periodo, situacion as a bounded str following the Declaracion.estado precedent (never a StrEnum), and mode Literal read, verified by a model validation unit test
- `2026-08-07-aeat-liabilities-sanciones-P02-S04` - Add the LIVE_DEUDAS_SNAPSHOT_NAMESPACE bucket-scoped namespace constant beside LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE
- `2026-08-07-aeat-liabilities-sanciones-P02-S05` - Add DeudasCapture, PersistedDeudasSnapshot, deudas_snapshot_object_key and _derive_snapshot_id mirroring the ExpedientesCapture/PersistedExpedientesSnapshot pattern exactly
- `2026-08-07-aeat-liabilities-sanciones-P02-S06` - Add DeudasService extending StatelessSnapshotService with capture, list_snapshots, show and latest verbs, structurally read-only by construction with no method that mutates AEAT state
- `2026-08-07-aeat-liabilities-sanciones-P02-S07` - Write the strict roundtrip test against a real SecureObjectRepository, real key provider and real SQLite engine, populate every defaultable field non-default, assert strict pydantic equality, then the anti-tautology proof deleting a persisted field on disk and asserting reload refusal
- `2026-08-07-aeat-liabilities-sanciones-P03-S08` - Add the deudas read-landing guard modelled on the censal reader _assert_read_landing, shipped with an empty refusing _DEUDAS_READ_PATH_PREFIXES tuple so it fails closed by construction before any fetch function exists
- `2026-08-07-aeat-liabilities-sanciones-P03-S09` - Write the guard unit test proving refusal on every synthetic landing URL including a payment-shaped and an aplazamiento-shaped URL against the empty prefix set, then a mutation proof populating one real-looking prefix and confirming it permits only that prefix

### plan

- `2026-08-07-aeat-liabilities-sanciones-plan` - `aeat-liabilities-sanciones` plan

### research

- `2026-08-07-aeat-liabilities-sanciones-research` - `aeat-liabilities-sanciones` research: `Sanciones, recargos and deudas pendientes: gap and options`
