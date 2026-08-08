---
tags:
  - '#plan'
  - '#aeat-liabilities-sanciones'
date: '2026-08-07'
modified: '2026-08-08'
body_hash: 'sha256:e78428f479962ae0129c1df319ed47f3e60b1af8b25c1b5301e7d64b8b248896'
tier: L2
related:
  - '[[2026-08-07-aeat-liabilities-sanciones-adr]]'
  - '[[2026-08-07-aeat-liabilities-sanciones-research]]'
---

# `aeat-liabilities-sanciones` plan

## Description

Executes `2026-08-07-aeat-liabilities-sanciones-adr`: a read-and-display
`Deuda` register mirroring `ExpedientesService` structurally, never a
calculation input, gated by a fail-closed read-landing guard given its
adjacency to AEAT's payment flow. Grounded throughout by
`2026-08-07-aeat-liabilities-sanciones-research`.

Phases P01-P04 are buildable and independently verifiable today: the domain
type and its closed enums, the snapshot service, the guard skeleton (shipped
refusing by construction), and the list/view/latest CLI read surface. None of
them touch AEAT, none of them need a specimen, and none of them need new
legal grounding, because they display AEAT's own reported figures without
interpreting them.

Phase P05 is blocked end-to-end on an operator-authorised live specimen
capture of "Consultar deudas" and is not startable before then; it carries
the DOM parse function, the guard's real allowed prefixes, the `pull` verb,
its write-guard enrollment, and the harness sweep together because each
depends on the same capture. Phase P06 is blocked on named human legal
reviewers per `aeat-calculation-grounding`'s human-reviewed mandate; an agent
must never author these entries. Phase P07 is blocked on the in-flight
`en.yml`/`hu.yml` peer WIP landing in the shared worktree.

Divergence reconciliation against filed declarations (the ADR's rejected
option 2) is out of scope for this plan and requires its own ADR once P05
ships and a real specimen exists to validate a comparison against.

## Steps

### Phase `P01` - Deuda domain type and closed enums

Land the Deuda adapter schema model and its closed ObjetoTributario and Direccion StrEnums in core, buildable and testable with no AEAT specimen and no new legal grounding. situacion ships a bounded str from birth, following the Declaracion.estado precedent, not a StrEnum, because it mirrors an AEAT free-text listing label the app does not control rather than an axis the app defines.

- [x] `P01.S01` - Add the closed ObjetoTributario StrEnum (interes de demora, recargo de apremio, sancion, liquidacion, other) to core, never reused or widened from PostFilingEventKind, verified by a new unit test asserting the closed member set; `src/cadrumo/core`.
- [x] `P01.S02` - Add the closed Direccion StrEnum (owed, refundable) to core as its own typed axis rather than a sign, mirroring the ledger contract amount-is-magnitude convention, verified by a unit test; `src/cadrumo/core`.
- [x] `P01.S03` - Add the Deuda adapter schema model in a new _deudas.py module mirroring Expediente placement and STRICT_FROZEN_CONFIG, with clave_liquidacion, objeto_tributario, importe_pendiente as a non-negative Decimal, direccion, periodo, situacion as a bounded str following the Declaracion.estado precedent (never a StrEnum), and mode Literal read, verified by a model validation unit test; `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.

### Phase `P02` - DeudasService snapshot family

Mirror ExpedientesService/PersistedExpedientesSnapshot/ExpedientesCapture exactly for deudas, with a bucket-scoped namespace and content-addressed snapshot ids, roundtrip-tested against a synthetic capture fixture.

- [x] `P02.S04` - Add the LIVE_DEUDAS_SNAPSHOT_NAMESPACE bucket-scoped namespace constant beside LIVE_EXPEDIENTES_SNAPSHOT_NAMESPACE; `src/cadrumo/adapters/persistence/storage`.
- [x] `P02.S05` - Add DeudasCapture, PersistedDeudasSnapshot, deudas_snapshot_object_key and _derive_snapshot_id mirroring the ExpedientesCapture/PersistedExpedientesSnapshot pattern exactly; `src/cadrumo/application/live/_deudas.py`.
- [x] `P02.S06` - Add DeudasService extending StatelessSnapshotService with capture, list_snapshots, show and latest verbs, structurally read-only by construction with no method that mutates AEAT state; `src/cadrumo/application/live/_deudas.py`.
- [x] `P02.S07` - Write the strict roundtrip test against a real SecureObjectRepository, real key provider and real SQLite engine, populate every defaultable field non-default, assert strict pydantic equality, then the anti-tautology proof deleting a persisted field on disk and asserting reload refusal; `src/cadrumo/application/live/tests/test_deudas_service.py`.

### Phase `P03` - Fail-closed read-landing guard skeleton

Land the guard function modelled on the censal reader's _assert_read_landing, shipped with an empty/refusing allowed_path_prefixes tuple so it fails closed by construction before any adapter fetch function exists.

- [x] `P03.S08` - Add the deudas read-landing guard modelled on the censal reader _assert_read_landing, shipped with an empty refusing _DEUDAS_READ_PATH_PREFIXES tuple so it fails closed by construction before any fetch function exists; `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.
- [x] `P03.S09` - Write the guard unit test proving refusal on every synthetic landing URL including a payment-shaped and an aplazamiento-shaped URL against the empty prefix set, then a mutation proof populating one real-looking prefix and confirming it permits only that prefix; `src/cadrumo/adapters/outbound/aeat/sede/tests/test_deudas_read_landing_guard.py`.

### Phase `P04` - CLI read surface: list, view, latest

Expose aeat app live deudas list/view/latest over persisted snapshots, matching the expedientes verb shape exactly; needs no specimen since it reads only what has already been captured.

- [x] `P04.S10` - Add the deudas CLI entrypoint and its list, view and latest payload models as new OutputSchema subclasses in the existing _app_live_payloads module, mirroring the expedientes payload shapes. Introduces tr help keys, so this row and S11 and S12 land as ONE unit with P07.S23 rather than independently: the codebase-to-locale parity gate is tree-wide and immediate, so the moment a tr key exists in source it must exist in all four catalogues; `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py, src/cadrumo/entrypoints/cli/_app_live_payloads.py`.
- [x] `P04.S11` - Wire aeat app live deudas list, view and latest into the app live command group, matching the expedientes latest, list, view verb shape exactly; `src/cadrumo/entrypoints/cli`.
- [x] `P04.S12` - Add the three new leaves to the reviewed-non-mutating roster as pure reads over persisted snapshots, verified by test_every_app_leaf_is_accounted_for_by_name_independent_census and a new CLI integration test asserting the three verb shapes; `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py`.

### Phase `P05` - Specimen-blocked: adapter parse, pull, write-guard enrollment

Wire the live AEAT fetch once an operator authorises a specimen capture: the DOM-to-Deuda parse function, the guard real allowed_path_prefixes, the pull CLI verb, its PROFILE_BOUND_WRITE_VERB_PATHS entry, and the operator-orientation harness sweep. Every row here is blocked until the specimen exists and is not startable before then.

- [ ] `P05.S13` - BLOCKED on an operator-authorised live specimen capture of Consultar deudas: observe the real situacion label vocabulary and confirm the str Field length bound is adequate, per the Declaracion.estado precedent, with no type change since situacion stays str; `no type change, situacion stays str; `src/cadrumo/core, src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.
- [ ] `P05.S14` - BLOCKED on the same specimen: write walk_deudas_consulta mapping the real DOM to Deuda rows, verified by a parse test against the captured fixture with sensitive fields never committed to the repo; `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.
- [ ] `P05.S15` - BLOCKED on the same specimen: populate the guard real allowed_path_prefixes from the captured consulta path, verified by the guard test refusing every known payment and aplazamiento path observed in the specimen; `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`.
- [ ] `P05.S16` - BLOCKED on the same specimen: wire aeat app live deudas pull calling the walker and DeudasService capture, named pull never capture or refresh or fetch or sync per the CLI contract; `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py`.
- [ ] `P05.S17` - Enroll app live deudas pull in PROFILE_BOUND_WRITE_VERB_PATHS with a comment stating it persists a captured snapshot to bucket storage, verified by test_root_fallback_guard_predicate_covers_profile_bound_mutations extended with the new entry; `src/cadrumo/application/storage_write_policy.py`.
- [ ] `P05.S18` - Add deudas pull to the operator-orientation agent-harness document alongside expedientes pull and notifications pull in the same commit as the verb, verified by test_documented_command_conformance; `src/cadrumo/_data/agent/rules/cadrumo-operator-orientation-routing.md`.

### Phase `P06` - Human-grounding-blocked: LGT legal-catalogue rows

Author legal-catalogue entries for the four ungrounded LGT provisions, each with a named human reviewer and a live-cross-checked BOE corpus_ref, needed only before the register interprets a legal category rather than displaying AEAT's own reported figures.

- [ ] `P06.S19` - BLOCKED on a named human legal reviewer, never an agent stamp: author the legal-catalogue entry for LGT art. 28, recargo del periodo ejecutivo and recargo de apremio, with a corpus_ref resolving to the last live-cross-checked BOE consolidated text; `src/cadrumo/_data/corpus/normatives/html, legal catalogue`.
- [ ] `P06.S20` - BLOCKED on a named human legal reviewer: author the legal-catalogue entry for LGT arts. 178-212, regimen sancionador, focused on the arts. 191-197 pecuniaria proporcional bands, with a live-cross-checked corpus_ref; `src/cadrumo/_data/corpus/normatives/html, legal catalogue`.
- [ ] `P06.S21` - BLOCKED on a named human legal reviewer: author the legal-catalogue entry for LGT arts. 65 and 82, aplazamiento y fraccionamiento del pago and garantias, with a live-cross-checked corpus_ref; `src/cadrumo/_data/corpus/normatives/html, legal catalogue`.
- [ ] `P06.S22` - BLOCKED on a named human legal reviewer: author the legal-catalogue entry for LGT arts. 163 and 167 through 173, procedimiento de apremio, providencia and embargo, with a live-cross-checked corpus_ref, verified by the legal-entry evidence gate; `src/cadrumo/_data/corpus/normatives/html, legal catalogue`.

### Phase `P07` - Peer-WIP-blocked: locale rows

Author real es/en/ca/hu values for the new deudas CLI help and labels once the in-flight en.yml/hu.yml peer WIP lands and scaffold --check is clean.

- [x] `P07.S23` - Author real es, en, ca and hu values for the new deudas CLI help and label keys via python -m dev.locales set, then scaffold and scaffold --check clean. Lands as ONE unit with P04.S10 through S12 because the codebase-to-locale parity gate is tree-wide and immediate, so no ordering exists in which the CLI rows are green before these values exist in all four catalogues. The original en.yml and hu.yml peer-WIP blocker is discharged; `src/cadrumo/locales`.

## Parallelization

P01 must land before P02 and P03 (both consume `Deuda`, its enums, and the
module `_deudas.py` lives in). P02, P03 and P04 have no interdependency
among themselves once P01 is closed and may run in parallel: the snapshot
service, the guard skeleton, and the CLI read surface touch disjoint files.
Within P04, S10 must land before S11, and S11 before S12. Within P02, S04
through S06 are sequential (each is a precondition for the next); S07 depends
on S04-S06 all being closed.

P05 is hard-blocked behind P01-P04 (it extends the same module and CLI
surface) and, independently, behind an operator authorising a live specimen
capture. Its own Steps are sequential: S13 (enum finalisation) before S14
(parse function, which needs the finalised `Situacion` type), S14 before S15
(prefixes come from the same capture but the parse function is the
consumer that proves the prefix is right), S15 before S16 (the `pull` verb
wires the guarded walker), S16 before S17 (enrollment names a verb that must
already exist), S17 before S18 (the harness doc must describe a live verb).

P06's four Steps are mutually independent (four separate LGT provisions) and
may run in parallel once a human reviewer is assigned to each; none of them
blocks P01-P05, since the base register displays AEAT's reported figures
without needing any of these citations. P07 is independent of every other
Phase except that it cannot start until the peer `en.yml`/`hu.yml` write
lands in the shared worktree.

## Verification

The plan is complete when every Step is closed (`- [x]`) or the closeout
audit records why a Step is a deferred carry-forward, per
`aeat-agent-orchestration`'s campaign-close mandate. Per-phase criteria:

- **P01**: new unit tests for `ObjetoTributario`, `Direccion` and the `Deuda`
  model pass; `uv run --no-sync pytest --collect-only -q` collects cleanly
  with no import cycle introduced.
- **P02**: `test_deudas_service.py`'s roundtrip passes with real adapters
  (real key provider, real SQLite, real `SecureObjectRepository`) and its
  anti-tautology proof fails the load when a persisted field is deleted from
  the on-disk payload.
- **P03**: `test_deudas_read_landing_guard.py` proves the guard refuses every
  synthetic URL against the empty prefix set, then proves a populated
  single-entry prefix permits only that entry (the mutation-proof pairing:
  break it, confirm red, restore).
- **P04**: `test_every_app_leaf_is_accounted_for_by_name_independent_census`
  stays green with the three new leaves classified, and a new CLI
  integration test exercises `list`/`view`/`latest` against a persisted
  snapshot fixture.
- **P05**: each Step's own named gate
  (`test_root_fallback_guard_predicate_covers_profile_bound_mutations`,
  `test_documented_command_conformance`, the parse fixture test) passes, and
  no Step in this Phase is started before an operator has authorised and
  delivered a specimen capture.
- **P06**: each legal-catalogue entry passes the legal-entry evidence gate
  (corpus cross-check, `required_text` phrase distinctiveness) and carries a
  named human reviewer's sign-off, never an agent stamp.
- **P07**: `python -m dev.locales scaffold` then `scaffold --check` run
  clean with no self-referencing placeholder and no missing `ca`/`hu` entry.

Cross-cutting: at no point in P01-P05 does a persisted `Deuda` value reach a
`BindingAggregation`, relation, or casilla resolution - grep
`BindingSourceKind` after P05 lands and confirm no new member references a
post-filing enforcement concept, the same structural check the research used
to establish the current gap.
