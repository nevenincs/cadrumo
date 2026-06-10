---
tags:
  - '#research'
  - '#ledger-invoice-unification'
date: '2026-06-10'
related: []
---



# `ledger-invoice-unification` research: `Unified invoice command and domain decoupling`

This research inventories the invoice surface of the codebase to ground a
decision to collapse two parallel operator-facing CLI noun-groups
(`payable-invoice`, `collectible-invoice`) into a single `invoice` command
gated by `--kind issued|received`. It supersedes the bare-`invoice`-ban
position of `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr`
while carrying forward that ADR's four-source-kind taxonomy and its
distinct-domain decision. The scope is the C4 cluster of the broader CLI
restructure: the invoice domain and the unified `invoice` command. Every
finding below was verified against the working tree at the date of writing.

## Findings

### Two invoice aggregates exist and both must survive

The codebase carries two distinct invoice models that are NOT duplicates of
each other — they serve different layers and must both be kept.

The **rich calculation aggregate** is `Invoice` in
`src/aeat/domain/invoices/_models.py`. It is strict, frozen, extra-forbidden,
and identity-bearing: `invoice_id` is a SHA-256 derived hash over
(`kind`, `invoice_number`, `issued_at`, `counterparty_tax_id`, `currency`,
`grand_total`) computed in a `model_validator`. Its direction axis is
`InvoiceKind` (`ISSUED` / `RECEIVED`) from `aeat.domain.iva`. It carries
`lines: tuple[InvoiceLine, ...]` with per-line arithmetic invariants
(subtotal = quantity × unit_price, iva_amount = subtotal × rate, exempt-line
zero-iva enforcement), `base_total` / `iva_total` / `grand_total` cross-checked
against the line sums, `payment_status`, `iva_category: IvaCategory | None`,
`retention_rate` / `retention_amount`, `linked_transaction_ids`, and EU
member-state accessors. It is held in `InvoiceCatalogue` (keyed by
`invoice_id`) and feeds modelo aggregation (M349 / M303 / M369 / M390) via the
source resolver. It is the reconciliation and calculation authority.

The **slim operator-CRUD record** is `BusinessOperationInvoice` in
`src/aeat/application/ledger/_business_operation_invoice.py`. Its discriminator
is `source_kind: BusinessOperationInvoiceSourceKind` (`PAYABLE_INVOICE` /
`COLLECTIBLE_INVOICE`). It is intentionally flat: `counterparty_nif`,
`counterparty_name`, `invoice_number`, `invoice_date` (a 10-char `str`, not a
`date`), `currency`, `taxable_base`, `iva_rate`, `iva_amount`, `total_amount`,
`notes`, intracom EU fields (`country_code`, `eu_iva_id`,
`operation_type: IntracomOperationType | None`), `created_at` / `updated_at`.
Its module docstring states the boundary explicitly: "The records are
intentionally slim. Business-detail enrichment (line items, IVA breakdown,
reconciliation linkages) belongs to the `aeat.domain.invoices` richer
`Invoice` aggregate consumed by modelo aggregation pipelines." The two models
have no shared base and no conversion path between them. Merging them is out of
scope and is explicitly rejected.

### Two CLI noun-groups have byte-identical bodies over the slim model

`src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py` defines two Typer
sub-apps, `payable_invoice_app` (mounted as `payable-invoice`) and
`collectible_invoice_app` (mounted as `collectible-invoice`), each carrying the
five-verb CRUD spine (`add` / `view` / `list` / `update` / `remove`). The two
command bodies are structurally identical: same options, same parse helpers
(`_parse_decimal`, `_validated_eu_iva_id`, `_parse_intracom_operation_type`),
same `_business_invoice_payload` / `_business_invoice_text_lines` emit shape,
same `_emit_envelope` contract. The only difference is the service factory:
`_payable_invoice_service()` returns `PayableInvoiceService`,
`_collectible_invoice_service()` returns `CollectibleInvoiceService`. Both
concrete services are thin subclasses of `_BusinessOperationInvoiceService`
that bind a single `source_kind` class attribute. `register_business_invoice_commands`
mounts both onto the ledger app; the ledger app calls it at module bottom
(`src/aeat/entrypoints/cli/_ledger.py`). This duplication is the redundancy the
unified command removes.

### The source-kind mapping is real, load-bearing, and currently implicit

`src/aeat/application/invoices/_source_resolver.py:107-108` maps the rich
aggregate's `InvoiceKind` onto the source-kind string:

```
def _invoice_source_kind(invoice: Invoice) -> str:
    return "collectible_invoice" if invoice.kind is InvoiceKind.ISSUED else "payable_invoice"
```

So `ISSUED → collectible_invoice` and `RECEIVED → payable_invoice`. This is the
semantic anchor the unified `--kind` must preserve: an issued invoice (we billed
a customer) is *collectible*; a received invoice (a vendor billed us) is
*payable*. The mapping is currently expressed inline at one call site; the
unified command needs the same mapping at the CLI boundary, and it should be
promoted to a single named, contractual mapping rather than re-deriving the
ternary at a second site.

### The source-kind strings are load-bearing across registry, events, storage

The `payable_invoice` / `collectible_invoice` strings are NOT cosmetic CLI
labels — they are persisted contract values:

- **Registry TOML.** M349 `0007-bindings.toml` carries 17 `collectible_invoice`
  occurrences (intracom entrega bindings); the M349 filing-schedule TOML carries
  one more. These are authored authority and cannot change.
- **Binding taxonomy.** `INVOICE_BINDING_SOURCE_KINDS` in
  `src/aeat/domain/calculations/registry/_invoice_bindings.py:33` is the single
  source for "is this an invoice binding?" — the frozenset
  `{collectible_invoice, payable_invoice, purchase_invoice_evidence}`.
- **Events.** `BucketEventType.{PAYABLE,COLLECTIBLE}_INVOICE_{CREATED,UPDATED,REMOVED}`
  plus correction variants, and `BucketEventObjectType.{PAYABLE,COLLECTIBLE}_INVOICE`,
  wired through `_EVENT_MAP` / `_OBJECT_TYPE_MAP` in the slim-model module.
- **Storage key grammar.** The secure-object namespace
  `LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE` uses
  `object_key_grammar="{bucket_id}:{source_kind}"`; the slim repository keys each
  document by `{bucket_id}:{source_kind}` via `_document_key`.
- **Core taxonomy.** `AggregationSourceKind` in `src/aeat/core/aggregation.py`
  enumerates `PAYABLE_INVOICE` / `COLLECTIBLE_INVOICE` (and the retired bare
  `INVOICE = "invoice"` remnant — see below).

The locked decision keeps every one of these strings. The collapse is of the
CLI *noun group*, not the source-kind *values*.

### Secure-storage invariant holds today

The slim records ride the per-profile encrypted bucket-scoped repository.
`BusinessOperationInvoiceRepository` extends
`SecureBoundRepository[BusinessOperationInvoiceDocument]` and binds
`namespace` / `sensitivity` / `schema_version` from
`LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE`
(`src/aeat/adapters/persistence/storage/_namespace_registry.py:375`), which
declares `sensitivity=SensitivityClass.FINANCIAL` and
`scope=StorageNamespaceScope.BUCKET_LOCAL`. The repository is constructed via
`secure_object_repository_for_bucket(bucket_id, settings)`. The rich `Invoice`
catalogue rides `InvoiceCatalogueRepository`. Both invoice catalogues are
encrypted bucket-scoped secure objects. The unified command does not change this
storage; it drives the same slim repository through the same namespace, so the
secure-storage gate is satisfied by construction — but the unification must
carry a roundtrip test proving a record written through the unified `invoice add`
path survives a save→load→equality cycle against the encrypted namespace, with
every defaultable field populated non-default.

### The `link` verb targets the RICH aggregate, not the slim model

`aeat app ledger link --invoice-id` in `src/aeat/entrypoints/cli/_ledger.py`
(around line 1111) resolves `--invoice-id` against the **rich** catalogue:
it imports `InvoiceCatalogueRepository` from `domain.invoices`, loads the
snapshot, looks the id up in `invoices_snapshot.invoices`, runs a pre-write
bucket-scope guard, then calls `link_invoice_transaction_repositories`. This is
the orthogonal LINK axis the CRUD contract records on both invoice noun-groups
(`OrthogonalAxis.LINK`). The slim `BusinessOperationInvoice` has no
`linked_transaction_ids` field at all — only the rich `Invoice` does. So the
`--invoice-id` of `link` and the `invoice_id` of the slim CRUD record address
two different stores. The unification must specify this explicitly: the unified
`invoice` CRUD drives the slim store, while `link` continues to target the rich
catalogue. The `--kind` of the new command keys the slim CRUD; `link` does not
need `--kind` because the rich `invoice_id` is globally unique within the
bucket catalogue and already carries its own `InvoiceKind`.

### Deletion inventory (no-legacy, locked)

Per `no-legacy-compatibility`, the redundant surfaces are deleted outright, with
no deprecation aliases:

- **Two CLI apps:** `payable_invoice_app` and `collectible_invoice_app` (and the
  duplicate verb bodies) in `_ledger_business_invoice_cli.py`, replaced by one
  `invoice_app`.
- **Locale keys:** the mirror sets `cli.app.ledger.payable_invoice.*` and
  `cli.app.ledger.collectible_invoice.*` (13 + 13 leaf keys across each of the
  four catalogues `en` / `es` / `ca` / `hu`), removed and replaced by a single
  `cli.app.ledger.invoice.*` set managed through the `aeat.locales` CLI (never by
  hand-editing the `.yml`).
- **Payload schemas:** the 10 envelope classes
  `Payable/CollectibleInvoice{Add,View,Update,Remove,List}Result`
  (`_ledger_payloads.py:676-723`), replaced by a single five-class
  `Invoice{Add,View,Update,Remove,List}Result` family carrying the same
  `BusinessInvoiceRecordPayload` shape.
- **CRUD contracts:** the two `MutatingNounGroupContract` entries `PAYABLE_INVOICE`
  and `COLLECTIBLE_INVOICE` (`_crud_registry.py:41-52`), replaced by one `INVOICE`
  contract that keeps the `OrthogonalAxis.LINK` axis.
- **Retired remnant:** `AggregationSourceKind.INVOICE = "invoice"`
  (`core/aggregation.py:16`) is an explicitly-documented retired alias kept only
  for "persisted-registry validation and explicit rejection". It is the bare
  `invoice` token the 2026-05-12 ADR banned. Because the new English `invoice`
  CLI noun deliberately reuses the word `invoice` at the operator surface, the
  remnant should be retired so the bare token no longer carries a dead alias
  meaning. Confirm no live consumer depends on `AggregationSourceKind.INVOICE`
  before deletion; the `CounterpartSourceKind` Literal and
  `COUNTERPART_SOURCE_KINDS` frozenset already exclude it.

What is KEPT: every source-kind string, every `BucketEventType` /
`BucketEventObjectType` value, the M349 TOML, `INVOICE_BINDING_SOURCE_KINDS`,
both invoice aggregates, and the `_source_resolver` mapping (promoted to an
explicit contract).

### Naming: English `invoice` is a framework-vocabulary exception

`aeat-spanish-stem-naming` mandates Spanish stems for AEAT-surface concepts; the
Spanish noun for invoice is `factura`. The operator directive for this campaign
fixes the English noun `invoice` with `--kind issued|received` at the operator
surface. This is an explicit, operator-grounded exception to the Spanish-stem
rule, analogous to the rule's existing carve-out for generic computing
vocabulary and cross-cutting framework concepts. The exception must be recorded
in the ADR (and is a candidate codification into `aeat-spanish-stem-naming`'s
exception list). The internal source-kind strings `payable_invoice` /
`collectible_invoice` are not Spanish either, but they are load-bearing
pre-existing taxonomy values, not new authoring.

### Cross-cluster contracts

- **C2** — `purchase_invoice_evidence` stays a separate source kind. It is in
  `INVOICE_BINDING_SOURCE_KINDS` and the `EVIDENCE` CRUD contract
  (`aeat app ledger evidence`), but it is NOT merged into the `invoice` command.
  An invoice may be used as expense evidence, but the models and CLI surfaces
  stay distinct.
- **C3** — the unified `invoice` command's `invoice_date` and amount inputs must
  use C3's shared canonical validators rather than the local ad-hoc
  `_parse_decimal` helpers, so date and money parsing is uniform across the
  ledger surface.
- **C5** — the `invoice` verbs ride the same uniform envelope contract
  (`_emit_envelope`, `register_schema`) as every other operator-surface CRUD.
- **C7** — invoice records participate in modelo filing via the rich aggregate's
  `_source_resolver` and the `INVOICE_BINDING_SOURCE_KINDS` taxonomy; the slim
  operator records feed aggregation through the same source-kind strings.

### Tests in scope

`src/aeat/entrypoints/cli/tests/test_business_invoice_verbs.py` (CLI verbs),
`src/aeat/domain/invoices/tests/*` (rich aggregate + secure-storage roundtrip),
`src/aeat/application/ledger/tests/test_business_operation_invoice.py` (slim
service), `src/aeat/application/operator_surface/tests/test_crud_registry.py`
(CRUD contract conformance), and the locale parity / honesty gates. These move
from the dual-noun shape to the single-`invoice` shape; the CRUD-registry
conformance test must assert the single `INVOICE` contract with the LINK axis.
