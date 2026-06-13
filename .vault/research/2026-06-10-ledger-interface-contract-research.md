---
tags:
  - '#research'
  - '#ledger-interface-contract'
date: '2026-06-10'
modified: '2026-06-10'
related: []
---



# `ledger-interface-contract` research: `Ledger CRUD envelope, ID, and sort contract`

This research catalogues the response-contract shape of the 26-verb `aeat app
ledger` CLI surface: how each verb's `--json` payload is shaped, how a CLI
operator addresses a single transaction by id, and how (or whether) the list
read surface can be ordered. It is the C5 cluster of the ledger-interface
factory campaign; the sibling clusters own the read/filter surface (C6), the
participation read verb (C7), and the non-negative-amount + direction money
shape (C1). The goal here is to establish, against the live code, the exact
state of three uniformity questions — payload envelope shape, id-input
convention, and sort capability — so the companion ADR can settle a single
canonical contract instead of the per-verb divergence that exists today.

All file/line citations below were read against `HEAD` at authoring time.

## Findings

### A. The outer envelope is already uniform; the divergence lives in `result`

Every successful ledger `--json` response is rendered through one shared
wrapper. `_emit_envelope` (`src/aeat/entrypoints/cli/_common.py:71`) is imported
by `_ledger.py` (line 61) and used at every emit site across the five verb
modules (`_ledger.py`, `_ledger_lifecycle_cli.py`, `_ledger_read_cli.py`,
`_ledger_review_cli.py`, `_ledger_import_cli.py`). It produces a
`SchemaEnvelope` (`src/aeat/core/json_contract.py:76`) with the stable outer
keys `{schema_version, command, result, warnings}`: `schema_version` defaults to
`"1"`, `command` is the stable command-path string (e.g. `"ledger.add"`),
`result` is the strict-validated per-verb payload, and `warnings` is a free-form
list. `register_schema(...)` decorates each payload class so the JSON-contract
test suite enumerates every command surface. Prior art that established this
uniform outer surface is recorded in the ADRs `2026-06-01-envelope-conformance-gate`
and `2026-06-02-emit-envelope-schema-burndown`.

The consequence: the envelope is **not** where the inconsistency lives. The
divergence is entirely in the `result` payload shapes declared in
`src/aeat/entrypoints/cli/_ledger_payloads.py`. Every payload subclasses the
strict `OutputSchema` base (`src/aeat/core/json_contract.py:53`), which is
`extra="forbid"`, `frozen=True`, `strict=True` — so a payload that omits a field
or types it loosely is a real wire-contract decision, not an accident the
caller can paper over.

### B. Single-transaction mutation payloads are inconsistent

The intended shared shape for verbs that mutate one transaction is
`_LedgerMutationResult` (`_ledger_payloads.py:150`): `{bucket_id,
transaction_id, bucket_event_ids, review_status, transaction:
TransactionPayload}`. `update`, `allocate`, `attach`/`doclink`, `archive`,
`stash`, and `restore` all subclass it and therefore carry `review_status`.

Three deviations:

- **`LedgerAddResult` (`_ledger_payloads.py:141`) is missing `review_status`.**
  It declares `{bucket_id, transaction_id, bucket_event_ids, transaction}` but
  does **not** subclass `_LedgerMutationResult`, so the one field that every
  other single-transaction mutation carries is absent from `add`. A consumer
  that reads `review_status` off a mutation response gets it everywhere except
  the first verb in the lifecycle.

- **`LedgerLinkResult` (`_ledger_payloads.py:556`) carries no `transaction`
  payload.** It returns `{operation, bucket_id, transaction_id, invoice_id?,
  evidence_id?, actor, evidence_update?}` — the operator who just linked an
  invoice/evidence to a transaction gets back no post-mutation projection of the
  transaction, breaking the "mutation returns the mutated object" contract the
  other verbs honour. `evidence_update` is additionally a bare
  `dict[str, object] | None` (a typed-boundary violation; see finding C).

- **`LedgerClassifyResult` (`_ledger_payloads.py:169`) is an all-optional
  union-of-branches.** It folds the single-transaction path, the bulk
  `--from-csv` path, the `--llm` suggest path, and the `--llm --saturate` path
  into one class where every field is optional so all branches validate. The
  single-transaction branch carries the same `{bucket_id, transaction_id,
  bucket_event_ids, review_status, transaction}` quintet as the mutation shape,
  but it is drowned in twenty optional fields, so a consumer cannot
  discriminate which branch it received without inspecting field presence.

The structural verbs legitimately differ and should not be forced into the
mutation shape: `LedgerSplitResult` (`:274`) returns parent + child ids + a
`split_group_id`; `LedgerMergeResult` (`:285`) returns the merged id + source
child ids; `LedgerRemoveResult` (`:236`) and `LedgerResetResult` (`:255`) mirror
removal/reset reports with cascade lists and `blocking_modelo_references`. These
operate on a *set* of transactions or destroy the subject, so a single
`transaction: TransactionPayload` slot does not apply.

### C. Several read/list payloads expose `list[dict[str, object]]` wire boundaries

`aeat-architecture-boundaries` forbids a bare `dict[str, Any]` at a wire
boundary. The following payloads violate it:

- `LedgerListResult.rows` is `list[dict[str, object]]` (`_ledger_payloads.py:313`).
- `LedgerHistoryResult.events` is `list[dict[str, object]]` (`:366`).
- `LedgerTrackResult.tracking` is `dict[str, object]` (`:487`).
- `LedgerImportPayload.{imported,skipped,likely_duplicate}_transaction_refs`
  are `list[dict[str, object]]` (`:443`–`:445`).
- `LedgerExportPayload.rows` (`:403`), `LedgerLinkResult.evidence_update`
  (`:565`), `LedgerPreflightResult.{period,issues}` (`:549`,`:551`),
  `RatiosEligibleResult.rows` (`:613`), and the business-invoice / inventory /
  evidence `list` results (`rows: list[dict[str, object]]`, e.g. `:672`,`:755`,
  `:855`) are the same bare-dict shape.

The list rows are constructed in `_ledger_list.py:153` from
`review_payload.model_dump(mode="python")` (a `LedgerTransactionReviewPayload`)
plus three appended keys (`full_id`, `display_id`, `group_label`). So a
strongly-typed row schema already has a source projection to reuse — the row is
a typed object that was deliberately flattened to a dict at the boundary.

### D. The canonical id resolver is sound but wrapped by two duplicate CLI shims

The authoritative resolver is `resolve_transaction_id`
(`src/aeat/application/ledger/_id_resolution.py:69`): it takes a lowercase-hex
prefix or full id, refuses empty / non-hex / over-length input, and resolves to
the single 64-char content-addressed id, raising `TransactionIdPrefixError` on
zero-match or ambiguity (the error lists collision candidates). A read-side
companion `resolve_lineage_transaction_id` (`:117`) additionally follows the
edit-lineage chain so a pre-`update` id still resolves. There is **no**
`//uuid` double-slash form anywhere — that discovery hint was inaccurate; ids
are bare hex prefixes only.

The defect is duplication of the *CLI-facing* shim: `_resolve_id` exists twice,
once in `_ledger.py:291` and once in `_ledger_lifecycle_cli.py:84`, each
wrapping `resolve_transaction_id` with a near-identical block that translates
`TransactionIdPrefixError` into a `tr(...)`-localised `typer.BadParameter`. The
`_ledger.py` copy additionally has a sibling `_resolve_read_id` (`:306`) for the
lineage path. The two `_resolve_id` bodies are substitutable and should be one
shared helper.

The real operator-facing inconsistency is the **id-input convention**, not the
resolver. Mutation verbs accept the id as a `--id` Typer Option; the read verbs
`view` / `history` / `track` accept it as a positional `Argument`;
`classify` / `review` make it optional. So the same conceptual "address one
transaction" input has three different CLI shapes across the surface.

### E. There is no sort capability on the list surface

`project_ledger_list` (`src/aeat/entrypoints/cli/_ledger_list.py:41`) is the
single projection/paging function for `ledger list`. It applies the C6 filter
spec, an optional `--group` equality filter, and an optional `--by-group` sort.
The `--by-group` sort (`:67`) keys on `(group_label or "￿",
transaction_id)` — the secondary key is the content-hash id, which is
order-meaningless to an operator, so within a group the order is effectively
arbitrary. There is **no** `--sort-by` / `--sort-order` capability for date,
amount, description, lifecycle, or classification. `project_ledger_list` is the
correct single injection point for a sort, and it is the same function C6
extends for filtering, so sort params and filter params must compose there.

### F. `Transaction` carries no `created_at` / `modified_at`

The `Transaction` model (`src/aeat/domain/transactions/_models.py:690`) has no
`created_at` or `modified_at` field (a `grep` for both returns nothing in that
module). The temporal facts that do exist are: `classified_at` (`:806`,
nullable, set when a classification decision is made), `created_event_id`
(`:798`, a bucket-event reference, not a timestamp), the `edit_lineage` chain
(`:800`), and — only for imported rows — `raw.provenance.ingested_at`
(`src/aeat/domain/transactions/_raw_transaction.py:67`, the ingest-run
timestamp). A manually-added row (`ledger add`) therefore has no creation
timestamp at all. This is the load-bearing gap for honest temporal sorting: a
`--sort-by created_at` cannot be honest until the field exists on every row, not
just imported ones.

### G. Secure-storage gate — list/read read encrypted bucket rows; envelopes are transient

The ledger persistence boundary is the per-profile encrypted bucket. All ledger
data rides the bucket-scoped `SecureObjectRepository`:
`TransactionCatalogueRepository` (`src/aeat/domain/transactions/_repository.py:92`)
is bound to one `bucket_id` and stores/loads the catalogue under the encrypted
object key `transaction-catalogue:{bucket_id}` (`:42`, `:102`–`:105`). The list
read path (`list_manual_transactions` → `TransactionCatalogueRepository.load`,
`:116`) decrypts and returns persisted rows from that bucket; `project_ledger_list`
reads the loaded catalogue and projects it. The `--json` envelope and the typed
row/payload schemas are **transient output** — they are constructed in memory at
emit time and printed; no list, view, history, track, or export read path writes
a plaintext copy of ledger rows to disk. Sorting (finding E) reorders the
in-memory projection only; it touches neither the encrypted store nor any
on-disk plaintext. Any new `created_at` field (finding F) added to `Transaction`
rides the same encrypted catalogue envelope and must survive a strict
save→load→equality roundtrip per the roundtrip-discipline rule.

### H. Roster is pinned

`src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py` pins the 26-verb
roster, so any contract change that adds/removes/renames a verb is caught by an
existing gate. The JSON-contract registry (`register_schema`) similarly pins
each payload class to its command path.
