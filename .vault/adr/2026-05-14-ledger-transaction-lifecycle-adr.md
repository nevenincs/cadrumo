---
tags:
  - "#adr"
  - "#ledger-transaction-lifecycle"
date: '2026-05-14'
modified: '2026-05-14'
related:
  - "[[2026-05-14-ledger-transaction-lifecycle-research]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-02-aeat-cli-redesign-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]"
---

# `ledger-transaction-lifecycle` adr: full crud plus split and re-merge with traceable lineage | (**status:** `accepted`)

## Context

The ledger CLI must support add, edit, remove, split, and re-merge for
bucket-scoped ledger transactions. Every operation must be event-emitting,
flow user-facing strings through `tr(...)`, and refuse half-implementations
or legacy-compat shims. The full ground truth on the existing record shape,
action surface, event coverage, and CLI surface lives in the companion
research document; this ADR builds on its eight numbered gaps and does not
restate them in full.

The eight gaps the research closes against and this ADR resolves are:
(1) no split primitive on the domain record;
(2) no re-merge primitive;
(3) no LEDGER_TRANSACTION_SPLIT or LEDGER_TRANSACTION_MERGED event types;
(4) archive and stash are silently destructive;
(5) sub-app services do not return bucket_event_ids;
(6) _resolve_id errors leak raw Python text instead of tr-rendered messages;
(7) the ledger track verb skips _resolve_id;
(8) no ledger history verb even though the event store and the
modelo history pattern already exist.

The non-negotiable charter for this work:

- The CLI supports add, edit, remove, split, and re-merge for ledger
  transactions; every op is event-emitting and audit-anchored.
- All user-facing strings flow through tr(...) with real translations in
  every locale (en/es/ca/hu) -- no scaffold placeholders.
- No tautological tests, no shims, no half-implementations, no
  legacy-compat aliases.
- Destructive ops require explicit confirmation UX (--yes, optionally
  --dry-run) and a free-text --reason recorded into the event payload.
- Removed code stays removed; in-flight work lands fully.
- Backend already implements BucketEvent content-addressing and atomic
  catalogue-plus-event persistence; the CLI must enrol every verb.

**Distinction from prior `split`-named work.** Two earlier ADRs in this project use the word "split" with a different meaning. `[[2026-05-02-aeat-cli-redesign-adr]]` specified `aeat app ledger edit --split business=SHARE --split personal=SHARE` — a single-row allocation knob recorded via `business_pct`, not N-way row splitting. `[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]` then renamed `split` → `allocate` and removed the prior framing because it never produced child rows. The deleted `LedgerSplit` model (workflow-layer annotation on `LedgerReviewRecord`, removed in commit `3a08f880` on 2026-05-14) was that earlier feature. The live guard at `src/aeat/application/review/_actions.py:17-29` rejects any split overlay routed through review and is exercised by the test at `application/review/test_actions.py:40`. This ADR introduces a **wholly new primitive**: true N-way row splitting where one parent produces N child transactions whose amounts sum to the parent, each child carrying independent classification and an explicit `split_lineage` field. The new work replaces the guard in `_actions.py:17-29` with a real implementation; the `allocate` verb (single-row `business_pct`) remains unchanged and orthogonal.

## Decision 1 -- Canonical record shape for split lineage

Add a new frozen pydantic v2 field `split_lineage: SplitLineage | None` to
the existing `Transaction` model. `SplitLineage` is a strict frozen model
with three fields: `split_group_id: str` (64-char sha256 hex);
`role: SplitRole`; and `sibling_transaction_ids: tuple[str, ...]` (for a
parent: every child id; for a child: the parent id plus every other child
id; for a merged row: every source-child id).

`SplitRole` is a new `StrEnum` under `src/aeat/domain/transactions/_enums.py`
with members `PARENT`, `CHILD`, and `MERGED`. `split_group_id` is
content-addressed: sha256 over (parent_transaction_id, sorted child amounts
as canonical decimal strings, sorted child narratives). The same digest is
re-computed on the merge path so re-emission is naturally idempotent.

This shape beats a parallel `SplitGroup` aggregate because: the catalogue
remains the single source of truth; the `for_object(parent_id)` event query
already used by modelo-history needs no parallel index; and the lineage
field travels with the row through every persistence boundary that already
carries the rest of the `Transaction` record.

A transaction with `split_lineage = None` is not part of any split. A
parent and its children share the same `split_group_id`. Re-merge produces
a new transaction whose `split_lineage.role` is `MERGED` and whose
`sibling_transaction_ids` enumerates the merged source-child ids.

## Decision 2 -- Per-op semantics

For each verb, the contract is fixed below.

**add** (`create_manual_transaction`). Pre-conditions: deterministic
content hash must be unique among ACTIVE rows. Effect: writes one ACTIVE
row; emits `LEDGER_TRANSACTION_CREATED`. Reversibility: inverse is
`remove`. Idempotency: re-running with identical inputs produces the same
`transaction_id` and is refused at the catalogue boundary, not silently
swallowed.

**edit** (`update_manual_transaction` / `update_manual_transaction_fields`).
Pre-conditions: target must be ACTIVE; finalized-modelo guard refuses if
the row is referenced by a sealed calculation; split-lineage guard refuses
edits to a parent in `SPLIT` state and to any child whose parent is in
`SPLIT` (edit the children individually if needed; never the sealed
parent). Effect: full-replace; if the deterministic hash changes, the
prior id is recorded on `TransactionEditLineageEntry`; emits up to four
event types per the existing `_update_event_specs` contract. Reversibility:
no explicit inverse; lineage is the audit trail. Idempotency: the
mutation-signature diff check refuses no-op edits.

**remove** (`remove_manual_transaction`). Pre-conditions: ACTIVE,
ARCHIVED, or STASHED; finalized-modelo guard; split-lineage guard refuses
removal of a child whose parent is still in `SPLIT` (the parent must be
re-merged or the sibling-group archived together). Effect: hard delete
with cascading detach; emits `LEDGER_TRANSACTION_REMOVED`. Reversibility:
**irreversible**. Idempotency: re-running on a deleted id raises a typed
not-found refusal.

**archive** (`archive_manual_transaction`). Pre-conditions: ACTIVE;
finalized-modelo guard does not block archive (audit is preserved).
Effect: ACTIVE to ARCHIVED; emits `LEDGER_TRANSACTION_ARCHIVED`.
Reversibility: inverse is `activate` via
`_transition_manual_transaction_lifecycle`. Idempotency: re-archiving an
already-ARCHIVED row is a typed refusal, not a silent no-op.

**stash** (`stash_manual_transaction`). As archive, but ACTIVE to STASHED;
emits `LEDGER_TRANSACTION_STASHED`. The existing ban on archive-from-
stashed and stash-from-archived stands.

**split** (new). Pre-conditions: parent must be ACTIVE; finalized-modelo
guard refuses split if the parent is referenced by a sealed calculation
(splitting would mutate the calculation input set); a row already in
`SPLIT` cannot be re-split (re-merge first). Effect: parent transitions
ACTIVE to SPLIT (new lifecycle member); N child rows are written with
`role=CHILD` and the same `split_group_id`; emits one
`LEDGER_TRANSACTION_SPLIT` event whose `object_id` is the parent id.
Sum of child amounts must equal parent amount **exactly** (no rounding
tolerance -- the caller supplies cents-accurate decimals or the op
refuses). Direction is inherited from the parent. Classification,
category, evidence, and attachment links are **not** auto-cloned; each
child is born unclassified and must be classified independently. This
forces conscious per-row tax treatment, which is the whole point of
splitting. Reversibility: inverse is `merge`. Idempotency: the
content-addressed `split_group_id` makes re-emission of an identical
split a typed refusal at the catalogue boundary.

**merge** (new, the re-merge inverse). Pre-conditions: every supplied
child id must share the same `split_group_id`; the parent must currently
be in `SPLIT`; finalized-modelo guard refuses if any source child is
sealed-referenced. Effect: a fresh transaction is content-addressed from
the merged amounts and narratives (so its `transaction_id` is **new**,
not the original parent id); the children are transitioned to ARCHIVED
with `split_lineage.role` preserved; the parent transitions SPLIT to
ARCHIVED (not back to ACTIVE -- the parent has already left the active
set); emits one `LEDGER_TRANSACTION_MERGED` event whose `object_id` is
the parent id (so `for_object(parent_id)` returns the full lineage chain
parent then split then merged). The merged row is ACTIVE and unclassified.
Reversibility: inverse is `split` again on the new merged row.
Idempotency: re-emission with identical inputs produces an identical
content-addressed merged id and is refused at the catalogue boundary.

## Decision 3 -- New BucketEventType members

Two new members in `src/aeat/domain/buckets/_event.py`:

- `LEDGER_TRANSACTION_SPLIT = "ledger.transaction.split"`. Emitted once
  per `split` op. Payload carries `split_group_id`,
  `parent_transaction_id`, `child_transaction_ids` (tuple), `reason`,
  `source_command`.
- `LEDGER_TRANSACTION_MERGED = "ledger.transaction.merged"`. Emitted once
  per `merge` op. Payload carries `split_group_id`,
  `merged_transaction_id`, `source_child_ids` (tuple),
  `parent_transaction_id`, `reason`, `source_command`.

Both events emit the **parent transaction id** as `object_id` so the
existing `for_object(parent_id)` query returns the full lineage chain in
one call. Re-emission idempotency is guaranteed by the existing
`BucketEvent.event_id` SHA-256 content-addressing; an identical payload
produces an identical event id and is collapsed by `save_many`.

## Decision 4 -- Destructive-op UX charter

Three tiers, applied uniformly to every CLI verb:

**Tier 1 -- reversible state transitions** (`archive`, `stash`). Require
`--yes` (regression fix: today these verbs accept no guard at all). Add
`--reason` (free-text up to 500 chars) recorded into the event payload.
The inverse op is documented in the verb help text.

**Tier 2 -- semantic mutations that consume the active row** (`split`,
`merge`). Require `--yes` AND offer `--dry-run`. Without `--yes` the op
refuses, citing the locale key `cli.ledger.errors.confirm_required`.
`--dry-run` renders the planned child or merged rows through `_emit`
without mutating the catalogue.

**Tier 3 -- hard delete** (`remove`, `reset`). Require `--yes` AND offer
`--dry-run`. Already conformant today; no change beyond locale-key
alignment.

No new CLI verb may be silently destructive. The `archive` and `stash`
regression fix is bundled into this ADR implementation plan, not
deferred.

## Decision 5 -- CLI naming and event surfacing

Align the W71 CRUD spine. Rename top-level `create` to `add`, `edit` to
`update`, `read` to `view` so the top-level vocabulary matches every
sub-app. The old names are **removed**, not aliased. Hidden aliases
violate the no-legacy-compat charter and the canonical naming charter
from the apex CLI redesign ADR; this is a deliberate breaking change
because the CLI shape has not yet shipped to a 1.0.0 surface.

Two new verbs are introduced under `aeat app ledger`:

- `aeat app ledger split --id PARENT --child-amount AMOUNT --child-description DESC [--child-amount ... --child-description ... (repeatable, must match in count)] --reason REASON --yes [--dry-run]`
- `aeat app ledger merge --child-id ID --child-id ID [... --child-id ID] --reason REASON --yes [--dry-run]`

One new read verb:

- `aeat app ledger history --id ID [--include-split-siblings]` -- queries
  the existing event catalogue via `for_object()`, mirroring the
  `modelo history` rendering pattern. With `--include-split-siblings`,
  the lineage chain is fanned out to include every event whose `object_id`
  matches any sibling in the row `split_group_id`.

All sub-app services (`evidence`, `payable-invoice`, `collectible-invoice`,
`ratios`, `inventory`) MUST be extended to return `bucket_event_ids` from
their result payloads so their CLI verbs can surface audit anchors. The
backend event types already exist (`PAYABLE_INVOICE_*`,
`COLLECTIBLE_INVOICE_*`, `LEDGER_INVENTORY_*`,
`PURCHASE_INVOICE_EVIDENCE_*`); the gap is purely at the service-return
boundary. No mutation without a returned event id; no event id without a
mutation. That symmetry is the audit contract.

## Decision 6 -- `_resolve_id` and `tr()` compliance

Wrap `TransactionIdPrefixError` at the CLI boundary in four tr-keyed
messages:

- `cli.ledger.errors.id_prefix_empty`
- `cli.ledger.errors.id_prefix_not_hex`
- `cli.ledger.errors.id_prefix_not_found`
- `cli.ledger.errors.id_prefix_collision`

Every locale (en/es/ca/hu) must carry these keys with real translations
-- scaffold placeholders are forbidden. The `ledger track` verb MUST go
through `_resolve_id` like every other id-consuming verb; accepting only
the full 64-char id is inconsistent and breaks the prefix UX promise.
Fix bundled into the plan.

## Decision 7 -- Test discipline

This ADR tests are bound by the project no-tautological-tests rule.
The following patterns are **forbidden**:

- Asserting a `Decimal` output equals a hand-computed `Decimal` derived
  from the same formula the runtime executes.
- Asserting an event was emitted with a payload the test constructed
  from the same source code that builds the event.

The following patterns are **required**:

- Split invariance tested against the deterministic `split_group_id`:
  splitting the same parent with the same child amounts and narratives
  twice must produce the same group id (content-addressed reproducibility),
  and re-emission is collapsed.
- Event idempotency tested by re-emission: the second call produces an
  identical `event_id` and `save_many` collapses it.
- Re-merge round-trip tested by splitting then merging and asserting
  that the merged row content matches the parent content (same amount,
  same narrative, same direction), **without** asserting the merged id
  equals the original parent id -- the merged id is freshly
  content-addressed and that distinction is the audit guarantee.
- Finalized-modelo blocker tested by attempting destructive ops against
  modelo-referenced transactions and asserting the typed refusal raised
  by the existing guard in `_actions.py`.
- Destructive-UX tested by invoking each tier-2 and tier-3 verb without
  `--yes` and asserting the tr-rendered refusal text via the locale key,
  not via the raw English string.

## Decision 8 -- Migration discipline

No legacy `LedgerSplit` resurrection. No alias for the renamed top-level
verbs. No backwards-compat for the schema change.
`Transaction.split_lineage` ships as a real pydantic field with default
`None`. Existing bucket catalogues persisted before this change
deserialise with `split_lineage = None` because pydantic applies the
declared default at construction time -- that is the only acceptable
migration path and no helper script is provided. Extending
`TransactionLifecycleState` with `SPLIT` and `SplitRole` with `MERGED`
are real enum additions; every exhaustive switch on either enum must
handle the new members at the point of compilation, not via a
fall-through default.

## Consequences

1. Every ledger op becomes auditable via `for_object()` queries on the
   existing event store -- no new audit infrastructure needed.
2. Deterministic `split_group_id` makes re-emission idempotent and split
   reproducibility testable without parallel-formula tautology.
3. Split is irreversible at the parent identity level: re-merge creates
   a new content-addressed id. Operators must learn this; UX surfaces
   it through the `ledger history --include-split-siblings` chain.
4. Extending `TransactionLifecycleState` with `SPLIT` is a breaking enum
   change. Every exhaustive switch (list filters, classification
   pipelines, finalized-modelo guard) must handle it at compile time.
5. The `archive` and `stash` UX regression is fixed as part of this ADR
   plan, not deferred -- silent destruction was never sanctioned.
6. Renaming `create` to `add`, `edit` to `update`, `read` to `view` is a
   real breaking change to the CLI surface. Users on prior builds must
   adapt. No aliases mitigate this; the charter forbids them.
7. Sub-app services gain a `bucket_event_ids` return-payload contract.
   Every mutation in evidence, payable-invoice, collectible-invoice,
   ratios, and inventory must emit at least one event or refuse the op.
8. Every locale gains four new keys for `_resolve_id`. Translation work
   is real, not scaffolded; the plan must allocate locale time.

## Alternatives considered

**Parallel `SplitGroup` aggregate persisted in its own catalogue.**
Rejected: the catalogue would no longer be the single source of truth
for row lineage; the existing `for_object()` event query would need a
parallel index to traverse the group; persistence would double-write
through two `save_many` boundaries; and the deterministic content-address
of a row would no longer carry its lineage by construction.

**Resurrect the deleted `LedgerSplit` workflow-layer annotation.**
Rejected: the no-backwards-compat charter forbids legacy resurrection,
and the prior workflow-layer location was the wrong layer in the first
place (annotation lived on `UserCliState`, not the canonical row). The
deletion in commit `042824d2` was correct and stays.

**Use `MIXED` plus `business_pct` as the split primitive.** Rejected:
this only allows one ratio per row and produces no N-way split with
independent classifications, evidence links, and category bindings. The
mandate is N children with conscious per-row tax treatment.

**Re-merge produces the same id as the original parent.** Rejected:
this violates the content-addressing invariant of `transaction_id` (a
64-char sha256 of amount, narrative, provider, value-date). If the
merged row content differs from the parent content, the id must differ;
if the content is identical, the merge is a content-equal restoration
and the parent ARCHIVED state suffices for audit. Either way, fresh
content-addressing is the only honest answer.

**Soft-delete via a new lifecycle state on the children instead of
`SPLIT` on the parent.** Rejected: muddles "the parent should not
appear in default lists" with "the parent is gone for good"; `SPLIT`
on the parent correctly models a frozen-but-present row whose ACTIVE
successors are its children, which is what split actually is.

## Open questions for the plan

Deferred to the implementation plan document, not decided here:

- Step ordering: enum additions (`SplitRole`,
  `TransactionLifecycleState.SPLIT`, two `BucketEventType` members)
  land before the record-shape field; record-shape lands before the
  action functions; actions land before the CLI verbs; CLI verbs land
  before locale population; tests bracket every layer.
- Whether the plan is one ADR-execution doc or split across multiple
  wave records.
- Test fixture strategy for content-addressed id assertions (in
  particular how to seed `split_group_id` deterministically without
  leaking the formula into the assertion).
- The cohort of existing tests that need updating when the top-level
  renames land -- every CLI smoke test that exercises `ledger create`,
  `ledger edit`, or `ledger read` must be rewritten, not aliased.
