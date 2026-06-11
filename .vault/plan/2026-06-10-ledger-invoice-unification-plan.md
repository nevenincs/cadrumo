---
tags:
  - '#plan'
  - '#ledger-invoice-unification'
date: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-ledger-invoice-unification-adr]]'
  - '[[2026-06-10-ledger-invoice-unification-research]]'
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

# `ledger-invoice-unification` `Unify invoice CLI to invoice --kind` plan

### Phase `P01` - C4 prerequisite - consumer search and direction-to-source-kind contract promotion

Confirm AggregationSourceKind.INVOICE consumer count and promote the direction-to-source-kind mapping from an inline ternary to a named contractual function shared by the source resolver and the new unified CLI.

- [x] `P01.S01` - Grep all consumers of AggregationSourceKind.INVOICE across src/aeat to confirm none are load-bearing (i.e. all sites either guard against it as a retired alias or are tests asserting exclusion); `record findings as a comment in core/aggregation.py; `src/aeat/core/aggregation.py`.
- [x] `P01.S02` - Promote the inline ternary at _source_resolver.py:108 into a named module-level function invoice_direction_to_source_kind(kind: InvoiceKind) -> BusinessOperationInvoiceSourceKind (or Mapping) in src/aeat/application/invoices/_source_resolver.py and update the one call site in _source_resolver.py to call it; `src/aeat/application/invoices/_source_resolver.py`.
- [x] `P01.S03` - Export invoice_direction_to_source_kind from the invoices application package __init__.py / __all__ so downstream consumers (including the new CLI) can import it from the package top-level; `src/aeat/application/invoices/__init__.py`.
- [x] `P01.S04` - Run uv run --no-sync pytest --collect-only -q on the invoices application test tree to confirm clean collection after the promotion; `src/aeat/application/invoices`.

### Phase `P02` - Locale surface collapse

Replace the 26 duplicate payable-invoice and collectible-invoice locale leaves across all four catalogues with one cli.app.ledger.invoice.* set, using the aeat.locales CLI.

- [x] `P02.S05` - Run python -m aeat.locales audit to record the current payable_invoice and collectible_invoice locale key count as a baseline before deletion; `src/aeat/locales`.
- [x] `P02.S06` - Remove all 13 cli.app.ledger.payable_invoice.* locale leaves from en, es, ca, and hu catalogues using python -m aeat.locales remove LOCALE KEY for each leaf (or python -m aeat.locales scaffold if the CLI supports bulk removal from a deleted code reference); `src/aeat/locales`.
- [x] `P02.S07` - Remove all 13 cli.app.ledger.collectible_invoice.* locale leaves from en, es, ca, and hu catalogues using python -m aeat.locales remove LOCALE KEY; `src/aeat/locales`.
- [x] `P02.S08` - Add the unified cli.app.ledger.invoice.* leaf set (group_help, kind_help, kind_invalid, add_help, view_help, list_help, update_help, remove_help, invoice_date_help, invoice_id_help, country_code_help, eu_iva_id_help, operation_type_help, operation_type_invalid, yes_help, yes_required) to all four locales using python -m aeat.locales set LOCALE KEY VALUE; `src/aeat/locales`.
- [x] `P02.S09` - Run python -m aeat.locales scaffold --check to confirm zero drift, then python -m aeat.locales audit to confirm parity across all four catalogues; `both must exit clean; `src/aeat/locales`.

### Phase `P03` - Payload and CRUD contract collapse

Replace the 10 duplicate payload classes and the two CRUD contracts with one InvoiceAddResult/ViewResult/UpdateResult/RemoveResult/ListResult family and one INVOICE contract retaining the LINK orthogonal axis.

- [x] `P03.S10` - Delete the 10 duplicate payload classes (PayableInvoiceAddResult, PayableInvoiceViewResult, PayableInvoiceUpdateResult, PayableInvoiceRemoveResult, PayableInvoiceListResult, CollectibleInvoiceAddResult, CollectibleInvoiceViewResult, CollectibleInvoiceUpdateResult, CollectibleInvoiceRemoveResult, CollectibleInvoiceListResult) from src/aeat/entrypoints/cli/_ledger_payloads.py lines 676-723; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `P03.S11` - Add the unified five-class payload family InvoiceAddResult, InvoiceViewResult, InvoiceUpdateResult, InvoiceRemoveResult, InvoiceListResult registered under ledger.invoice.{add,view,update,remove,list} schema keys in src/aeat/entrypoints/cli/_ledger_payloads.py; `src/aeat/entrypoints/cli/_ledger_payloads.py`.
- [x] `P03.S12` - Replace the PAYABLE_INVOICE and COLLECTIBLE_INVOICE MutatingNounGroupContract entries in src/aeat/application/operator_surface/_crud_registry.py with one INVOICE contract (noun=invoice, cli_path=aeat app ledger invoice, orthogonal_axes={OrthogonalAxis.LINK}) and update BUILTIN_CRUD_CATALOGUE and __all__; `src/aeat/application/operator_surface/_crud_registry.py`.
- [x] `P03.S13` - Update src/aeat/application/operator_surface/tests/test_crud_registry.py to assert the unified INVOICE contract is present (noun=invoice, LINK axis) and the old PAYABLE_INVOICE and COLLECTIBLE_INVOICE contracts are gone; `src/aeat/application/operator_surface/tests/test_crud_registry.py`.
- [x] `P03.S14` - Run uv run --no-sync pytest --collect-only -q src/aeat/application/operator_surface and src/aeat/entrypoints/cli to confirm clean collection after payload and contract changes; `src/aeat/application/operator_surface src/aeat/entrypoints/cli`.

### Phase `P04` - Unified invoice CLI and AggregationSourceKind.INVOICE retirement

Collapse payable_invoice_app and collectible_invoice_app into one invoice_app with --kind issued|received and retire AggregationSourceKind.INVOICE once no live consumer depends on it.

- [x] `P04.S15` - Rewrite src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py: collapse payable_invoice_app and collectible_invoice_app into one invoice_app (name=invoice); `add an InvoiceKindOption StrEnum (ISSUED=issued, RECEIVED=received) declared as the Typer type for --kind so click renders Choice([issued, received]); route --kind through invoice_direction_to_source_kind to select PayableInvoiceService or CollectibleInvoiceService; `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`.
- [x] `P04.S16` - Implement add, view, update, remove verbs on invoice_app each requiring --kind issued|received (typed InvoiceKindOption, mandatory) and emitting via the unified InvoiceAddResult / InvoiceViewResult / InvoiceUpdateResult / InvoiceRemoveResult payload schemas with command strings ledger.invoice.{add,view,update,remove}; `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`.
- [x] `P04.S17` - Implement the list verb on invoice_app with --kind as an optional filter (Optional[InvoiceKindOption] = None): when None load both source kinds and concatenate; `when provided load only the matching source kind; emit via InvoiceListResult with command string ledger.invoice.list; `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py`.
- [x] `P04.S18` - Update the register_business_invoice_commands function in _ledger_business_invoice_cli.py to mount only invoice_app under name=invoice and delete the payable_invoice_app and collectible_invoice_app mounts; `update the import in src/aeat/entrypoints/cli/_ledger.py to remove the now-deleted app names; `src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py src/aeat/entrypoints/cli/_ledger.py`.
- [x] `P04.S19` - Retire AggregationSourceKind.INVOICE from src/aeat/core/aggregation.py: remove the INVOICE = invoice member, remove it from CounterpartSourceKind Literal, remove it from COUNTERPART_SOURCE_KINDS frozenset, and update the module docstring; `verify no remaining load-bearing consumer exists via grep on AggregationSourceKind.INVOICE across the codebase; `src/aeat/core/aggregation.py`.
- [x] `P04.S20` - Update every reference to AggregationSourceKind.INVOICE in src/aeat/application/aggregation/_retenciones.py:56 and src/aeat/domain/calculations/registry/_bindings.py and src/aeat/domain/calculations/registry/_schema.py and src/aeat/domain/calculations/registry/_validate_record_sections.py to remove or adapt the guard/routing that depended on the retired alias; `src/aeat/application/aggregation src/aeat/domain/calculations/registry`.
- [x] `P04.S21` - Update or remove the test assertion in src/aeat/application/operator_surface/tests/test_contract.py:311 that asserts the canonical minus operator values set equals {AggregationSourceKind.INVOICE.value} now that INVOICE is retired; `src/aeat/application/operator_surface/tests/test_contract.py`.
- [x] `P04.S22` - Update the AST-gate allowlist in src/aeat/tests/test_enum_constant_extraction_inventory.py:168-173 that asserts sites use AggregationSourceKind.INVOICE: remove the entry or rewrite it to assert INVOICE no longer appears in production code; `src/aeat/tests/test_enum_constant_extraction_inventory.py`.
- [x] `P04.S23` - Run python -m dev.docs.apidocs scaffold to regenerate any affected API reference stubs after the symbol relocations and deletions in this phase; `docs/api`.
- [x] `P04.S24` - Run uv run --no-sync pytest --collect-only -q across the full src/aeat tree to confirm clean collection before committing the P04 atomic explicit-path commit; `src/aeat`.

### Phase `P05` - Roundtrip and test surface hardening

Author a strict save-load-equality roundtrip test for the unified invoice path with all defaultable fields non-default, the EU triple non-default, and an anti-tautology proof; update existing invoice test coverage to the unified surface.

- [x] `P05.S25` - Update src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py to drive the unified invoice_app: rename tests from test_payable_invoice_* and test_collectible_invoice_* to test_invoice_*, pass --kind issued or --kind received, assert source_kind in response matches payable_invoice or collectible_invoice respectively; `src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py`.
- [x] `P05.S26` - Add a test_invoice_list_without_kind_returns_both_kinds test in src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py: write one issued record and one received record, call invoice list without --kind, assert count=2 and both source_kind values appear in rows; `this is the no-silent-under-declaration guard; `src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py`.
- [x] `P05.S27` - Author a strict roundtrip test test_invoice_add_roundtrip_all_fields in src/aeat/application/ledger/tests/test_business_operation_invoice.py: create a BusinessOperationInvoice (issued kind, all optional fields incl. country_code, eu_iva_id, operation_type non-default, notes non-default) via PayableInvoiceService.add against a real EphemeralMasterKeyProvider+SQLite engine, reload via list_all, assert model_a == model_b strict pydantic equality; `src/aeat/application/ledger/tests/test_business_operation_invoice.py`.
- [x] `P05.S28` - Author an anti-tautology proof test test_invoice_roundtrip_antitautology in src/aeat/application/ledger/tests/test_business_operation_invoice.py: save a record, mutate the on-disk JSON payload to delete the eu_iva_id field, reload and assert ValidationError raised or strict pydantic inequality surfaced; `confirm the roundtrip would fail if the boundary were broken; `src/aeat/application/ledger/tests/test_business_operation_invoice.py`.
- [x] `P05.S29` - Run uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py src/aeat/application/ledger/tests/test_business_operation_invoice.py -v to confirm all roundtrip and list-both-kinds tests pass green; `src/aeat/entrypoints/cli/tests src/aeat/application/ledger/tests`.
- [x] `P05.S30` - Run uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m integration to confirm the unified invoice surface passes the CLI conformance gate; `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.

## Description

Collapses the two operator-facing invoice noun-groups (`aeat app ledger payable-invoice` and `aeat app ledger collectible-invoice`) into one `aeat app ledger invoice` command gated by `--kind issued|received`. The internal `payable_invoice` / `collectible_invoice` source-kind strings, events, storage keys, and M349 registry TOML are untouched; only the CLI surface, locale keys, payload schemas, and CRUD contract entries are consolidated. Authorised by `2026-06-10-ledger-invoice-unification-adr`, which supersedes the prior ban on a bare `invoice` operator surface from `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr`.

The plan removes two parallel noun-group apps and their duplicated surfaces (26 locale leaves, 10 payload classes, 2 CRUD contracts), promotes the inline direction-to-source-kind ternary at `_source_resolver.py:108` into a single named contractual function consumed by both the resolver and the new CLI, and retires the stale `AggregationSourceKind.INVOICE = "invoice"` alias after confirming no load-bearing consumer depends on it. The `list` verb defaults to returning both kinds when `--kind` is omitted, preventing a silent half-records drop. The `link` command continues targeting the rich `InvoiceCatalogue` (no `--kind` flag), and the slim `BusinessOperationInvoice` remains the CRUD record.

## Parallelization

P01 must land before P04 (the CLI needs `invoice_direction_to_source_kind` from the package top-level). P02 and P03 can execute concurrently with each other once P01 is done, since they touch disjoint files (locale catalogues vs. payload/CRUD modules). P04 depends on P02 (locale keys must exist before the CLI references them) and P03 (payload classes must exist before the CLI emits them). P05 depends on P04 (tests drive the unified CLI). Within each phase, steps are sequential.

## Verification

- `python -m aeat.locales scaffold --check` exits clean with zero drift after P02.
- `python -m aeat.locales audit` reports parity across all four catalogues after P02.
- `uv run --no-sync pytest --collect-only -q src/aeat` exits clean after each phase.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py -v` passes all tests with `--kind issued` and `--kind received` variants after P04/P05.
- `test_invoice_list_without_kind_returns_both_kinds` passes: bare `invoice list` returns both issued and received records.
- `test_invoice_add_roundtrip_all_fields` passes: strict pydantic equality across the encrypted namespace boundary with EU triple and notes non-default.
- `test_invoice_roundtrip_antitautology` passes: a mutated on-disk payload surfaces `ValidationError` or inequality.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m integration` passes after P05.
- `python -m dev.docs.apidocs scaffold --check` exits clean after P04.
- The `AggregationSourceKind` enum in `src/aeat/core/aggregation.py` contains no `INVOICE` member after P04.
