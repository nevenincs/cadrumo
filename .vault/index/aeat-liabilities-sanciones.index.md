---
generated: true
tags:
  - '#index'
  - '#aeat-liabilities-sanciones'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:da7aa9e404393fdb023bf92036ba9da4c128c50245080f9797623858de3583f1'
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
  - '[[2026-08-07-aeat-liabilities-sanciones-P04-S10]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P04-S11]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P04-S12]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P07-S23]]'
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
- `2026-08-07-aeat-liabilities-sanciones-P04-S10` - Add the deudas CLI entrypoint and its list, view and latest payload models as new OutputSchema subclasses in the existing _app_live_payloads module, mirroring the expedientes payload shapes. Introduces tr help keys, so this row and S11 and S12 land as ONE unit with P07.S23 rather than independently: the codebase-to-locale parity gate is tree-wide and immediate, so the moment a tr key exists in source it must exist in all four catalogues
- `2026-08-07-aeat-liabilities-sanciones-P04-S11` - Wire aeat app live deudas list, view and latest into the app live command group, matching the expedientes latest, list, view verb shape exactly
- `2026-08-07-aeat-liabilities-sanciones-P04-S12` - Add the three new leaves to the reviewed-non-mutating roster as pure reads over persisted snapshots, verified by test_every_app_leaf_is_accounted_for_by_name_independent_census and a new CLI integration test asserting the three verb shapes
- `2026-08-07-aeat-liabilities-sanciones-P07-S23` - Author real es, en, ca and hu values for the new deudas CLI help and label keys via python -m dev.locales set, then scaffold and scaffold --check clean. Lands as ONE unit with P04.S10 through S12 because the codebase-to-locale parity gate is tree-wide and immediate, so no ordering exists in which the CLI rows are green before these values exist in all four catalogues. The original en.yml and hu.yml peer-WIP blocker is discharged

### plan

- `2026-08-07-aeat-liabilities-sanciones-plan` - `aeat-liabilities-sanciones` plan

### research

- `2026-08-07-aeat-liabilities-sanciones-research` - `aeat-liabilities-sanciones` research: `Sanciones, recargos and deudas pendientes: gap and options`
