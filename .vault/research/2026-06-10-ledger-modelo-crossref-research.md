---
tags:
  - '#research'
  - '#ledger-modelo-crossref'
date: '2026-06-10'
modified: '2026-06-10'
related: []
---



# `ledger-modelo-crossref` research: `Transaction to modelo revision/filing back-reference`

This research maps the ledger-to-modelo cross-reference surface for a legal
audit. The question is: given a single ledger transaction, which modelo
calculation revisions and which filings consumed it, and is that back-reference
durably persisted and surfaceable, or only derivable on demand. The forward link
(a revision naming its contributing rows) is complete and persisted; the inverse
link (a transaction naming the revisions/filings it participated in) exists only
as an on-the-fly scan used as a write-guard, is never persisted on the
transaction, and is never surfaced to the operator. This is cluster C7 of the
ledger/modelo connectivity work. It is the read-side companion to the already
accepted snapshot/evidence layer (`modelo-filing-ledger-snapshot`,
`modelo-export-evidence-parity`), which captured *what the ledger said* at filing
time but left *which filings a given row fed* unaddressed.

## Findings

### Forward link is complete and persisted

`CalculationRevision.source_transaction_ids` (`src/aeat/domain/modelos/_calculation_revision.py`,
the field is a `tuple[...]` defaulting to `()`) records the contributing ledger
rows of a revision. It is fed at calculate time by `persist_calculation_revision`
and threaded into the content-addressed `derive_calculation_revision_id`. On top
of it the snapshot/evidence layer adds two optional typed envelopes:
`LedgerFilingSnapshot` (per-contributor `LedgerRowFingerprint` + aggregate
`snapshot_fingerprint`, for staleness) and `LedgerFilingEvidence`
(`LedgerEvidenceRow` per contributor + `ManualFactBasisEntry`, the reconstructable
fact basis), both in `src/aeat/domain/modelos/_ledger_filing_snapshot.py`,
captured at verify/file time and pegged by `snapshot_fingerprint`. Neither
snapshot nor evidence is threaded into the revision-id hash. So from a *revision*
the path down to its rows is fully modelled.

### Inverse link is derived only, never persisted, never surfaced

The only inverse traversal is `_blocking_modelo_references` (and its batch
sibling `_blockers_by_source_transaction_id`) in
`src/aeat/application/ledger/_actions_common.py`. Both load the *entire*
`CalculationRevisionCatalogueRepository`, keep only revisions in the finalized
states `{VERIFICADO_COMPLETO, PRESENTADO, PRESENTADO_SUPERSEDIDO}`
(`_REMOVAL_BLOCKING_REVISION_STATES`), restrict to the active bucket via the
revision's work unit, intersect `wanted` transaction ids against each revision's
`source_transaction_ids`, and emit `LedgerRemovalBlocker` rows. This is invoked
only as a *write-guard*: the remove path and the lifecycle/transition paths call
it to refuse mutating a row a finalized modelo depends on. The output is a
transient refusal, not a stored fact.

Confirmed gaps:

- `Transaction` (`src/aeat/domain/transactions/_models.py`) carries zero revision
  or filing references. It is frozen and content-addressed; adding a mutable
  participation set to it would break its content addressing and is the wrong
  home for the inverse link.
- `LedgerRemovalBlocker` (`src/aeat/application/ledger/_models.py`) is constructed
  in-memory per scan and is never persisted on or beside the transaction.
- The inverse scan is O(all revisions) per query because it has no index — fine
  for a one-shot write-guard, but a poor read-path primitive for audit.

### Transaction to filing is a two-hop traversal with no denormalised shortcut

`ModeloRecord` (the filing receipt, `src/aeat/domain/modelos/_filing_record.py`)
holds only `calculation_revision_id`; it carries no `source_transaction_ids`. So
"which filings consumed this row" is transaction → revision (via the inverse scan
above) → filing (via `calculation_revision_id`), a two-hop join with no one-hop
shortcut. `derive_filing_record_id` hashes only
`work_unit_id`/`calculation_revision_id`/`filed_at`/`filed_by` (+ optional
`member_nif`), so a denormalised `source_transaction_ids` could be added to
`ModeloRecord` for one-hop external audit *without* perturbing the filing id, by
excluding it from the hash — mirroring how `ledger_filing_snapshot` is excluded
from the revision-id hash.

### The read CLI shows lineage, not participation

`ledger track` (`src/aeat/entrypoints/cli/_ledger_read_cli.py`,
`_register_ledger_track_command`) renders a transaction's *edit/import lineage*
(`LedgerTrackResult` over the uniform output envelope) but says nothing about
which modelos the row participated in. There is no `participated_in` section and
no dedicated participation verb. So an operator (or an auditor) has no surface
that answers "where did this row end up filed".

### Borradores are invisible to the inverse scan

Because `_REMOVAL_BLOCKING_REVISION_STATES` is finalized-only, a row that feeds a
draft (`BORRADOR`) revision that has not yet been verified is *not* reported by
the inverse scan. For a legal audit this is acceptable (only finalized filings
matter), but it means a pre-mutation "this row is referenced in a pending draft"
warning is not derivable from today's scan and would need draft states included.

### The atomic multi-object write template already exists

`save_with_secure_object_writes` on the `TransactionCatalogueRepository`
(`src/aeat/domain/transactions/_repository.py`) and the application helpers
`_save_transaction_catalogue_and_events` /
`_save_transaction_catalogue_invoices_and_events`
(`src/aeat/application/ledger/_actions_common.py`) show the pattern: build the
extra secure-object writes, then commit them together via the substrate's
`save_many` (`src/aeat/adapters/persistence/storage/sql/secure_objects.py`),
which is a single SQL unit of work and enforces a *registered-write policy* —
an unregistered namespace cannot be written. This is the template a new
participation index must reuse so the index update co-emits in the same atomic
write as the revision/filing save, never as a parallel write path.

### Secure-object namespace registration is the mandatory persistence boundary

Every persisted, encrypted, bucket-scoped artefact is a
`SecureObjectNamespaceDefinition` registered in `STORAGE_NAMESPACE_REGISTRY`
(`src/aeat/adapters/persistence/storage/_namespace_registry.py`), carrying a
`SensitivityClass` (governs at-rest encryption), a `StorageNamespaceScope`, an
`object_key_grammar`, and a `schema_version`. The existing modelo catalogues
(`modelo_calculation_revision_catalogue`, `modelo_filing_record_catalogue`) are
`PROFILE_LOCAL` `FINANCIAL` singletons. A new participation index must be
registered the same way; the registry's `save_many` policy gate is what makes
"encrypted + bucket/profile-scoped + atomic" a structural guarantee rather than a
convention.

### Scope-mismatch note for the atomic write

The calculation-revision and filing-record catalogues are `PROFILE_LOCAL`-scoped,
not `BUCKET_LOCAL`. They are persisted through their own
`CalculationRevisionCatalogueRepository.save` / `ModeloRecordCatalogueRepository.save`
(single-object today), but both repositories are constructed over the *same*
`SecureObjectRepository` substrate for the bucket
(`secure_objects_for_modelo_bucket`). So co-writing the participation index with
the revision/filing catalogue in one `save_many` is feasible at the substrate
level; the work is to give the revision/filing persistence path a multi-object
write entry point (mirroring the transaction repository's
`save_with_secure_object_writes`) so the index rides the same SQL unit of work.

### Cross-cluster contracts touched

- C5 (uniform output contract): the read verb must ride the
  `SchemaEnvelope`/`OutputSchema` contract. Every ledger read result is already an
  `OutputSchema` (e.g. `LedgerTrackResult`, `src/aeat/entrypoints/cli/_ledger_payloads.py`),
  registered via `@register_schema`. The participation payload is a typed
  `OutputSchema`, not a bare dict.
- C6 (period-filter consistency): the participation entry derives from the same
  `source_transaction_ids` the period filter selected at calculate time, so the
  inverse index and the forward selection are definitionally the same set.
- C1 (amount sign): any amount surfaced in a participation projection follows the
  non-negative-amount-plus-direction convention already used by `LedgerEvidenceRow`.
