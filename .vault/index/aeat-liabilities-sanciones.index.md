---
generated: true
tags:
  - '#index'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:ca6a3e73799705ae57da55715c03b23920dbba180de07d18645c0434af1777e8'
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
  - '[[2026-08-07-aeat-liabilities-sanciones-P05-S13]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P05-S14]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P05-S15]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P05-S16]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P05-S17]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P05-S18]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P06-S19]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P06-S20]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P06-S21]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P06-S22]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P07-S23]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P08-S25]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P08-S26]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P08-S27]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P08-S28]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-P08-S29]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-adr]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-plan]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-research]]'
  - '[[2026-08-12-aeat-liabilities-sanciones-p05-p06-closeout-honesty-audit]]'
  - '[[2026-08-13-aeat-liabilities-sanciones-notification-documents-adr]]'
---

# `aeat-liabilities-sanciones` feature index

Auto-generated index of all documents tagged with `#aeat-liabilities-sanciones`.

## Documents

### adr

- `2026-08-07-aeat-liabilities-sanciones-adr` - `aeat-liabilities-sanciones` adr: `Deudas y sanciones: read-only liability register, never a calculation input` | (**status:** `accepted`)
- `2026-08-13-aeat-liabilities-sanciones-notification-documents-adr` - `aeat-liabilities-sanciones` adr: `Notification documents: fetch, encrypt, parse deterministically` | (**status:** `accepted`)

### audit

- `2026-08-12-aeat-liabilities-sanciones-p05-p06-closeout-honesty-audit` - `aeat-liabilities-sanciones` audit: closeout honesty review after the live discovery session

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
- `2026-08-07-aeat-liabilities-sanciones-P05-S13` - BLOCKED on an operator-authorised live specimen capture of Consultar deudas: observe the real situacion label vocabulary and confirm the str Field length bound is adequate, per the Declaracion.estado precedent, with no type change since situacion stays str
- `2026-08-07-aeat-liabilities-sanciones-P05-S14` - BLOCKED on the same specimen: write walk_deudas_consulta mapping the real DOM to Deuda rows, verified by a parse test against the captured fixture with sensitive fields never committed to the repo
- `2026-08-07-aeat-liabilities-sanciones-P05-S15` - BLOCKED on the same specimen: populate the guard real allowed_path_prefixes from the captured consulta path, verified by the guard test refusing every known payment and aplazamiento path observed in the specimen
- `2026-08-07-aeat-liabilities-sanciones-P05-S16` - BLOCKED on the same specimen: wire aeat app live deudas pull calling the walker and DeudasService capture, named pull never capture or refresh or fetch or sync per the CLI contract
- `2026-08-07-aeat-liabilities-sanciones-P05-S17` - Enroll app live deudas pull in PROFILE_BOUND_WRITE_VERB_PATHS with a comment stating it persists a captured snapshot to bucket storage, verified by test_root_fallback_guard_predicate_covers_profile_bound_mutations extended with the new entry
- `2026-08-07-aeat-liabilities-sanciones-P05-S18` - Add deudas pull to the operator-orientation agent-harness document alongside expedientes pull and notifications pull in the same commit as the verb, verified by test_documented_command_conformance
- `2026-08-07-aeat-liabilities-sanciones-P06-S19` - BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half of this row's blocker is discharged as of 2026-08-10: the consolidated Ley 58/2003 is bundled with its extracted sidecar, so art. 28 is present and a corpus_ref has a target. Author the legal-catalogue entry for LGT art. 28, recargo del periodo ejecutivo and recargo de apremio, pointing corpus_ref at the bundled consolidated file at anchor a28 rather than hand-authoring a duplicate excerpt. The reviewer cross-checks every percentage against live BOE before stamping, because the standing grounding rule distrusts bundled text on a number
- `2026-08-07-aeat-liabilities-sanciones-P06-S20` - BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 178 through 212 are all present in the bundled consolidated Ley 58/2003 and in its sidecar. Author the legal-catalogue entry for the regimen sancionador focused on the arts. 191-197 pecuniaria proporcional bands, pointing corpus_ref at the bundled consolidated file. Every band percentage is cross-checked against live BOE by the reviewer before stamping
- `2026-08-07-aeat-liabilities-sanciones-P06-S21` - BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 65 and 82 are present in the bundled consolidated Ley 58/2003. Author the legal-catalogue entry for aplazamiento y fraccionamiento del pago and its garantias, pointing corpus_ref at the bundled consolidated file. Any interest rate the entry carries is cross-checked against live BOE by the reviewer before stamping
- `2026-08-07-aeat-liabilities-sanciones-P06-S22` - BLOCKED on a named human legal reviewer, never an agent stamp. The corpus half is discharged as of 2026-08-10: arts. 163 and 167 through 173 are all present in the bundled consolidated Ley 58/2003. Author the legal-catalogue entry for the procedimiento de apremio, providencia and embargo, pointing corpus_ref at the bundled consolidated file, verified by the legal-entry evidence gate
- `2026-08-07-aeat-liabilities-sanciones-P08-S25` - Add the frozen PersistedNotificationDocument model carrying certificado_id, the AttachmentStore attachment id, pdf_sha256, source_url and fetched_at under STRICT config, exposing NO filesystem path field of any kind, verified by a model validation unit test asserting the field set and that no field name or value carries a path
- `2026-08-07-aeat-liabilities-sanciones-P08-S26` - Add NotificationDocumentService storing the fetched bytes through the encrypted content-addressed AttachmentStore resolved the way application/ledger/_actions_common.py resolves it, delegating to that single-writer primitive rather than re-implementing its write path, verified by a unit test asserting the store receives the bytes and the service opens no second write path
- `2026-08-07-aeat-liabilities-sanciones-P08-S27` - Make a re-store of an already-persisted certificado id a content-addressed no-op returning the existing record with no second attachment write and no re-stamped fetched_at, and refuse with an instructive localised conflict when the same certificado id arrives with a different pdf_sha256, verified by an idempotency test covering the no-op, the field-complete match and the divergent-digest refusal
- `2026-08-07-aeat-liabilities-sanciones-P08-S28` - Write the strict roundtrip test against a real SecureObjectRepository, real key provider, real SQLite engine and real AttachmentStore, populating every defaultable field non-default and asserting strict pydantic equality, then the anti-tautology proof deleting a persisted field on disk and asserting reload refusal
- `2026-08-07-aeat-liabilities-sanciones-P08-S29` - Write the custody gate proving a full fetch-and-store cycle writes the PDF bytes to no filesystem path: run the service against a temporary profile root, assert every file created is an encrypted store artefact and that the plaintext PDF magic bytes appear nowhere on disk, then the mutation proof writing the bytes to a temp file and confirming the gate reds

### plan

- `2026-08-07-aeat-liabilities-sanciones-plan` - `aeat-liabilities-sanciones` plan

### research

- `2026-08-07-aeat-liabilities-sanciones-research` - `aeat-liabilities-sanciones` research: `Sanciones, recargos and deudas pendientes: gap and options`
