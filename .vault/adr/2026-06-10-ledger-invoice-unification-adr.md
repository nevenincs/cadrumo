---
tags:
  - '#adr'
  - '#ledger-invoice-unification'
date: '2026-06-10'
related:
  - "[[2026-06-10-ledger-invoice-unification-research]]"
  - "[[2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr]]"
---



# `ledger-invoice-unification` adr: `Unify invoice CLI to invoice --kind (supersedes 2026-05-12)` | (**status:** `accepted`)

## Supersession

This ADR **supersedes** `2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr`
on the single point of the operator-facing invoice CLI surface. The prior ADR
mandated that no bare `invoice` surface appear at the operator boundary — every
invoice verb had to spell out one of the four narrow source kinds, and the
implementation shipped two parallel noun-groups `payable-invoice` and
`collectible-invoice`. Per operator directive (recorded 2026-06-10), that
bare-`invoice`-ban position is overturned: the two noun-groups collapse into one
`invoice` command gated by `--kind issued|received`.

The prior ADR must be marked `superseded` by the coordinator (editing it is a
separate step outside this authoring pass). The supersession is narrow: it
overturns ONLY the prohibition on a bare `invoice` operator surface.

**Carried forward unchanged from the 2026-05-12 ADR:**

- The four-source-kind taxonomy: `ledger_transaction`,
  `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`. Every
  one of these strings survives in domain enums, event payloads, storage key
  grammar, audit traces, and registry TOML.
- The distinct-domain decision: a ledger row is a financial-movement fact;
  purchase-invoice evidence supports deductible expense without double-counting;
  payable/collectible invoices are business-operation entities, not ledger rows.
- The CLI Backend Boundary discipline: the CLI stays a thin entrypoint that
  delegates to backend/application/domain services and central error/output
  drivers.

**Overturned:**

- The ban on a bare `invoice` operator surface (prior ADR "Refactor Mandate" and
  "Consequences"). The collapse is at the *CLI noun group* only; the *source-kind
  values* are untouched.

## Problem Statement

The operator-facing CLI ships two invoice noun-groups,
`aeat app ledger payable-invoice` and `aeat app ledger collectible-invoice`,
whose five-verb CRUD bodies (`add` / `view` / `list` / `update` / `remove`) are
structurally identical in
`src/aeat/entrypoints/cli/_ledger_business_invoice_cli.py` — same options, same
parse helpers, same emit shape — differing only in which service factory they
call. This forces an operator to know the internal `payable` vs `collectible`
split (a settlement-direction distinction that is fully determined by whether the
invoice was issued or received) before they can record an invoice, and it
triples the maintenance surface: two locale-key mirror sets (13 + 13 leaves ×
four catalogues), ten payload-envelope classes, and two CRUD-contract entries
all carry the same shape twice. The duplication is the redundancy this decision
removes while keeping the load-bearing internal taxonomy intact.

## Considerations

- The `payable` / `collectible` distinction is not an operator concept the user
  should have to choose at the noun level — it is mechanically derivable from
  invoice direction. An *issued* invoice (we billed a customer) is *collectible*;
  a *received* invoice (a vendor billed us) is *payable*. The
  `_source_resolver._invoice_source_kind` function
  (`src/aeat/application/invoices/_source_resolver.py:108`) already encodes
  exactly this: `ISSUED → collectible_invoice`, `RECEIVED → payable_invoice`.
- The source-kind strings are persisted contract, not labels. They appear in M349
  registry TOML (18 occurrences), `INVOICE_BINDING_SOURCE_KINDS`,
  `BucketEventType` / `BucketEventObjectType` enums, the
  `{bucket_id}:{source_kind}` storage key grammar, and `AggregationSourceKind`.
  Collapsing them would break authored authority and stored data.
- Two invoice aggregates exist for good reason: the rich `Invoice`
  (`src/aeat/domain/invoices/_models.py`) is the calculation/reconciliation
  authority with derived identity, line-item arithmetic, and modelo aggregation;
  the slim `BusinessOperationInvoice`
  (`src/aeat/application/ledger/_business_operation_invoice.py`) is the flat
  operator-edit record. They have no shared base and no conversion path. Merging
  them is out of scope and rejected.
- The English noun `invoice` conflicts with `aeat-spanish-stem-naming` (the
  Spanish surface noun is `factura`). The operator directive fixes the English
  noun; this is a deliberate framework-vocabulary exception that must be recorded.
- `no-legacy-compatibility`: this is a pre-beta project with no released data, so
  the redundant surfaces are deleted outright with no deprecation aliases.

## Constraints

- **Locked taxonomy strings.** `payable_invoice` and `collectible_invoice` MUST
  remain as source-kind values in domain enums, events, storage keys, and
  registry TOML. The collapse is of the CLI noun group only.
- **Both aggregates survive.** The rich `Invoice` and the slim
  `BusinessOperationInvoice` both stay; this decision does not touch the
  calculation aggregate beyond promoting the direction→source-kind mapping to a
  shared contract.
- **Secure-storage invariant.** The unified command MUST drive the existing
  per-profile encrypted bucket-scoped `BusinessOperationInvoiceRepository` over
  `LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE`
  (`SensitivityClass.FINANCIAL`, `StorageNamespaceScope.BUCKET_LOCAL`). It MUST
  NOT introduce a parallel write path (`composition-service-no-parallel-write-path`).
- **CLI root surface unchanged.** The unified `invoice` command stays mounted
  under `aeat app ledger`; it does not add a third CLI root family
  (`aeat-architecture-boundaries` keeps the root at `config` / `app`).
- **Cross-cluster.** Depends on C3's shared canonical date/amount validators for
  `--invoice-date` and amount inputs, and rides C5's uniform envelope contract.
  C2's `purchase_invoice_evidence` stays a separate source kind and is not merged.

## Implementation

The two Typer sub-apps in `_ledger_business_invoice_cli.py` collapse into one
`invoice_app` mounted as `aeat app ledger invoice` with the five CRUD verbs.

**`--kind` axis.** Mutating verbs (`add`, `update`, `remove`) and the
single-record `view` require `--kind issued|received`, typed as a closed enum so
the Typer boundary renders a `Choice([...])` and instructs the operator on parse
failure (`aeat-architecture-boundaries` CLI-hint mandate). The new operator-facing
`--kind` enum carries the two member names `issued` / `received` (mirroring
`InvoiceKind`). The boundary maps each `--kind` to a source kind through one
explicit, contractual mapping: `issued → collectible_invoice`,
`received → payable_invoice`. This mapping is promoted from the inline ternary at
`_source_resolver.py:108` into a single named function (or `Mapping`) that both
the rich-aggregate resolver and the new CLI boundary consume, so the
direction→settlement relationship is single-sourced rather than re-derived. The
CLI then selects the matching service (`PayableInvoiceService` /
`CollectibleInvoiceService`) from the resolved source kind. `list` without
`--kind` returns both kinds (loading each source-kind document and concatenating);
with `--kind` it filters to one. The verb bodies otherwise reuse the existing
slim service, parse helpers (migrated to C3 validators), and `_emit_envelope`
shape verbatim.

**Model boundary.** The unified command drives the **slim**
`BusinessOperationInvoice` — the operator-CRUD record. The **rich** `Invoice`
remains the calculation aggregate consumed by modelo aggregation. The ADR states
the boundary explicitly to resolve the standing "are invoices ledger-bound?"
question: invoices are a *distinct domain*, mounted under `ledger` for operator
ergonomics, not a ledger transaction row. The two stores are addressed by
different identifiers and serve different layers.

**`link` interaction.** `aeat app ledger link --invoice-id`
(`src/aeat/entrypoints/cli/_ledger.py`) continues to target the **rich**
`InvoiceCatalogue` via `InvoiceCatalogueRepository`, not the slim store: the
slim `BusinessOperationInvoice` has no `linked_transaction_ids` field, only the
rich `Invoice` does. `link` does NOT gain a `--kind` flag — the rich
`invoice_id` is a globally-unique derived hash within the bucket catalogue and
already carries its own `InvoiceKind`, so direction is intrinsic to the id. The
`OrthogonalAxis.LINK` axis recorded on the CRUD contract is preserved on the
single unified `INVOICE` contract entry. This keeps the LINK axis pointed at the
calculation aggregate where reconciliation lives, while CRUD edits the operator
record.

**Deletion (no-legacy).** Remove: the `payable_invoice_app` /
`collectible_invoice_app` apps and their duplicate verb bodies; the 26 duplicate
locale leaves `cli.app.ledger.{payable,collectible}_invoice.*` across all four
catalogues (via the `aeat.locales` CLI, replaced by one
`cli.app.ledger.invoice.*` set); the 10 duplicate payload schemas
(`_ledger_payloads.py:676-723`, replaced by one five-class
`Invoice{Add,View,Update,Remove,List}Result` family); the two CRUD contracts
`PAYABLE_INVOICE` / `COLLECTIBLE_INVOICE` (`_crud_registry.py:41-52`, replaced by
one `INVOICE` contract retaining the LINK axis). Retire the
`AggregationSourceKind.INVOICE = "invoice"` remnant (`core/aggregation.py:16`)
once it is confirmed no live consumer depends on it — the bare `invoice` token
should not carry a dead alias meaning now that the operator surface reuses the
word. KEEP every source-kind string, every event-type / object-type value, the
M349 TOML, `INVOICE_BINDING_SOURCE_KINDS`, both aggregates, and the
direction→source-kind mapping (now contractual).

### Secure-storage gate

The unified `invoice` command MUST persist exclusively through the per-profile
encrypted bucket-scoped `SecureObjectRepository` path. Specifically:
`BusinessOperationInvoiceRepository` rides
`LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE`, which asserts
`sensitivity=SensitivityClass.FINANCIAL`, `scope=StorageNamespaceScope.BUCKET_LOCAL`,
and `object_key_grammar="{bucket_id}:{source_kind}"`; the repository is
constructed via `secure_object_repository_for_bucket(bucket_id, settings)`. The
slim `BusinessOperationInvoice` catalogue (and the rich `Invoice` catalogue) are
encrypted bucket-scoped secure objects. The unification introduces no plaintext
sidecar and no parallel write path. A strict save→load→equality roundtrip test
MUST exercise a record written through the unified `invoice add` path against the
real encrypted namespace (real `EphemeralMasterKeyProvider`, real engine), with
every defaultable field — including the intracom EU triple
(`country_code`, `eu_iva_id`, `operation_type`) and `notes` — populated
non-default, plus an anti-tautology proof that a mutated on-disk payload surfaces
inequality or a `ValidationError` (`aeat-roundtrip-discipline`).

## Rationale

The research (`2026-06-10-ledger-invoice-unification-research`) established that
the `payable` / `collectible` split is mechanically determined by invoice
direction and already encoded in one resolver function, that the two CLI
noun-groups are byte-identical over a single slim model differing only in a
bound `source_kind`, and that the source-kind strings are load-bearing across
registry / events / storage and therefore cannot be collapsed. The minimal,
honest design is therefore to collapse the *redundant operator surface* (the two
noun-groups, their locale mirrors, their payload mirrors, their contract mirrors)
while preserving the *taxonomy* (the source-kind strings and everything keyed on
them). Routing the operator's `--kind` through the same direction→source-kind
mapping the calculation layer already uses keeps a single source of truth for the
direction↔settlement relationship. Keeping `link` pointed at the rich aggregate
respects the existing reconciliation boundary; only the rich `Invoice` carries
`linked_transaction_ids`.

## Consequences

- **Simpler operator UX.** One `invoice` verb with an instructive `--kind` Choice
  replaces two noun-groups; the operator no longer needs the internal
  payable/collectible vocabulary.
- **Two-thirds less duplicate surface.** One locale set, one payload family, one
  CRUD contract replace the mirrored pairs; future invoice-field additions land
  once.
- **The direction→source-kind mapping becomes a named contract** consumed by both
  the resolver and the CLI, removing a second derivation site.
- **A `--kind`-shaped trap to avoid:** `list` must default to *both* kinds when
  `--kind` is omitted, or an operator's bare `invoice list` silently drops half
  their records — a `no-silent-under-declaration`-adjacent failure. The default
  must be all-kinds, with `--kind` as an optional filter.
- **The `link` / CRUD store split is a documented sharp edge:** `--invoice-id` on
  `link` and `invoice_id` on the unified CRUD address two different stores (rich
  vs slim). The ADR fixes this explicitly so a future agent does not "unify" them
  by mistake.
- **Naming-rule tension recorded.** The English `invoice` noun is an explicit
  exception to `aeat-spanish-stem-naming`, grounded in operator directive; it is a
  codification candidate so the exception survives in the rule's carve-out list.
- **Migration risk is low** (pre-beta, no released data) but the
  `AggregationSourceKind.INVOICE` retirement is the one deletion that must be
  guarded by a consumer search before it lands.

## Codification candidates

- **Rule slug:** `invoice-cli-noun-is-english-by-directive`.
  **Rule:** The operator-facing invoice CLI noun is the English `invoice` with
  `--kind issued|received`; this is the standing operator-directed exception to
  `aeat-spanish-stem-naming` for the invoice surface, and the internal
  `payable_invoice` / `collectible_invoice` source-kind strings remain the
  load-bearing taxonomy (never collapsed). Best landed by extending the
  exception list in the existing `aeat-spanish-stem-naming` rule rather than a
  new rule, per `vaultspec-codify`'s edit-in-place guidance.
