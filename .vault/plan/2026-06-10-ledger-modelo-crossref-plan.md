---
tags:
  - '#plan'
  - '#ledger-modelo-crossref'
date: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-ledger-modelo-crossref-adr]]'
  - '[[2026-06-10-ledger-modelo-crossref-research]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

# `ledger-modelo-crossref` `Transaction participation index for audit cross-reference` plan

### Phase `P01` - Secure-object namespace + domain model

Register the encrypted participation-index namespace and define the TransactionRevisionParticipationIndex domain model with full pydantic schema.

- [x] `P01.S01` - Define TransactionRevisionParticipation pydantic model (calculation_revision_id, work_unit_id, modelo, filing_year, period, revision_state; `optional filing_record_id and justificante_reference for filed states) in src/aeat/domain/modelos/_participation_index.py; `src/aeat/domain/modelos/_participation_index.py [new file]`.
- [x] `P01.S02` - Define TransactionRevisionParticipationIndex pydantic model keyed by transaction_id mapping to tuple[TransactionRevisionParticipation, ...]; `derive_participation_index_id using transaction_id for object-key grammar; strict frozen config; `src/aeat/domain/modelos/_participation_index.py`.
- [x] `P01.S03` - Register participation_index_catalogue namespace in STORAGE_NAMESPACE_REGISTRY in src/aeat/adapters/persistence/storage/_namespace_registry.py: key=transaction_participation_index, namespace=aeat.domain.modelos.participation_index, sensitivity=FINANCIAL, scope=PROFILE_LOCAL, schema_version=1, object_key_grammar matching transaction_id slug; `src/aeat/adapters/persistence/storage/_namespace_registry.py`.
- [x] `P01.S04` - Add TransactionParticipationIndexRepository wrapping SecureObjectRepository for the new namespace; `load/save per transaction_id; add to __all__ in src/aeat/domain/modelos/__init__.py and relevant top-level re-exports; `src/aeat/domain/modelos/_participation_index.py, src/aeat/domain/modelos/__init__.py`.
- [x] `P01.S05` - Write roundtrip test: build a populated TransactionRevisionParticipationIndex with all non-default fields; `save via real EphemeralMasterKeyProvider + real SQLite engine; load back; assert strict model equality; assert anti-tautology (corrupt on-disk row triggers ValidationError or strict inequality); `src/aeat/domain/modelos/tests/test_participation_index_roundtrip.py [new file]`.
- [x] `P01.S06` - Gate: uv run --no-sync pytest src/aeat/domain/modelos/tests/test_participation_index_roundtrip.py src/aeat/adapters/persistence/storage/tests/test_namespace_registry.py -x -q; `assert new namespace key present in STORAGE_NAMESPACE_REGISTRY; roundtrip and anti-tautology tests pass; `tests`.

### Phase `P02` - Co-emission: index write atomic with revision + filing persist

Add save_with_secure_object_writes entry points to calculation-revision and filing-record persistence so the participation-index update co-emits in the same SQL unit of work.

- [x] `P02.S07` - Add upsert_transaction_participation helper: merge a new TransactionRevisionParticipation into the per-transaction entry in a TransactionRevisionParticipationIndex; `return updated index; no mutation of existing entries; `src/aeat/domain/modelos/_participation_index.py`.
- [x] `P02.S08` - Add to_secure_object_write on TransactionParticipationIndexRepository mirroring the BucketEventHistoryRepository pattern so participation writes can be passed to save_with_secure_object_writes as an extra write slot; `expose the method at the top-level re-export; `src/aeat/domain/modelos/_participation_index.py`.
- [x] `P02.S09` - Add save_with_participation_index_write entry point to CalculationRevisionCatalogueRepository (or a helper in _revision_persistence.py): after computing the new CalculationRevision for VERIFICADO_COMPLETO state, build the participation entries for each source_transaction_id and pass as an extra SecureObjectWrite alongside the catalogue save via save_many on the shared SecureObjectRepository substrate; `src/aeat/domain/modelos/_calculation_repository.py, src/aeat/application/modelo/_revision_persistence.py`.
- [x] `P02.S10` - Extend persist_filed_revision in src/aeat/application/modelo/_revision_persistence.py:194 to accept an optional TransactionParticipationIndexRepository; `when present, upsert the filing_record_id and justificante_reference onto each transaction's participation entry and pass the updated index object as an extra SecureObjectWrite inside the same save_many call that persists the filing catalogue - do NOT re-implement the filing write path; `src/aeat/application/modelo/_revision_persistence.py`.
- [x] `P02.S11` - Wire participation_index_repository into the verify action call site (src/aeat/application/modelo/_actions_common.py or the verify action module) so all callers of persist_calculation_revision for VERIFICADO_COMPLETO pass the repository; `confirm _blocking_modelo_references retains its live catalogue scan (write-guard unchanged); `src/aeat/application/modelo/_actions_common.py`.
- [x] `P02.S12` - Write integration test: create a real CalculationRevision with source_transaction_ids, transition to VERIFICADO_COMPLETO then PRESENTADO through real persist helpers, assert participation index entries exist for every source_transaction_id; `assert filed entry carries filing_record_id; assert _blocking_modelo_references still returns correct blockers (live scan unchanged); `src/aeat/application/modelo/tests/test_participation_co_emission.py [new file]`.
- [x] `P02.S13` - Gate: uv run --no-sync pytest src/aeat/application/modelo/tests/test_participation_co_emission.py -x -q; `all co-emission tests pass; live-guard tests in test_ledger_removal_blockers (or equivalent) still pass; `tests`.

### Phase `P03` - Index rebuild from revision catalogue

Implement a rebuild action that regenerates the participation index from scratch by iterating the full finalized-revision catalogue, so a stale or corrupt index can be replaced without data loss.

- [x] `P03.S14` - Implement rebuild_participation_index action in src/aeat/application/modelo/_participation_index_rebuild.py: load the full CalculationRevisionCatalogue + ModeloRecordCatalogue (for filing_record_id and justificante_reference); `iterate revisions in finalized states; build TransactionRevisionParticipationIndex entries; save each per-transaction entry via TransactionParticipationIndexRepository; return rebuild stats (transaction_count, participation_count); `src/aeat/application/modelo/_participation_index_rebuild.py [new file]`.
- [x] `P03.S15` - Wire rebuild action into CLI as aeat app modelo participation rebuild (or ledger participation rebuild); `emit JSON with rebuild stats on the uniform envelope; add to __all__ and top-level re-exports; `src/aeat/entrypoints/cli/_ledger_read_cli.py or new _participation_cli.py`.
- [x] `P03.S16` - Write test: seed a revision catalogue with known finalized revisions covering multiple transactions and multiple revisions per transaction; `run rebuild_participation_index; assert every finalized revision's source_transaction_ids appear in the rebuilt index; assert borrador revisions are excluded; assert filed revisions carry filing_record_id; `src/aeat/application/modelo/tests/test_participation_rebuild.py [new file]`.
- [x] `P03.S17` - Gate: uv run --no-sync pytest src/aeat/application/modelo/tests/test_participation_rebuild.py -x -q; `all rebuild tests pass; confirmed by running pytest --collect-only -q that no test files are discovered with naked placement (tests-live-under-domain-tests-folders rule); `tests`.

### Phase `P04` - Read verb + CLI surface + LedgerTrackResult extension

Implement the ledger participation read action, register LedgerTransactionParticipationPayload on the C5 envelope, wire the ledger participation CLI verb, and extend ledger track with a participated_in section.

- [x] `P04.S18` - Define LedgerTransactionParticipationEntryPayload OutputSchema (calculation_revision_id, work_unit_id, modelo, filing_year, period, revision_state; `optional filing_record_id, justificante_reference) and LedgerTransactionParticipationPayload OutputSchema (transaction_id, participations: list[LedgerTransactionParticipationEntryPayload]); decorate with @register_schema('ledger.participation') in src/aeat/entrypoints/cli/_ledger_payloads.py; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `P04.S19` - Implement get_transaction_participation application action in src/aeat/application/ledger/_actions_read.py (or new file): load TransactionParticipationIndexRepository for the given transaction_id; `return LedgerTransactionParticipationPayload; amounts in any surfaced evidence projection use non-negative magnitude + direction (C1 convention); `src/aeat/application/ledger/_actions_read.py`.
- [x] `P04.S20` - Wire aeat app ledger participation <transaction-id> CLI verb in src/aeat/entrypoints/cli/_ledger_read_cli.py: call get_transaction_participation; `emit LedgerTransactionParticipationPayload on the uniform SchemaEnvelope; add --include-borradores flag reserved (no-op for now with a documented stub comment); `src/aeat/entrypoints/cli/_ledger_read_cli.py`.
- [x] `P04.S21` - Extend LedgerTrackResult in src/aeat/entrypoints/cli/_ledger_payloads.py with an optional participated_in: list[LedgerTransactionParticipationEntryPayload] | None field; `populate it in the ledger track handler from the participation index when the transaction has finalized participations; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_read_cli.py`.
- [x] `P04.S22` - Write CLI command conformance test (add to documented-command-conformance suite or new test): assert ledger participation command exists in the Typer tree; `assert --include-borradores flag is declared; assert ledger track result includes participated_in field in JSON schema; `src/aeat/entrypoints/cli/tests/`.
- [x] `P04.S23` - Gate: uv run --no-sync pytest src/aeat/entrypoints/cli/tests/ src/aeat/application/ledger/tests/ -x -q; `all participation verb tests pass; ledger track JSON output includes participated_in for transactions with finalized revisions; `tests`.

### Phase `P05` - ModeloRecord denormalization + post-roundtrip validator

Add source_transaction_ids to ModeloRecord excluded from derive_filing_record_id, and add a post-roundtrip validator cross-checking ledger_filing_snapshot vs ledger_filing_evidence contributor coverage.

- [x] `P05.S24` - Add source_transaction_ids: tuple[str, ...] = () field to ModeloRecord in src/aeat/domain/modelos/_filing_record.py; `exclude it from derive_filing_record_id (mirror the ledger_filing_snapshot exclusion pattern); update persist_filed_revision in _revision_persistence.py to populate source_transaction_ids from the filed CalculationRevision; `src/aeat/domain/modelos/_filing_record.py, src/aeat/application/modelo/_revision_persistence.py`.
- [x] `P05.S25` - Add _assert_evidence_covers_snapshot post-roundtrip validator to the verify/file path: after loading a persisted CalculationRevision, assert ledger_filing_snapshot.rows contributor set equals ledger_filing_evidence.rows contributor set; `raise a typed validation error if a contributor is present in one envelope but not the other; gate fires on every load from the encrypted store; `src/aeat/domain/modelos/_calculation_revision.py or src/aeat/application/modelo/_actions_common.py`.
- [x] `P05.S26` - Write ModeloRecord roundtrip test asserting source_transaction_ids survives save/load unchanged with non-default values and that derive_filing_record_id is stable across calls regardless of source_transaction_ids value; `also assert anti-tautology: remove source_transaction_ids from the serialized payload and confirm load raises ValidationError or returns () when field is absent; `src/aeat/domain/modelos/tests/test_filing_record_roundtrip.py [new or extend existing]`.
- [x] `P05.S27` - Write validator test: build a CalculationRevision with ledger_filing_snapshot contributor set and ledger_filing_evidence contributor set; `introduce a deliberate mismatch (drop a row from one); assert the post-roundtrip validator raises with the missing contributor identified in the error message; `src/aeat/domain/modelos/tests/test_snapshot_evidence_coverage_validator.py [new file]`.
- [x] `P05.S28` - Gate: uv run --no-sync pytest src/aeat/domain/modelos/tests/ src/aeat/application/modelo/tests/ -x -q; `uv run --no-sync pytest --collect-only -q 2>&1 | grep -v 'test session' | head -3 (confirm clean collection); run full affected-module suite; all tests green; `tests`.

## Description

This plan implements the transaction-to-revision participation index described in the
accepted ADR. The ledger currently provides only a forward link (revision names its
contributing transaction ids); the inverse question an auditor asks - which finalized
modelo revisions and filings consumed a given transaction - has no persisted, surfaced
answer. The only inverse traversal today is the write-guard `_blocking_modelo_references`
scan, which is transient and never exposed to an operator.

The work introduces a `TransactionRevisionParticipationIndex` secure-object, registered
as an encrypted PROFILE_LOCAL FINANCIAL namespace in `STORAGE_NAMESPACE_REGISTRY`, and
co-emits an index update atomically with every revision verification and filing persist.
The write path follows the `save_with_secure_object_writes` multi-object commit template
already used by the transaction-catalogue layer; it does not re-implement the revision
write path. The lifetime write-guard keeps its authoritative live catalogue scan; the
index is a read-side derived cache that is fully rebuildable from the revision catalogue.

A dedicated `ledger participation <transaction-id>` read verb surfaces a typed
`LedgerTransactionParticipationPayload` on the C5 uniform `SchemaEnvelope`; the existing
`ledger track` output gains a parallel `participated_in` section. `ModeloRecord` gains a
denormalized `source_transaction_ids` field excluded from `derive_filing_record_id`, so
an external audit tool resolves the filing's transaction set in one hop. A
post-roundtrip validator cross-checks `ledger_filing_snapshot.rows` against
`ledger_filing_evidence.rows` contributor coverage so an envelope that silently drops a
contributor row is caught on load.

Amounts in any evidence projection surfaced by the participation verb follow the
non-negative-magnitude plus authoritative `direction` convention (C1). The index is
scoped to finalized revision states (`VERIFICADO_COMPLETO`, `PRESENTADO`,
`PRESENTADO_SUPERSEDIDO`); borrador inclusion is deferred and a `--include-borradores`
flag is reserved at the CLI boundary.

## Steps

## Parallelization

Phases carry hard ordering dependencies that must be respected:

- P01 (namespace + domain model) is a hard prerequisite for all subsequent phases.
  No other phase can start until the `TransactionRevisionParticipationIndex` model and
  its registered namespace exist and pass the P01 gate.

- P02 (co-emission) depends on P01 (repository and `to_secure_object_write` method from
  P01.S04/S08 are consumed here). P02 must be complete before P04's read action can
  load populated index data from a real lifecycle run.

- P03 (rebuild) depends on P01 (model + repository) but is independent of P02 in
  implementation terms. It can proceed in parallel with P02 once P01 is closed.

- P04 (read verb + CLI surface) depends on P01 (for the payload type `LedgerTransactionParticipationPayload`
  defined against the domain model) and P02 (for end-to-end tests using real persisted
  index entries). P04.S18 (payload schema) can start as soon as P01 is closed; the full
  P04 gate requires P02 to be closed so integration tests can verify real index data.

- P05 (ModeloRecord denormalization + post-roundtrip validator) depends on P01 (for
  the calculation-revision model shape in the validator) but is independent of P02, P03,
  and P04 in implementation terms. It can proceed in parallel with P02 and P03 once P01
  is closed.

## Verification

- `STORAGE_NAMESPACE_REGISTRY` contains the `transaction_participation_index` namespace;
  `test_namespace_registry.py` asserts its presence and shape with correct sensitivity
  and scope.
- `TransactionRevisionParticipationIndex` strict-roundtrip test passes against real
  encrypted storage using `EphemeralMasterKeyProvider`; anti-tautology proof (corrupted
  payload) triggers `ValidationError` or strict inequality on load.
- Co-emission integration test (`test_participation_co_emission.py`) transitions a real
  revision through VERIFICADO_COMPLETO then PRESENTADO via real persist helpers and
  asserts participation index entries exist for every `source_transaction_id`, that the
  filed entry carries `filing_record_id`, and that `_blocking_modelo_references` returns
  the same blockers as before (write-guard correctness unchanged).
- Rebuild test (`test_participation_rebuild.py`) seeds a revision catalogue with
  finalized and borrador revisions, runs the rebuild action, and asserts every finalized
  revision's `source_transaction_ids` appear in the rebuilt index while borrador
  revisions are excluded.
- `ledger participation <id>` CLI verb is registered in the Typer tree; `--include-borradores`
  flag is declared (reserved); the command emits valid `LedgerTransactionParticipationPayload`
  JSON conforming to the `@register_schema("ledger.participation")` contract.
- `ledger track` JSON output includes a `participated_in` list for transactions that
  appear in finalized revisions.
- `ModeloRecord` roundtrip test asserts `source_transaction_ids` round-trips correctly
  with non-default values and that `derive_filing_record_id` is stable regardless of
  `source_transaction_ids` value.
- Post-roundtrip validator test (`test_snapshot_evidence_coverage_validator.py`)
  asserts a deliberate `ledger_filing_snapshot` vs `ledger_filing_evidence` contributor
  mismatch raises a typed validation error naming the missing contributor.
- `uv run --no-sync pytest --collect-only -q` exits clean with no test files discovered
  outside a `tests/` parent directory (tests-live-under-domain-tests-folders rule).
- Full affected-module suite (`src/aeat/domain/modelos/`, `src/aeat/application/modelo/`,
  `src/aeat/application/ledger/`, `src/aeat/entrypoints/cli/`) green between commits.
