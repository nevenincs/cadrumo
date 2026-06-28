---
tags:
  - '#plan'
  - '#ledger-transaction-lifecycle'
date: '2026-05-14'
modified: '2026-05-14'
tier: L2
related:
  - '[[2026-05-14-ledger-transaction-lifecycle-adr]]'
  - '[[2026-05-14-ledger-transaction-lifecycle-research]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---


# `ledger-transaction-lifecycle` plan

## Proposed Changes

Land full CRUD plus split and re-merge for bucket-scoped ledger
transactions, with traceable lineage, atomic event emission, and
tr-rendered user-facing strings in every locale. Add the
`TransactionLifecycleState.SPLIT` member, a new `SplitRole` enum, a
frozen `SplitLineage` field on `Transaction`, two new `BucketEventType`
members (`LEDGER_TRANSACTION_SPLIT`, `LEDGER_TRANSACTION_MERGED`), the
matching `split_transaction` and `merge_transactions` application
actions, three new CLI verbs (`split`, `merge`, `history`), the top-
level rename `create`->`add` / `edit`->`update` / `read`->`view` with no
aliases, the destructive-UX regression fix on `archive` and `stash`, the
tr-compliance wrap of `TransactionIdPrefixError` with four locale keys,
and the sub-app `bucket_event_ids` return-payload contract. Every Step
lands fully: no shims, no half-implementations, no deprecated paths
left dangling. Steps execute sequentially because later Steps depend on
earlier Steps' types, actions, and events.

## Steps

### Phase `P01` - ledger-transaction-lifecycle full-CRUD-plus-split-and-merge delivery

Deliver the ADR's eight decisions end-to-end across the domain, event,
application, CLI, and locale layers; ten Steps run in fixed order with
green tests between Steps.

- [x] `P01.S01` - extend `TransactionLifecycleState` with `SPLIT` and add `SplitRole(PARENT, CHILD, MERGED)`; `update every exhaustive switch on `TransactionLifecycleState` enumerated by pre-Step swarm (currently `src/aeat/application/ledger/_actions.py` lines 419/450/940/958-960/991/1434/1560/2022, `_preflight.py:111`, `src/aeat/application/aggregation/_iva_ledger.py:163`, `_renta_ledger.py:199`, plus tests); `src/aeat/domain/transactions/_enums.py`.
- [x] `P01.S02` - introduce `SplitLineage` frozen pydantic v2 record (`split_group_id: str(64-hex)`, `role: SplitRole`, `sibling_transaction_ids: tuple[str, ...]`) and `Transaction.split_lineage: SplitLineage | None = None`; `add `derive_split_group_id(parent_id, children_seed)` deterministic helper; `src/aeat/domain/transactions/_models.py`.
- [x] `P01.S03` - add `LEDGER_TRANSACTION_SPLIT` and `LEDGER_TRANSACTION_MERGED` to `BucketEventType` (parent id as `object_id`, payload carries `split_group_id` plus child/parent ids plus `reason` plus `source_command`); `refresh taxonomy comment; `src/aeat/domain/buckets/_event.py`.
- [x] `P01.S04` - implement `split_transaction(*, bucket_id, transaction_id, children, actor, source_command, reason, occurred_at=None)` with `SplitChildCommand` record and `SplitTransactionResult`; `enforce parent-ACTIVE, finalized-modelo, sum-equals-parent, direction-inherited invariants; persist via `_save_transaction_catalogue_and_events`; `src/aeat/application/ledger/_actions.py`.
- [x] `P01.S05` - implement `merge_transactions(*, bucket_id, child_ids, actor, source_command, reason, occurred_at=None)` with `MergeTransactionsResult`; `enforce same-group, parent-SPLIT, no-finalized-modelo, archive-children, archive-parent, content-address fresh merged row invariants; emit one event anchored on the parent id; `src/aeat/application/ledger/_actions.py`.
- [x] `P01.S06` - rename `create`->`add` / `edit`->`update` / `read`->`view` with no aliases; `add `split`, `merge`, `history` verbs (each with `--yes`, `--reason`, plus `--dry-run` for `split` and `merge`); add `--yes` and `--reason` to `archive` and `stash`; route `track` through `_resolve_id`; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `P01.S07` - wrap `TransactionIdPrefixError` at the CLI boundary into the four locale keys `cli.ledger.errors.id_prefix_empty`, `id_prefix_not_hex`, `id_prefix_not_found`, `id_prefix_collision`; `src/aeat/entrypoints/cli/_ledger.py` and `src/aeat/application/ledger/_id_resolution.py`.
- [x] `P01.S08` - extend sub-app result models to carry `bucket_event_ids: tuple[str, ...]` and emit the appropriate `LEDGER_INVENTORY_*` / `PAYABLE_INVOICE_*` / `COLLECTIBLE_INVOICE_*` / `PURCHASE_INVOICE_EVIDENCE_*` events on every mutation; `surface in CLI text and JSON; `src/aeat/application/ledger/_evidence.py`, `_business_operation_invoice.py`, `_inventory.py`, `_ratios.py`.
- [x] `P01.S09` - run `uv run --no-sync python -m aeat.locales scaffold`, then hand-write real translations in `en.yml`, `es.yml`, `ca.yml`, `hu.yml` for every key introduced across S01-S08 (new verbs, args, errors, dry-run, confirm-required); `no scaffold placeholders survive; `src/aeat/locales/{en,es,ca,hu}.yml`.
- [x] `P01.S10` - run `uv run --no-sync pytest src/aeat/application/ledger/ src/aeat/entrypoints/cli/ -q` and fix every rename-induced test (every `["create", ...]`, `["edit", ...]`, `["read", ...]` invocation flipped); `run `uv run --no-sync python -m aeat.locales audit` and confirm `ok` for every locale; zero new failures`.

## Parallelization

All ten Steps are strictly sequential. S02 depends on S01's enums; S04
and S05 depend on S02's `SplitLineage` and S03's events; S06 depends on
S04 and S05's actions; S07 depends on S06's verb wiring; S08 is
independent of split/merge but bundles cleanly after S06; S09 collects
every key introduced by S01-S08; S10 verifies the full stack. Within
the Phase, no Step starts before its predecessor's tests are green.

## Verification

The plan is complete when every Step row is checked and the following
mission criteria hold:

- `uv run --no-sync pytest src/aeat/application/ledger/ src/aeat/entrypoints/cli/ -q` is green.
- `uv run --no-sync python -m aeat.locales audit` reports `ok` for `en`, `es`, `ca`, `hu`.
- `aeat app ledger create`, `aeat app ledger edit`, `aeat app ledger read` raise typer 404 (renamed, not aliased).
- `aeat app ledger split` and `aeat app ledger merge` refuse without `--yes` and render via the `cli.ledger.errors.confirm_required` tr key.
- `aeat app ledger history --id <prefix>` returns the `LEDGER_TRANSACTION_*` chain for parent/children via `for_object()`.
- Split-then-merge round-trip: merged row content equals parent content; merged id differs from parent id (content-addressed afresh).
- Re-emission of identical split or merge inputs produces identical `event_id` and is collapsed by `save_many` (idempotency).
- Every sub-app mutation returns a non-empty `bucket_event_ids` tuple.
- Existing persisted catalogues round-trip with `split_lineage=None` by pydantic default (no migration helper required).
- Commit messages follow project convention (lowercase imperative one-line subject; no `--no-verify`; no Claude Code attributions).

## Acceptance criteria per Step

- S01: files = `_enums.py`; new tests in `test_enums` (membership + lifecycle-state round-trip); touched = every callsite enumerated by the pre-S01 swarm to handle `SPLIT` exhaustively.
- S02: files = `_models.py`; new tests in `test_models.py` (deterministic `split_group_id`, serialise round-trip, default-None deserialisation of legacy payload); touched = `Transaction` construction tests for the new optional field.
- S03: files = `_event.py`; new tests in `domain/buckets/test_event.py` (enum count, `for_object()` parent-id lookup, content-addressed `event_id` idempotency).
- S04: files = `application/ledger/_actions.py`, `_models.py`; new tests in `application/ledger/test_actions.py` (invariant enforcement matrix; idempotent re-emission; finalized-modelo refusal; sum-mismatch refusal); touched = `_update_event_specs` neighbours where the new path co-locates.
- S05: files = `application/ledger/_actions.py`; new tests in `application/ledger/test_actions.py` (round-trip, cross-group refusal, partial-group refusal, fresh merged id).
- S06: files = `entrypoints/cli/_ledger.py`; new tests in `entrypoints/cli/test_ledger_verbs.py` (each verb's surface; destructive-UX refusal; tr-rendered help; rename 404 tests); touched = every existing CLI test referencing the old verb names.
- S07: files = `entrypoints/cli/_ledger.py`, `application/ledger/_id_resolution.py`; new tests cover all four error paths in each locale.
- S08: files = `application/ledger/{_evidence,_business_operation_invoice,_inventory,_ratios}.py`; new tests on each service's result model carrying `bucket_event_ids` and on `for_bucket()` finding the new events.
- S09: files = `src/aeat/locales/{en,es,ca,hu}.yml`; verified by `python -m aeat.locales audit`.
- S10: no source files changed beyond the cohort touched by S01-S09; only test-call rewrites against the renamed verbs.

## Risk register

- Schema evolution: `Transaction.split_lineage` defaults to `None`, so persisted catalogues deserialise unchanged; mitigation = a serialisation round-trip test pinned in S02.
- Enum exhaustiveness: every `match`/`if` on `TransactionLifecycleState` must learn `SPLIT`; mitigation = pre-S01 swarm enumerates every callsite (see S01 row for the explicit list), and S01 patches them all in one Step.
- Locale parity: four locales gain four error keys plus the three new verb surfaces; mitigation = real translations land in S09 before S10's audit gate.
- Test bit-rot from the top-level rename: every `["create", ...]`/`["edit", ...]`/`["read", ...]` invocation breaks; mitigation = pre-S06 swarm enumerates every test callsite; S06 flips them; S10 confirms.
- Finalized-modelo blocker interaction: split and merge interact with the existing sealed-calculation guard; mitigation = explicit pass and refusal test cases in S04 and S05.
- Event idempotency: identical re-emission must collapse; mitigation = round-trip test in S03 (event level) and S04/S05 (action level).
- `_resolve_id` integration in `track`: latent inconsistency; mitigation = regression test in S06 asserting `track <prefix>` works.
- Sub-app emission gap: some sub-app mutations have no emitter today; mitigation = S08 bundles the emitter fix with the result-model extension so no mutation lands without an event id.

## Out of scope

- Bulk split across N parents in one CLI op (N=1 only).
- Three-way merge across different `split_group_id`s (single-group only; refused).
- UI/TUI surfaces (CLI verb surface only).
- Live-AEAT consequence handling (split/merge are local-state only; LiveSubmitForbidden charter unchanged).
- Sub-app verb-vocabulary renames (already aligned with W71 spine).
- Backwards-compat aliases for renamed verbs (charter forbids).

## Step status table

| Step | File group | Status | Owner |
| --- | --- | --- | --- |
| P01.S01 | `domain/transactions/_enums.py` + exhaustive-switch callsites | pending | TBD |
| P01.S02 | `domain/transactions/_models.py` | pending | TBD |
| P01.S03 | `domain/buckets/_event.py` | pending | TBD |
| P01.S04 | `application/ledger/_actions.py` (split) | pending | TBD |
| P01.S05 | `application/ledger/_actions.py` (merge) | pending | TBD |
| P01.S06 | `entrypoints/cli/_ledger.py` (rename + new verbs) | pending | TBD |
| P01.S07 | `entrypoints/cli/_ledger.py` + `application/ledger/_id_resolution.py` | pending | TBD |
| P01.S08 | sub-app services (`_evidence`, `_business_operation_invoice`, `_inventory`, `_ratios`) | pending | TBD |
| P01.S09 | `src/aeat/locales/{en,es,ca,hu}.yml` | pending | TBD |
| P01.S10 | full ledger + CLI pytest sweep and locales audit | pending | TBD |
