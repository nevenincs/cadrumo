---
tags:
  - "#research"
  - "#ledger-transaction-lifecycle"
date: "2026-05-14"
modified: '2026-05-14'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
---

# ledger-transaction-lifecycle research

Consolidates ground-truth findings from three parallel audits of the ledger
backend domain, the bucket-event system, and the ledger CLI surface.
Establishes the factual baseline that the upcoming ADR on full
ledger-transaction CRUD plus split and re-merge with traceable lineage must
build on.

## 1. Mandate

The CLI must support add, edit, remove, split, and re-merge for bucket-scoped
ledger transactions. Every operation must:

- define its semantics, including destructiveness and reversibility;
- emit bucket-event-history events so the existing audit surface picks them up;
- flow user-facing strings through tr(...);
- refuse half-implementations or legacy-compat shims.

No tautological tests. Destructive operations require explicit confirmation UX.

## 2. Existing record shape (ground truth from backend audit)

The canonical record is Transaction in src/aeat/domain/transactions/_models.py
at line 394. Its transaction_id is a deterministic SHA-256 over
(amount, narrative, provider_id, value_date) - content-addressed, declared at
lines 38-60.

There are three lifecycle values declared in TransactionLifecycleState at
src/aeat/domain/transactions/_enums.py lines 58-63:

- ACTIVE
- ARCHIVED
- STASHED

The same Transaction carries all three states; there is no separate
ArchivedTransaction or StashedTransaction type.

The only cross-id reference on Transaction today is
TransactionEditLineageEntry.previous_transaction_id at _models.py lines
308-313, which records the prior id when a full-replace edit changes the
deterministic hash. It is consumed at _actions.py lines 1533-1536 so
finalized-modelo calculations can resolve historical ids.

There is no parent_transaction_id, child_transaction_ids, split_group_id,
derived_from, composite, subdivision, split_ratio, or merge_group field
anywhere on Transaction or TransactionCatalogue.

The deleted LedgerSplit model (removed in commit 042824d2) was a
workflow-layer annotation (business_share + personal_share = 1) attached to
UserCliState, never persisted inside the Transaction domain model. It is gone
with zero residue. Commit f3526196 was a pure CLI-helper refactor that moved
_resolve_split and _resolve_skip_flag into helpers; it did not delete backend
code.

MIXED + business_pct (a single ratio on one monolithic row) is the closest
existing partial-business knob, but it does not produce N child rows summing
to the parent.

## 2.5 Prior art: the deleted LedgerSplit and the split→allocate rename

Two prior ADRs explicitly discussed "split" but meant something different from N-way row splitting:

- `[[2026-05-02-aeat-cli-redesign-adr]]` originally specified `aeat app ledger edit --split business=SHARE --split personal=SHARE` — a single-row allocation knob (one ratio, two shares summing to 1).
- `[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]` explicitly renamed `split` → `allocate` and stated "the prior 'split' framing implied row-splitting semantics, which the verb does not perform."

The `LedgerSplit(BaseModel)` model (introduced commit `f55ba4c8`, refactored `f3526196`, deleted `3a08f880` on 2026-05-14) carried `business_share` + `personal_share` summing to 1 — it was a **workflow-layer annotation** on `LedgerReviewRecord` in the now-deleted `user_cli.py` shim. It was **never persisted to `Transaction`**. Commit `19ccb0d5` scrubbed `--split` from the CLI.

The current `update_ledger_review` at `src/aeat/application/review/_actions.py:17-29` is a **live guard** that raises `ReviewError("ledger allocation must be written through transaction business_pct")` if any split overlay is passed. The companion test `test_update_ledger_review_refuses_skip_and_split_overlay` at `test_actions.py:40` asserts this refusal. Any new split work must replace this guard, not bypass it.

**This research's "split" is a different concept from the deleted feature.** What is proposed here is true N-way row splitting: one parent transaction produces N child transactions whose amounts sum to the parent's amount, with traceable lineage IDs and independent classifications per child. The earlier "split"-named feature was always single-row allocation (`business_pct`). Future readers should not interpret this work as resurrecting deleted code; it is a wholly new primitive that the project has never carried.

One dangling test exists: `src/aeat/entrypoints/cli/test_workflow_surface.py::test_ledger_split_is_nested_inside_edit` (line 415-421) asserts `--split` is in `ledger edit --help`. The deletion in `19ccb0d5` made it dead; the plan's Step 6 explicitly removes/rewrites this test as part of the rename pass.

## 3. Existing CRUD actions (ground truth from backend audit)

Public action functions in src/aeat/application/ledger/_actions.py:

- create_manual_transaction - line 129.
- update_manual_transaction - line 971. Full-replace. Guards: target must be
  ACTIVE, finalized-modelo blocker check, mutation-signature diff check.
- update_manual_transaction_fields - line 1085. Thin patch wrapper over
  update_manual_transaction.
- attach_manual_transaction_evidence - line 171.
- archive_manual_transaction - line 401. Reversible via inverse transition in
  _transition_manual_transaction_lifecycle at line 1407.
- stash_manual_transaction - line 432. Same pattern as archive.
- remove_manual_transaction - line 463. Hard delete with cascading detach and
  dry_run support.
- reset_ledger_catalogue - line 558. Bulk hard delete.
- import_ledger_transactions - line 229; plus import_ledger_source at line 311.
- export_ledger_transactions - line 677.

Finalized-modelo blocker: every destructive op consults _actions.py lines
500-516 to refuse removal of transactions referenced by a finalized modelo
calculation.

## 4. Bucket-event coverage (ground truth from event audit)

The event enum is declared in src/aeat/domain/buckets/_event.py lines
54-136. The existing LEDGER_TRANSACTION_* members are:

- CREATED
- IMPORTED
- UPDATED
- CLASSIFIED
- ALLOCATED
- REMOVED
- ARCHIVED
- STASHED
- EXPORTED
- IMPORT_DIAGNOSTIC_RECORDED
- CATALOGUE_RESET
- SANITIZATION_COMPLETED

There is no LEDGER_TRANSACTION_SPLIT, LEDGER_TRANSACTION_MERGED, or
LEDGER_TRANSACTION_REASSIGNED member.

Event contract: BucketEvent at _event.py lines 187-233 carries event_id
(SHA-256 content-addressed, idempotent re-emit), bucket_id, event_type,
occurred_at, actor, object_type, object_id, payload_version, and payload.

Multi-event-per-operation is the established pattern:
update_manual_transaction emits up to four distinct event types per call via
_update_event_specs at _actions.py line 1853.

Atomic persistence: _save_transaction_catalogue_and_events at _actions.py
lines 2283-2296 writes catalogue plus events in one save_many.
_primary_lineage_event_id at _actions.py line 2320 picks the lineage anchor
for the transaction.

The history surface is read at _modelo.py lines 1826-1878 for the
modelo-history verb; the same pattern can wrap a new ledger-history verb.

Gap: the noun-group sub-app services (evidence, payable_invoice,
collectible_invoice, ratios, inventory) do not return bucket_event_ids in
their result payloads. Backend extension required.

## 5. CLI surface (ground truth from CLI audit)

Top-level verbs in src/aeat/entrypoints/cli/_ledger.py:

- create line 129
- edit line 225
- classify line 275
- allocate line 317
- attach line 356
- archive line 388
- stash line 410
- remove line 432
- reset line 469
- export line 503
- list line 548
- read line 579
- status line 608
- track line 644
- import line 673
- review line 742

Sub-apps: ratios, payable-invoice, collectible-invoice, inventory, evidence.

Naming drift: top-level uses create / edit / read; sub-apps use
add / update / view. The W71 CRUD spine is add / remove / update / view / list.

Destructive-UX inconsistency:

- remove and reset require both --yes and --dry-run - gold standard.
- archive and stash have no guard at all - silent state mutation, regression
  against the destructive-op charter.
- Sub-app remove verbs use --yes only (no --dry-run).

_resolve_id at _ledger.py lines 91-93 accepts hex prefixes via
resolve_transaction_id at application/ledger/_id_resolution.py lines 55-92.
It raises TransactionIdPrefixError with plain English text - not tr-wrapped;
the wrapper does not catch the error, so Typer surfaces a raw Python exception.
The ledger-track verb at line 651 skips _resolve_id entirely.

_emit at entrypoints/cli/_common.py lines 47-51 is the single text-or-JSON
rendering boundary; every verb must funnel through it.

## 6. Gaps the next work has to close

1. No split primitive anywhere in the domain model: no parent, child, or
   split-group field on Transaction.
2. No re-merge primitive: the inverse op of split is also absent.
3. No LEDGER_TRANSACTION_SPLIT or LEDGER_TRANSACTION_MERGED event types in the
   enum.
4. archive and stash are silently destructive: no confirmation, no dry-run.
5. Sub-app services do not return bucket_event_ids: the CLI cannot surface
   their audit anchors.
6. _resolve_id errors leak raw Python text instead of tr-rendered messages.
7. The ledger-track verb skips _resolve_id: it accepts only the full id,
   inconsistent with every other id-consuming verb.
8. No ledger-history verb even though the event store and the modelo-history
   pattern already exist.

## 7. Open design questions for the ADR

1. What is the canonical record shape for a split-derived child transaction?
   Embedded split_lineage: SplitLineage field, or a separate SplitGroup
   aggregate persisted in a parallel catalogue?
2. How is split-invariance enforced? Sum of child amounts must equal parent
   amount (and direction must agree); should it allow rounding tolerance for
   Decimal cents?
3. Is a split parent kept ACTIVE, transitioned to a new SPLIT lifecycle state,
   or transitioned to ARCHIVED with a back-reference?
   TransactionLifecycleState may need a new member.
4. Is re-merge symmetric (any N children produce a parent) or restricted to
   the same group? Does merge restore the original parent id, or create a new
   merged-id by content-addressing?
5. Does split clone all classification, evidence, and attachment links into
   each child, or require explicit per-child reassignment?
6. What is the destructive-op UX contract for split and re-merge? --yes plus
   --dry-run consistent with remove?
7. How does the finalized-modelo blocker interact with split: do children
   inherit blocked status, or is split itself blocked if the parent is
   referenced?
8. Do split events carry a split_group_id payload key so for_object queries
   find all children plus the parent in one query?

## 8. References

Related vault documents are linked through the related frontmatter field
above. The apex CLI redesign ADR (2026-05-12-cli-workflow-redesign-adr) and
the current epic plan (2026-05-13-cli-workflow-redesign-epic-plan) are the
immediate consumers of this research. A vault-list run filtered by the
ledger feature on 2026-05-14 returned no prior ledger-transaction-lifecycle
research or ADR documents; the closest neighbour is the
2026-05-08-ledger-renta-pipeline-adr pair, which addresses pipeline shape
rather than transaction lifecycle and is not a direct dependency.
