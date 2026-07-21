---
tags:
  - '#research'
  - '#ledger-latency-budget'
date: '2026-07-06'
modified: '2026-07-17'
related:
  - "[[2026-07-05-ledger-latency-budget-adr]]"
  - "[[2026-07-06-ledger-perf-optimization-reference]]"
---

# `ledger-latency-budget` research: `Fable review synthesis and HEAD drift`

This research reconciles the Fable optimization review with the current worktree before
implementation planning. The review snapshot was accurate as a cost decomposition, but
semantic search and exact-symbol confirmation show that this branch has already landed
part of the earlier O2 read-path work and part of the write-amplification fix. The plan
therefore targets only residual costs that still exist at HEAD.

## Findings

### F1 - Accepted latency ADR is the authorizing decision

The accepted decision is `2026-07-05-ledger-latency-budget-adr`, which authorizes Path A:
period-first partitioning through the five-column transaction date index, a mandatory
index-completeness gate, full-scan fallback on index drift, and uniform
`OUTSIDE_PERIOD` diagnostics for rows outside the requested period. It explicitly keeps
the plaintext index schema unchanged and leaves `_renta_ledger.py` on full `.load()`
pending #599.

### F2 - O2 partition exists, but targeted reads are still N+1

`src/aeat/adapters/persistence/profile/transactions.py` already implements
`partition_by_date_range`, and the IVA, M130 income, M130 gasto, M100 income, and
impatriado repository-backed entry points already call it where the transaction-date
index is valid. The residual Fable finding is narrower: the indexed path still loops
over in-window transaction ids and calls `SecureObjectRepository.load` once per id.
`src/aeat/adapters/persistence/storage/sql/secure_objects.py` has namespace scans,
single-row `load`, `namespace_payload_hashes`, `save_many`, and `apply_batch`, but no
targeted multi-load. A batch secure-object load is therefore the first implementation
slice.

### F3 - The double JSON parse is partly mitigated, not eliminated

`transactions.py` already centralizes the D6 timestamp witness parse in
`_decode_persisted_transaction_row`, so the guard no longer performs its own independent
decode. The authoritative envelope validation still calls
`Envelope[Transaction].model_validate_json(record.payload)`, so a row is still decoded
once for the witness and once for JSON-mode pydantic validation. That residual should
be measured after the batch-read work before changing the envelope contract.

### F4 - Out-of-window diagnostics are still a large allocation surface

`LedgerDatePartition.out_of_window` currently contains one
`OutOfWindowTransactionStub` pydantic object per excluded row. Each repository-backed
aggregator maps those stubs into one issue per row, and `_modelo_bindings.py` maps those
issues into `CalculationSourceDiagnostic` objects. M130 cumulative calculate resolves
income and gasto over the same window, so a multi-year bucket can allocate many
diagnostic objects for rows that cannot affect the target casillas. Collapsing this to
one count and date-span diagnostic is a diagnostics-channel contract change and needs
the accepted ADR amended before implementation.

### F5 - The Transaction before-validator residual is still present

`src/aeat/domain/transactions/_models.py` still uses
`@model_validator(mode="before")` for `Transaction._enforce_derived_transaction_id`.
It validates/coerces `raw`, derives the SHA-256 id, and manually coerces enums,
decimals, timestamps, optional strings, attachment tuples, and history collections
before field validation. Moving id enforcement to an after-validator is the main
validation fast-path lever, but it must preserve JSON roundtrips and tamper rejection.

### F6 - The write path no longer rewrites all rows, but it still scans and hashes all rows

The current transaction repository stores one secure-object row per transaction and
uses `_reconcile` plus `namespace_payload_hashes` so unchanged transactions are not
encrypted or upserted. That means the older "rewrite every row" wording is stale for
HEAD. The remaining write residual is still material: `_reconcile` serializes every
transaction in the incoming catalogue and hashes every serialized payload to discover
which row changed, then reads namespace hashes and syncs the date index. Single-row
mutation latency therefore still has an O(n) component and should be benchmarked as a
separate follow-up before dirty-set semantics are designed.

### F7 - Registry cache work appears already covered

The semantic search for registry TTL and snapshot caching points to the earlier
`codebase-performance-optimization` plan and current authority cache tests. Registry
cache tuning should stay a residual confirmation item unless fresh scale data shows it
dominates after storage, diagnostics, and transaction validation are addressed.

### F8 - Summary diagnostics are now an explicit contract change

The S15 ADR amendment authorizes the next diagnostics slice: repository-backed
resolvers may collapse the uniform out-of-window `OUTSIDE_PERIOD` rows into one
summary diagnostic per resolver/window. The summary contract is intentionally narrow:
excluded-row count plus filing-date span, and no decrypted financial fields such as
amount, counterparty, direction, category, lifecycle state, or business classification.

Consumer impact:

- `LedgerDatePartition` and the transaction repository protocol need a compact summary
  payload so callers no longer allocate one `OutOfWindowTransactionStub` pydantic object
  per excluded transaction.
- Repository-backed aggregation adapters currently turn every out-of-window stub into
  one aggregation issue. They must instead surface one summary issue/diagnostic while
  keeping in-window observations, casilla values, and provenance unchanged.
- `_modelo_bindings.py` maps Renta income, Renta gasto, impatriado income, and Renta
  expense aggregation issues to `CalculationSourceDiagnostic` rows one-for-one. IVA
  source diagnostics suppress `OUTSIDE_PERIOD` today, but IVA aggregation still pays
  the per-row issue allocation before that suppression. Tests and consumers that assert
  row-level out-of-window issue counts or transaction ids need to move to count/date-span
  assertions.
- Complete-index and stale-index fallback partitions must produce the same summary for
  the same catalogue/window, preserving the O2 stale-index invariant: stale means slow
  but correct, never a silent drop.

### W01.P01.S02 execution confirmation - 2026-07-06

The Fable synthesis is persisted as a current-state research baseline, not as an
implementation claim. The accepted constraints are the O2 latency ADR: preserve declared
tax values, keep the five-column plaintext date index unchanged, fall back to full scans
when the derived index is incomplete, keep `_renta_ledger.py` out of the date-index
optimization pending #599, and treat diagnostic taxonomy changes as explicit contract
work.

The open residual tiers for execution are:

- First, collapse targeted partition reads from per-id secure-object loads to one
  batched secure-object read while preserving classification, schema-version, AEAD, and
  revision-lineage checks.
- Second, after measurement, amend the ADR before collapsing out-of-window diagnostics
  from one object per excluded transaction to one count and date-span summary.
- Third, move transaction id enforcement away from the Python before-validator path only
  after JSON roundtrip and tamper-rejection tests are in place.
- Fourth, measure the remaining save-side O(n) serialise and hash residual before
  proposing dirty-set mutation semantics as a separate decision.

### W03.P06.S16 execution confirmation - 2026-07-06

The diagnostics summary contract is now recorded as an ADR-authorized implementation
constraint. The next implementation phase should change the partition payload first,
then update aggregation adapters and source-diagnostic tests so the reduced diagnostic
allocation is visible without changing declared tax outputs.

### W05.P14.S42 dirty-set mutation contract research - 2026-07-06

The S40/S41 benchmark makes the write residual material enough for a separate decision:
a one-row same-id transaction save over the 30k-row encrypted fixture measured P95
`2.659s`. The named residual is dominated by serializing and hashing every incoming
transaction payload, not by the decryption-free namespace hash scan:
`transaction_save_serialize_hash_all_rows` P95 `1.399s` versus
`transaction_save_namespace_hash_scan` P95 `0.201s`.

Current contract sources:

- `src/aeat/adapters/persistence/profile/transactions.py:330` -
  `save_with_secure_object_writes` composes transaction writes with event/invoice writes.
- `src/aeat/adapters/persistence/profile/transactions.py:671` - `_reconcile` loads the
  membership index, scans namespace payload hashes, serializes every incoming
  transaction, hashes every payload, and returns changed writes plus deletions.
- `src/aeat/adapters/persistence/profile/transactions.py:601` - `_sync_date_index`
  rebuilds the derived plaintext date-index diff from the whole incoming catalogue.
- `src/aeat/adapters/persistence/storage/sql/secure_objects.py:898` -
  `namespace_payload_hashes` is a decryption-free namespace metadata scan.
- `src/aeat/adapters/persistence/storage/sql/secure_objects.py:924` - `apply_batch`
  persists transaction and sibling secure-object writes atomically.
- `src/aeat/application/ledger/_actions_common.py:714` -
  `_save_transaction_catalogue_and_events` is the common single-writer persistence helper.
- `src/aeat/application/ledger/_actions_manual.py:456` and
  `src/aeat/application/ledger/_actions_manual.py:617` are representative single-row
  update/classify paths; both know the transaction id being changed.
- `src/aeat/application/ledger/_actions_classification.py:277` keeps bulk classify
  load-once/save-once and is already the multi-row amortized shape.

Design option A - repository dirty-set API:

Add an explicit adapter method for known transaction deltas, for example a method that
accepts changed transactions, removed transaction ids, and extra secure-object writes.
The caller supplies the ids it already knows from the mutation path. The repository
would serialize only changed/new transactions, optionally compare only those changed
digests against stored payload metadata, update the membership index by applying the
delta to the existing encrypted membership ids, and update/delete only affected
date-index rows. It would still call `apply_batch` once with transaction writes and
event/invoice writes so the existing atomic co-write contract survives.

Required invariants for option A:

- The existing full `save` / `_reconcile` path remains as the conservative fallback for
  imports, repair, index rebuild, and any caller that cannot prove a dirty set.
- Deleted ids must be bounded by the current membership index, preserving bucket
  isolation and preventing cross-bucket deletes.
- Id-changing edits must be expressed as one removed old id plus one changed replacement
  transaction; same-id edits must leave the membership index unchanged but may still
  update the date index if the filing date changed.
- Date-index rows remain derived and rebuildable; stale or missing membership/date index
  state should fall back to full reconciliation rather than silently trusting a dirty
  delta.
- Sibling writes from bucket events and invoices must stay in the same secure-object
  batch as the changed transaction writes.
- Unchanged rows must remain untouched at the secure-object row level: revision id,
  payload hash, and ciphertext hash should not change.

Design option B - per-transaction bytes/hash cache:

Cache serialized envelope bytes and payload hashes keyed by transaction id plus a stable
mutation stamp such as `modified_at` and/or object identity. This could reduce the
all-row serialization loop without changing the repository API, but it extends the
lifetime of plaintext envelope bytes or derived hashes in process memory and needs
careful invalidation across content-addressed id changes, process-per-command CLI usage,
and bulk mutation loops. It also leaves the full catalogue loop in place unless paired
with a dirty-set API.

Design option C - status quo with benchmark only:

Keep the existing full `_reconcile` path and rely on the validator/read-path wins. This
is simplest and preserves all contracts, but S40 shows a single-row mutation still costs
multi-second latency at scale and spends most named residual time on unchanged-row
serialization. That contradicts the goal of making everyday `ledger add/update/classify`
operations scale with the changed row rather than the whole ledger.

Recommendation:

Draft an ADR for option A as an additive dirty-set write path. It should not remove the
full reconciliation path. The ADR should authorize a small repository API extension and
the application wiring needed for single-row writers to pass the known changed/removed
ids. It should explicitly defer any process-level plaintext bytes cache unless a later
benchmark shows the dirty-set path still exceeds the mutation target. The acceptance
tests should reuse real encrypted storage and prove unchanged rows keep their revision
metadata, id-changing edits delete the old row and insert the replacement row, date-index
rows track changed filing dates, and transaction/event/invoice co-writes remain atomic.
