---
tags:
  - '#plan'
  - '#ledger-interface-contract'
date: '2026-06-10'
tier: L3
related:
  - '[[2026-06-10-ledger-interface-contract-adr]]'
  - '[[2026-06-10-ledger-interface-contract-research]]'
---


# `ledger-interface-contract` `Uniform ledger response envelope, ID resolution, and sorting` plan

## Wave `W01` - Persistence boundary extension (D6)

Add created_at and modified_at to Transaction and stamp them on add and every mutating edit; cover the change with a strict save-load-equality roundtrip test with both fields populated non-default. This Wave is a prerequisite for the honest temporal sort in W03.

### Phase `W01.P01` - Add created_at and modified_at to Transaction with roundtrip gate

Extend the Transaction persistence record, stamp fields at add/edit, and validate with a strict anti-tautology roundtrip test.

- [ ] `W01.P01.S01` - Add created_at and modified_at datetime fields to Transaction model with UTC-aware type; `set created_at at model construction, stamp modified_at on every mutating field update; `src/aeat/domain/transactions/_models.py`.
- [ ] `W01.P01.S02` - Stamp created_at on ledger add path and modified_at on every mutation application site (update, classify, allocate, attach, doclink, archive, stash, restore, link); `src/aeat/domain/transactions/_models.py, src/aeat/application/ledger/_actions.py, src/aeat/application/ledger/_actions_manual.py`.
- [ ] `W01.P01.S03` - Add created_at and modified_at to LedgerTransactionReviewPayload and LedgerTransactionPayload application projections so the fields appear in typed mutation result and list row; `src/aeat/application/ledger/_models.py, src/aeat/application/ledger/_actions_manual.py`.
- [ ] `W01.P01.S04` - Write strict save-load-equality roundtrip test for Transaction with both created_at and modified_at populated non-default; `add anti-tautology proof that mutates the encrypted payload and asserts ValidationError; `src/aeat/domain/transactions/tests/test_repository_roundtrip.py`.

## Wave `W02` - Mutation payload uniformity (D1, D3, D4)

Normalise every single-transaction mutation verb to return the uniform quintet via _LedgerMutationResult; collapse the duplicate _resolve_id shim to one shared helper; convert every mutation verb id input from --id Option to positional Argument and remove the Option outright. Depends on W01 completion only at the enum level (D4 enum lands in core/).

### Phase `W02.P02` - Collapse _resolve_id shim and uniform positional id input (D3, D4)

Merge the two duplicate CLI _resolve_id bodies into one shared helper; convert every mutation verb's id input from --id Option to positional Argument.

- [x] `W02.P02.S05` - Merge the _resolve_id body from _ledger_lifecycle_cli.py into the single authoritative _resolve_id helper in _ledger.py; `delete the duplicate from _ledger_lifecycle_cli.py; `src/aeat/entrypoints/cli/_ledger.py, src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `W02.P02.S06` - Convert every mutation verb id parameter from typer.Option('--id') to a positional typer.Argument in _ledger.py: update, classify, allocate, attach, doclink; `src/aeat/entrypoints/cli/_ledger.py`.
- [x] `W02.P02.S07` - Convert every mutation verb id parameter from typer.Option('--id') to positional typer.Argument in _ledger_lifecycle_cli.py: attach/doclink, archive, stash, restore, remove, split, merge; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `W02.P02.S08` - Convert classify and review optional --id Option to optional positional typer.Argument consistent with D4; `remove --id Option outright from all converted verbs (no-legacy-compatibility); `src/aeat/entrypoints/cli/_ledger.py, src/aeat/entrypoints/cli/_ledger_review_cli.py`.
- [x] `W02.P02.S09` - Update CLI conformance test to assert every single-transaction verb accepts a positional id and no --id Option; `run uv run --no-sync pytest src/aeat/entrypoints/cli/tests/ -x -q to verify gate; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.

### Phase `W02.P03` - Mutation payload quintet normalisation (D1)

Make LedgerAddResult subclass _LedgerMutationResult; add transaction slot to LedgerLinkResult; replace LedgerClassifyResult all-optional union with discriminated branches.

- [ ] `W02.P03.S10` - Change LedgerAddResult to subclass _LedgerMutationResult so it inherits the review_status field; `verify add emit site populates review_status; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W02.P03.S11` - Add transaction: TransactionPayload field to LedgerLinkResult; `remove bare dict evidence_update field and replace with a typed payload; update link emit site to populate both new fields; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W02.P03.S12` - Replace LedgerClassifyResult all-optional union with discriminated branches: LedgerClassifySingleResult (subclassing _LedgerMutationResult), LedgerClassifyBulkResult, LedgerClassifyLlmSuggestResult, LedgerClassifyLlmSaturateResult; `update register_schema decorator to cover all four; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [ ] `W02.P03.S13` - Update classify emit site to emit the correct discriminated branch payload per execution path; `run pytest on test_ledger_verb_spine.py and JSON-contract registry gate to confirm all branches registered; `src/aeat/entrypoints/cli/_ledger.py, src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py`.

## Wave `W03` - List/read payload typing and sort (D2, D5, D7)

Replace every list[dict[str,object]] wire boundary with typed OutputSchema subclasses; add --sort-by/--sort-order to project_ledger_list; reserve LedgerTransactionParticipationPayload for C7; pin D7 pipeable JSON. D5 sort co-lands with or rebases onto C6 filter on project_ledger_list. Depends on W01 (created_at/modified_at fields present for sort key) and W02 (classify branch normalised before LedgerListResult is typed).

### Phase `W03.P04` - LedgerSortField enum and sort capability in project_ledger_list (D5)

Declare LedgerSortField StrEnum in core/; add --sort-by/--sort-order params to project_ledger_list; apply stable sort with transaction_id tie-break.

- [ ] `W03.P04.S14` - Declare LedgerSortField StrEnum (date, value_date, amount, description, created_at, modified_at, classified_at, lifecycle_state, classification) and LedgerSortOrder StrEnum (asc, desc) in core/; `src/aeat/core/`.
- [ ] `W03.P04.S15` - Add sort_by: LedgerSortField | None and sort_order: LedgerSortOrder to project_ledger_list signature; `apply stable sort after filter and --group selection with transaction_id as final tie-break; remove legacy by_group secondary sort on hash key; `src/aeat/entrypoints/cli/_ledger_list.py`.
- [ ] `W03.P04.S16` - Expose --sort-by and --sort-order as Typer parameters on the ledger list command, typed to LedgerSortField and LedgerSortOrder enums so CLI renders Choice([...]); `thread params through to project_ledger_list call; `src/aeat/entrypoints/cli/_ledger.py`.
- [ ] `W03.P04.S17` - Write a real-behaviour sort-stability test: populate a catalogue with multiple rows sharing an equal sort key; `assert the stable ordering plus transaction_id tie-break holds under both asc and desc; `src/aeat/entrypoints/cli/tests/`.

### Phase `W03.P05` - Typed list/read row payloads replace bare-dict boundaries (D2)

Define LedgerListRowPayload and replace all list[dict[str,object]] wire boundaries with typed OutputSchema subclasses across list, history, track, import, export, preflight, ratios-eligible, business-invoice list, inventory list, evidence list, and link result.

- [ ] `W03.P05.S18` - Define LedgerListRowPayload as an OutputSchema subclass carrying full_id, display_id, date, non-negative amount, direction, description, review_status, lifecycle_state, business_classification, group_label, created_at, modified_at; `project from LedgerTransactionReviewPayload plus the three extra keys; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [ ] `W03.P05.S19` - Replace LedgerListResult.rows: list[dict[str,object]] with rows: list[LedgerListRowPayload]; `update LedgerListProjection and _ledger_list_rows_and_lines to construct typed rows; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_list.py`.
- [ ] `W03.P05.S20` - Define LedgerHistoryEventPayload as OutputSchema and replace LedgerHistoryResult.events: list[dict[str,object]] with typed list; `update history emit site; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_read_cli.py`.
- [ ] `W03.P05.S21` - Define LedgerTrackingPayload as OutputSchema and replace LedgerTrackResult.tracking: dict[str,object] with the typed payload; `update track emit site; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_read_cli.py`.
- [ ] `W03.P05.S22` - Define LedgerImportTransactionRefPayload as OutputSchema and replace LedgerImportPayload.imported_transaction_refs, skipped_transaction_refs, likely_duplicate_transaction_refs: list[dict] with typed lists; `update import emit site; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_import_cli.py`.
- [x] `W03.P05.S23` - Define LedgerExportRowPayload as OutputSchema and replace LedgerExportPayload.rows: list[dict] with typed list; `update LedgerExportPayload.from_result to construct typed rows; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W03.P05.S24` - Define LedgerPreflightPeriodPayload and LedgerPreflightIssueDetailPayload as OutputSchema; `replace LedgerPreflightResult.period: dict and issues: list[dict] with typed fields; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `W03.P05.S25` - Define RatiosEligibleRowPayload as OutputSchema and replace RatiosEligibleResult.rows: list[dict] with typed list; `update ratios-eligible emit site; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_ratios_cli.py`.
- [x] `W03.P05.S26` - Replace BusinessInvoiceListResult.rows: list[dict] with rows: list[BusinessInvoiceRecordPayload] for both PayableInvoiceListResult and CollectibleInvoiceListResult; `update business-invoice list emit sites; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`.
- [x] `W03.P05.S27` - Replace InventoryListResult.rows: list[dict] with rows: list[InventoryLedgerPayload]; `replace InventoryLedgerPayload.opening_layers and period_movements: list[dict] with typed OutputSchema subclasses; update inventory list emit site; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_inventory_cli.py`.
- [x] `W03.P05.S28` - Replace EvidenceListResult.rows: list[dict] with rows: list[EvidenceRecordPayload]; `update evidence list emit site; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_evidence_cli.py`.
- [x] `W03.P05.S29` - Define RatiosValidateFindingPayload as OutputSchema and replace RatiosValidateResult.findings: list[dict] with typed list; `update ratios-validate emit site; `src/aeat/entrypoints/cli/_ledger_payloads.py, src/aeat/entrypoints/cli/_ledger_ratios_cli.py`.
- [x] `W03.P05.S30` - Run JSON-contract registry gate and mypy/pyright check to confirm all former bare-dict boundaries now produce strict OutputSchema subclasses and no new dict[str,Any] surfaces were introduced; `src/aeat/entrypoints/cli/tests/, src/aeat/entrypoints/cli/_ledger_payloads.py`.

### Phase `W03.P06` - Reserve LedgerTransactionParticipationPayload and pin D7 pipeable JSON (D7)

Declare the C7 slot schema stub in _ledger_payloads.py; assert via the JSON-contract registry gate that every ledger verb emits a SchemaEnvelope so D7 is pinned.

- [ ] `W03.P06.S31` - Declare LedgerTransactionParticipationPayload as an OutputSchema stub in _ledger_payloads.py with a docstring noting it is the reserved slot for the C7 participation read verb; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [ ] `W03.P06.S32` - Assert via the JSON-contract registry gate that every registered ledger command path (all 26 verbs) returns a SchemaEnvelope; `run pytest src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py to pin D7 contract; `src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py`.

## Description

This plan executes the seven decisions settled in `2026-06-10-ledger-interface-contract-adr` against the `aeat app ledger` CLI surface. The research (`2026-06-10-ledger-interface-contract-research`) established three divergence classes in the 26-verb surface: inconsistent single-transaction mutation payloads, bare `list[dict[str,object]]` wire boundaries that violate `aeat-architecture-boundaries`, and a split id-input convention with two duplicate resolver shims and no sort capability on the list surface.

W01 lays the persistence foundation: `created_at` and `modified_at` are added to `Transaction` as clean-break fields (no migration - pre-beta, `no-legacy-compatibility`) and stamped at every mutation site. A strict roundtrip + anti-tautology test locks the encrypted-bucket boundary before any payload shape change depends on the new fields.

W02 delivers payload quintet uniformity and id-input convergence. The duplicate `_resolve_id` shim is collapsed to one helper; every mutation verb's `--id` Option is replaced by a positional `typer.Argument` (outright removal, no alias); `LedgerAddResult` subclasses `_LedgerMutationResult`; `LedgerLinkResult` gains a `transaction` slot and typed evidence payload; and `LedgerClassifyResult`'s all-optional union is replaced by four discriminated branch classes.

W03 types every bare-dict list boundary, adds `--sort-by`/`--sort-order` to `project_ledger_list` (stable, `transaction_id` tie-break, `LedgerSortField` StrEnum in `core/` so Typer renders `Choice`), reserves the C7 participation slot, and pins D7 pipeable JSON via the existing registry gate.

## Steps







## Parallelization

Waves are sequenced: W01 must land before W02 (mutation stamping is required before mutation verbs are converted); W02 must land before W03 (classify branch normalisation must precede `LedgerListResult` typing, and `created_at`/`modified_at` fields must be present before `LedgerSortField.created_at` / `LedgerSortField.modified_at` are sortable keys).

Within W02, P02 (shim collapse + positional id) and P03 (quintet normalisation) are independent of each other at the payload level but share `_ledger.py`. An executor can work P02 and P03 in sequence within W02 or land them jointly in one atomic commit per the relocation-atomicity rule in `aeat-architecture-boundaries`.

Within W03, P04 (sort), P05 (bare-dict replacement), and P06 (C7 stub + D7 gate) are structurally independent. P05 has the largest blast radius (13 Steps across 10 files) and benefits from being worked by a single focused executor to avoid concurrent edits to `_ledger_payloads.py`. P04 co-lands with or rebases onto C6's `project_ledger_list` signature changes - the executor must check C6 filter step status before landing S15/S16.

Cross-cluster coupling note: S15 and S16 (sort params on `project_ledger_list`) share the function signature with C6's filter params. These two Steps must either co-land with C6's filter Step in one commit or the sort executor must rebase onto C6's `project_ledger_list` signature after it lands.

## Verification

The plan is complete when every Step in every Wave is closed (`- [x]`) and all the following gates hold:

- `uv run --no-sync pytest src/aeat/domain/transactions/tests/test_repository_roundtrip.py -x -q` passes with the new timestamp roundtrip test (W01.P01.S04) and anti-tautology proof both present.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py -x -q` passes: 26-verb roster unchanged, all classify branches registered, D7 envelope gate green (W02.P03.S13, W03.P06.S32).
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m integration -x -q` passes: no `--id` Option present on any single-transaction verb, positional id confirmed on every converted verb (W02.P02.S09).
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/ -x -q` passes: sort-stability test present and green (W03.P04.S17).
- `uv run --no-sync python -m dev.type_check` (or equivalent check-types gate) exits clean: no `dict[str, Any]` at wire boundaries, no bare `object` list in any `OutputSchema` subclass (W03.P05.S30).
- `uv run --no-sync vaultspec-core vault check all` exits clean against this feature's documents.
- No `--id` Option token appears in `src/aeat/entrypoints/cli/_ledger*.py` after W02 lands.
- Every `list[dict[str, object]]` and `dict[str, object]` field in `_ledger_payloads.py` has been replaced with a typed `OutputSchema` subclass after W03.P05 lands.
