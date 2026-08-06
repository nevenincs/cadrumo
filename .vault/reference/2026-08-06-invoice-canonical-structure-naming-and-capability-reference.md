---
tags:
  - '#reference'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:2b088fbc46f90ca027e83a7892b80b63761e601d40f6fd76b56604d13e6705a8'
related:
  - "[[2026-08-06-invoice-canonical-structure-adr]]"
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
  - "[[2026-08-06-invoice-canonical-structure-audit]]"
---
# `invoice-canonical-structure` reference: `Canonical verdict, conflation map, capability and custody grounding`

The implementation grounding a coding team needs to execute this campaign: which of the two
invoice records is canonical and what would falsify that, where the vocabulary is conflated
and what each rename actually costs, which capabilities live on only one side, and how the
evidence survives a profile export and import.

All measurements were taken by direct read and targeted search at the HEAD named in each
section. Two HEADs appear: the naming and blast-radius sweep was measured at `daa9876ed3`,
and the capability, custody and writer-parity findings at `246d9a11f4`. The tree moves
several times a day under concurrent campaigns, so **re-read every cited site at HEAD before
editing on it** - the citations inherited from the earliest sweep had already drifted about
thirty lines when the audit re-measured them.

## Summary

The rich `Invoice` aggregate is canonical, but the collapse onto it is a migration of
capabilities rather than a deletion, and in one direction it is a narrowing. Three fields
live only on the slim store and one of them is load-bearing for Modelo 349 party identity.
Four canonical invariants have no slim counterpart, so records that are valid today would be
refused. Four canonical fields have no writer parameter at all, so the canonical aggregate
does not yet reach parity with what it claims to model. Each of these is a Step in the plan;
this document is the evidence behind them.

## Capability conservation

Invoices are the evidence base for three distinct concerns, and a proof covering only one of
them is not a proof:

- **Income** - issued, collectible invoices feeding the income side.
- **Business operations** - received, payable invoices feeding the deduction side.
- **Purchase evidence** - the document record, held separately by the purchase-evidence
  store, which this campaign explicitly does not merge.

### Fields held only by the slim store

Confirmed absent from `src/cadrumo/domain/invoices/` by targeted search at `246d9a11f4`:

- **`eu_iva_id`** - load-bearing, not cosmetic. `_business_invoice_party_tax_id`
  (`src/cadrumo/application/invoices/_source_resolver.py:675-679`) reads
  `(invoice.eu_iva_id or invoice.counterparty_nif)`, **preferring the EU VAT ID** as the
  declared M349 party id, and `_business_invoice_country_code` (`:682-689`) derives the M349
  country prefix from it, including the EL-to-GR mapping. The canonical projection
  (`:409-411`, `:425-427`) passes `counterparty_tax_id` straight through with no preference
  and no prefix derivation. For an EU counterparty holding both a domestic NIF and an EU VAT
  ID, the slim store records both and declares the correct one; the canonical aggregate
  cannot. Deleting the slim store before this field reaches the canonical model is a **silent
  identity substitution** in intra-EU recapitulative matching - it does not crash, it
  misdeclares.
- **`created_at`**, **`updated_at`** - the canonical aggregate carries no lifecycle
  timestamps at all. Audit metadata rather than declarable facts, but their loss must be a
  stated decision.

### Canonical invariants with no slim counterpart

The slim model carries **no `model_validator` at all** - only field validators for country
code, currency and the date strings. The canonical model carries eleven model validators and
four field validators. The four that make the fold a narrowing:

| Invariant | Canonical | Slim |
|---|---|---|
| counterparty name | required, `min_length=1` | defaults to the empty string |
| counterparty country | required, exactly two characters | nullable |
| line items | at least one line, with per-line arithmetic | no line concept at all |
| totals | exact invoice-level identity | three independent non-negative fields, no cross-check |

A fifth asymmetry sits inside the line set: the canonical `InvoiceLine.iva_rate` is the
closed `IvaRate` enum, where the slim record's `iva_rate` is a bare optional `Decimal`. A
rate that is not an enum member must refuse rather than round - an unread rate currently
resolves to the exempt member, minting a zero-cuota invoice whose printed total still shows
the cuota that was charged.

The live proof that these shapes exist: the blessing test at
`src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_link_flow.py:143-155` writes a
record through `invoice add` with no counterparty name, no country code and no lines, and it
passes today.

### Canonical fields no production path can write

`invoice_class`, `series`, `rectifies_invoice_number` and `recargo_amount` exist on the
canonical model but have **no parameter** on `build_catalogue_invoice` or
`create_catalogue_invoice`. Every canonically-written invoice is therefore `ORDINARIA` with
no series and no recargo **by construction**, and a rectificativa cannot be represented at
all. Retencion is the exception that proves the pattern: `retention_rate` and
`retention_amount` were absent on the same footing until they landed in `ef0438561d`, on both
the direct and the guided entry verb.

### Custody: how the evidence survives export and import

A relayed claim that the canonical catalogue is excluded from profile backup is **refuted**.
Measured at `246d9a11f4`:

- `INVOICE_CATALOGUE_NAMESPACE`
  (`src/cadrumo/adapters/persistence/storage/_namespace_registry.py:906-916`) declares
  `custody_disposition=StorageCustodyDisposition.STRUCTURED_CUSTODY` and a
  `default_object_key`.
- The registry that appeared to be missing an entry is a **natural-key resolver** map, not an
  inclusion list. `src/cadrumo/application/user_profile/_custody_carry.py:468-471` falls back
  for exactly this case - single-document and catalogue stores resolve through a fixed key.
  The slim repository has an explicit resolver because it is a per-record bound repository.
- A namespace with neither a resolver nor a default key raises `ProfileExportError`
  (`:472-476`). Custody failure is loud, not silent.
- End-to-end coverage already exists:
  `src/cadrumo/application/user_profile/tests/test_custody_store_matrix.py:1001` enrols the
  canonical namespace with a seed that builds a real invoice with lines.

**The real custody defect is weaker and different.** The verification at `:319-320` asserts
only that the reloaded catalogue is non-empty. That passes even when the boundary drops a
field and the loader re-defaults it - the precise blindness `aeat-roundtrip-discipline`
exists to catch, sitting on the aggregate about to absorb a second store's entire capability
set. Strengthening it to a strict-equality roundtrip with every defaultable field non-default,
plus the mutation proof, is the actionable item.

## Naming, blast radius, and the canonical verdict

Measured at `daa9876ed3`. The generated Sphinx build output is excluded from every count in
this section; including it inflates several symbols three- to six-fold.

Measured at HEAD `daa9876ed33536f5448f5f3a74f2a05b100052c4`, worktree `Y:\code\aeat-worktrees\main`.
Read-only investigation. No commits, no staging, no destructive git.

---

### 1. The grounded canonical verdict

**The rich `Invoice` aggregate at `src/cadrumo/domain/invoices/_models.py:500` is canonical — but the collapse is NOT a pure deletion. Three fields live only on the slim store and must be added to the rich aggregate first, or the collapse regresses Modelo 349 declaration fidelity.**

#### Two genuine structural schemas exist

| | RICH | SLIM |
|---|---|---|
| Type | `Invoice` | `BusinessOperationInvoice` |
| Site | `domain/invoices/_models.py:500` | `application/ledger/_business_operation_invoice.py:154` |
| Fields | ~36 | ~20 |
| Line items | `lines: tuple[InvoiceLine, ...]` (`:543`) | none |
| Date typing | `issued_at: date` (`:511`) | `invoice_date: str` (`:177`) |
| Validators | 11 `model_validator` + 4 `field_validator` | 3 `field_validator` |
| Repository | `InvoiceCatalogueRepository` | `BusinessOperationInvoiceRepository` (`:365`) |
| Operator verb | `aeat app ledger invoice catalogue …` | `aeat app ledger invoice …` |

#### Why rich wins on the evidence

The rich aggregate is a strict superset on every axis the tax domain needs. Fields the slim store has no equivalent for, quoted from the declaration:

- `invoice_class: InvoiceClass = InvoiceClass.ORDINARIA` (`:508`) — ordinaria / simplificada / rectificativa
- `series: str | None` (`:509`), `rectifies_invoice_number: str | None` (`:555`)
- `operation_date` + `operation_date_role: InvoiceOperationDateRole | None` (`:512-513`) — the devengo axis
- `retention_rate` / `retention_amount` (`:551-552`) — retención
- `recargo_amount` (`:553`), `suplido_amount` (`:554`)
- `iva_category: IvaCategory | None` (`:547`)
- `oss_ioss_regime` / `oss_transaction_kind` (`:549-550`)
- `payment_status: PaymentStatus` (`:544`), `payment_id` (`:556`)
- `legal_mentions: tuple[InvoiceLegalMention, ...]` (`:538`), `exemption_reference` (`:537`)
- `issuer_address` / `recipient_address` (`:525-526`) — carrying a genuine RD 1619/2012 art. 6.1.e comment on why they are named by legal role rather than party-relative
- `linked_transaction_ids` (`:545`)

FX is the axis where a falsifier looked most likely, and rich wins there too: it exposes six euro projections (`base_total_eur`, `iva_total_eur`, `grand_total_eur`, `retention_amount_eur`, `recargo_amount_eur`, `suplido_amount_eur`, `:565-614`) against the slim store's two (`taxable_base_eur`, `total_amount_eur`, `:235-242`), plus FX invariants the slim store does not enforce (`:674-679`: a EUR invoice must not carry an fx_rate; fx_rate and fx_rate_date must be set together; fx_rate must be strictly positive).

#### What would falsify it — and partially does

The honest counter-evidence. **The slim store carries three fields the rich aggregate genuinely lacks** (confirmed by grep returning empty against `domain/invoices/`):

1. **`eu_iva_id`** (`_business_operation_invoice.py:193`) — and this one is load-bearing, not cosmetic. `_business_invoice_party_tax_id` at `application/invoices/_source_resolver.py:675-679` reads `(invoice.eu_iva_id or invoice.counterparty_nif)`, **preferring the EU VAT ID** for the declared party id, and `_business_invoice_country_code` (`:682-689`) derives the M349 country prefix from it. The rich aggregate has a single `counterparty_tax_id` (`_models.py:515`) which must serve both roles — so for an EU counterparty holding both a domestic NIF and an EU VAT ID, the slim store can record both and declare the correct one; the rich aggregate cannot. Compare the rich projection at `_source_resolver.py:410,426`, which passes `party_tax_id=invoice.counterparty_tax_id` with no such preference.
2. **`created_at`** (`:195`)
3. **`updated_at`** (`:196`)

None of these overturn the verdict — rich is a superset on roughly twenty other axes — but they make the collapse a *migration of three fields onto rich*, not a deletion of the slim store. A plan that deletes the slim store without first adding `eu_iva_id` to the rich aggregate silently degrades M349.

**What would overturn the verdict outright:** evidence that the slim store is the only one reaching a modelo the rich store cannot serve. It is not — see below, both feed one resolver.

#### Both stores are live at the calculation boundary

This is the finding that most changes the plan's shape. `InvoiceCatalogueSourceResolver` (`application/invoices/_source_resolver.py:125`) is a **single resolver that loads both stores and unions their observations**:

- rich: `repository.load()` → `catalogue_observed` (`:151-176`)
- slim: `_load_business_operation_invoices(...)` → `business_observed` (`:178-197`)
- union: `observations = tuple(... catalogue_observed) + tuple(... business_observed)` (`:198-200`)

So neither store is dormant, and the duplication is currently *papered over at the resolver* rather than being a dead branch. The convergence type is `InvoiceObservation` (`domain/calculations/registry/_invoice_bindings.py:71`), which is already keyed on the sanctioned `BindingSourceKind` taxonomy — that is the correct canonical fact type and needs no rename.

**Collapse is legal without a data migration:** `cadrumo.core.COMPATIBILITY_REGIME` is `CompatibilityRegime.PRE_RELEASE` (`core/compatibility_lifecycle.py:53`), so `no-legacy-compatibility` governs — delete, do not migrate. The three-field gap above is a *schema* precondition, not a data-migration one.

#### Incidental defect found while grounding

`InvoiceObservation.source_kind` carries a **default**: `source_kind: BindingSourceKind = BindingSourceKind.COLLECTIBLE_INVOICE` (`_invoice_bindings.py:86`). A direction axis with a silent default means an observation constructed without an explicit direction silently declares as *issued*. This is the shape `no-silent-under-declaration` exists to prevent. Worth a plan step independent of any rename.

---

### 2. The conflation map

#### 2a. The direction axis is declared four times

This is the sharpest conflation. One concept — is the taxpayer owed, or does the taxpayer owe — has four separate declarations:

| Declaration | Site | Members | Verdict |
|---|---|---|---|
| `BindingSourceKind.PAYABLE_INVOICE` / `.COLLECTIBLE_INVOICE` | `core/aggregation.py:326-327` | `payable_invoice`, `collectible_invoice` | **CANONICAL — correct as-is** |
| `InvoiceKind` | `domain/iva/_classification.py:102` | `issued`, `received` | misplaced (see 2b) |
| `InvoiceKindOption` | `entrypoints/cli/_ledger_business_invoice_cli.py:70` | `issued`, `received` | **redundant** — its own docstring says "Mirrors `InvoiceKind`" |
| `BusinessOperationInvoiceDirection` | `application/ledger/_business_operation_invoice.py:67` | `payable_invoice`, `collectible_invoice` | **redundant** — byte-identical values to `BindingSourceKind` |

`BusinessOperationInvoiceDirection`'s own docstring concedes the point: "The member string values … are the load-bearing internal source-kind taxonomy per `aeat-spanish-stem-naming` and are preserved; only the enum TYPE name is the direction axis." It is a second Python type over the same two canonical strings.

**Respecting `aeat-spanish-stem-naming`:** that rule's explicit operator-directive exception makes `payable_invoice` / `collectible_invoice` canonical and bars collapsing them into a bare `invoice` source kind, and makes the operator-facing CLI noun the English `invoice` with `--kind issued|received`. **Both are correct as they stand and neither is proposed for change here.** What is proposed is removing the *duplicate Python types* over those same canonical strings — which the rule does not protect and `retired-enum-members-need-consumer-reconciliation` governs.

Proposed, in dependency order:
- `BusinessOperationInvoiceDirection` → **retire**, consumers move to `BindingSourceKind` (values already identical, so this is type-level only)
- `InvoiceKindOption` → **retire**, CLI types its `--kind` option directly on `InvoiceKind` (the CLI already round-trips through `InvoiceKind(kind.value)` at `_ledger_business_invoice_cli.py:94`)
- `InvoiceKind` → **relocate** to `domain/invoices/_enums.py`, keeping the name

#### 2b. `InvoiceKind` lives in the wrong domain

`InvoiceKind` is declared in `domain/iva/_classification.py:102`, not in `domain/invoices/`. Its docstring records that it already absorbed an earlier split (`InvoiceDirection` substrate vs `InvoiceKind` invoices, "identical semantics with mismatched lowercase / uppercase string values") — so a prior canonicalisation of this exact axis has already happened once. The type is used by `Invoice.kind` (`_models.py:507`), the CLI, the review filter and the registry tests. Its home should follow its meaning.

This is precisely the shape `binding-names-reserved-for-registry-input` set the precedent for: a name reserved for one concept, homonyms renamed or relocated to what they actually are.

#### 2c. The operator-facing verb tree inverts the canonical relationship

Measured from the Typer registrations in `_ledger_business_invoice_cli.py`:

- `invoice_app` (`:170`), mounted as `invoice` (`:87`) — **5 commands** (`:180, 276, 306, 357, 996`) → the **SLIM** store, via `_service_for_kind` returning `PayableInvoiceService | CollectibleInvoiceService` (`:91-97`)
- `catalogue_app` (`:416`), mounted as `invoice catalogue` (`:86`) — **6 commands** (`:582, 665, 768, 870, 915, 950`) → the **RICH** store

So the bare, sanctioned, most-discoverable operator noun `aeat app ledger invoice add` writes the *impoverished* schema, while the canonical aggregate sits one level deeper under `catalogue`. The CLI source itself calls the target "the slim CRUD service" (`:93`). Whatever else the plan does, this inversion is the operator-visible face of the conflation.

Note the naming constraint interaction: the `invoice` noun and `--kind issued|received` are operator-directive-protected. The fix is therefore not to rename the verb but to **repoint it at the canonical store**.

---

### 3. Blast radius

Counted with `rg -c -w <symbol>` at HEAD, tallied across files. **`docs/_build/**` is excluded** — it is generated Sphinx output, not a rename site. Counting it inflates several symbols by 3-6x (`PurchaseInvoiceEvidence` alone reads 150 with it, 0 without; `InvoiceCatalogue` reads 226 with it, 1 without). Any plan quoting docs counts that include `_build` is quoting build artefacts.

| Symbol | prod | tests | docs+dev | **total** |
|---|---:|---:|---:|---:|
| `Invoice` (bare) | 258 | 281 | 57 | **596** |
| `InvoiceKind` | 142 | 354 | 0 | **496** |
| `InvoiceCatalogueRepository` | 88 | 304 | 0 | **392** |
| `InvoiceCatalogue` | 148 | 237 | 1 | **386** |
| `InvoiceObservation` | 54 | 35 | 0 | **89** |
| `PurchaseInvoiceEvidence` | 50 | 25 | 0 | **75** |
| `BusinessOperationInvoiceDirection` | 23 | 27 | 0 | **50** |
| `BusinessOperationInvoice` | 37 | 12 | 0 | **49** |
| `InvoiceDraft` | 32 | 10 | 0 | **42** |
| `InvoiceKindOption` | 13 | 0 | 0 | **13** |

Facade exports carrying an invoice-named symbol (`__all__` entries requiring update on any rename):

- `domain/invoices/__init__.py` — 27
- `application/invoices/__init__.py` — 45
- `application/ledger/__init__.py` — 46
- **total 118**

#### The two calls to make on sequencing

**The largest renames are the ones to avoid.** `Invoice` (596) and `InvoiceCatalogue` (386) are the bare/ambiguous names, and renaming them is the most expensive thing this campaign could do. Grounded recommendation: **do not rename them.** Once the slim store is retired there is only one invoice schema, so the bare name `Invoice` stops being ambiguous by construction — the ambiguity is caused by the duplication, not by the name. Retiring the duplicate is both the cheaper and the more honest fix.

**The cheap, high-value renames** are the redundant direction types: `InvoiceKindOption` (13 sites, zero test sites) and `BusinessOperationInvoiceDirection` (50). Both are pure type-level retirements over already-canonical string values.

Per `aeat-architecture-boundaries` each relocation is one atomic commit — canonical-site move, every consumer, every fixture, every `__all__` baseline, subject-tagged `relocation:<symbol>` — and per `aeat-docs-scaffolding-cli` each must run `python -m dev.docs.apidocs scaffold` in the same commit.

---

### 4. Operator decision — slim retired, canonical used

Decision recorded: **the slim `BusinessOperationInvoice` implementation is removed; the canonical `Invoice` is the single invoice schema.** Two semantically identical intents will not both exist.

The one precondition that survives from §1 is not a challenge to the decision, only its ordering: **`eu_iva_id` must land on the canonical `Invoice` before the slim store is deleted**, because `_source_resolver.py:675-679` prefers it over the NIF when declaring the M349 party id, and the canonical aggregate has no equivalent field. `created_at` / `updated_at` follow the same rule but carry no declaration consequence. Delete-then-add regresses M349; add-then-delete does not. `COMPATIBILITY_REGIME` is `PRE_RELEASE`, so no data migration is owed — only the schema ordering.

The other work the retirement implies, all grounded above: the `ledger invoice` verbs (`_ledger_business_invoice_cli.py:180, 276, 306, 357, 996`) repoint from `PayableInvoiceService | CollectibleInvoiceService` to the canonical catalogue; the slim branch of the union resolver (`_source_resolver.py:178-197`) and its projection helpers (`:579-689`) go with it; `BusinessOperationInvoiceDirection` and `InvoiceKindOption` are retired as duplicate types over already-canonical values.

---

### 5. The subclassing option — assessed against the code

**Recommendation: adopt it, narrowly — a base `Invoice` with `IssuedInvoice` / `ReceivedInvoice` subclasses discriminated on `kind`. But expect it to solve less than it appears to, for the reason in the caveat.**

#### What the measurement says

Of 14 `model_validator`s on `Invoice`, **only 2 branch on `kind`** (`_models.py:910, 987`). That sounds like weak support for subclassing — but both are genuine *field-shape* divergences, not behavioural ones, which is exactly the case subclassing is for:

1. **`counterparty_tax_id` optionality** (`:909-914`) — optional only when the invoice is SIMPLIFICADA *and* ISSUED. The refusal message states the asymmetry directly: "on a RECEIVED invoice it names the issuer's own identity, which stays mandatory". As subclasses this becomes `ReceivedInvoice.counterparty_tax_id: str` (required) against `IssuedInvoice.counterparty_tax_id: str | None` — a type-level guarantee instead of a runtime refusal.
2. **OSS/IOSS axes are issued-only** (`:987-988`) — "OSS/IOSS invoice projection only applies to issued invoices". As subclasses, `oss_ioss_regime` and `oss_transaction_kind` simply *do not exist* on `ReceivedInvoice`.

The second is where this earns its keep. `Invoice.model_config` is `STRICT_FROZEN_CONFIG` = `ConfigDict(strict=True, frozen=True, extra="forbid")` (`core/_models.py:39`). With `extra="forbid"`, moving the OSS fields onto the issued subclass makes a received-invoice payload carrying an OSS axis **structurally unconstructible** rather than constructible-then-refused. That is a real strengthening, and it is the kind of guarantee this codebase's rules consistently prefer.

#### Why it is also cheap

This is the decisive practical argument, and it is why subclassing beats renaming. `Invoice` remains the base class and keeps its name, so **the 596 bare `Invoice` sites stay valid** — a parameter annotated `Invoice` accepts either subclass. Compare a rename of `Invoice`, which would touch all 596. Subclassing gets the disambiguation the operator wants while leaving the largest site set untouched.

#### What it costs

The catalogue boundary is the whole cost, and it is concentrated:

- `InvoiceCatalogue.invoices: Mapping[str, Invoice]` (`:1060`) becomes a discriminated union — `Annotated[IssuedInvoice | ReceivedInvoice, Field(discriminator="kind")]`.
- `Invoice.model_validate(item)` is **hardcoded to the base class** at `:1076`. Left as-is, a persisted `IssuedInvoice` deserializes back to base `Invoice` and silently loses its subclass, which breaks the strict save→load→equality requirement in `aeat-roundtrip-discipline`. This one line is the single highest-risk site in the change.
- That rule also requires an anti-tautology proof per persistence boundary: corrupt the persisted `kind`, reload, assert refusal.

#### The caveat — do not over-expect

**47 of the 50 production `InvoiceKind.ISSUED|RECEIVED` branch sites are outside the invoice record** (`domain/invoices/` accounts for 3). The concentration is `domain/iva/` with 26 — `_classification.py` (14), `_components.py` (6), `_invoice_classification.py` (3), `_flow.py` (3) — plus the aggregation layer. Those branch on **IVA treatment**, not on record shape: they take an invoice and decide how it classifies. Subclassing the record will not remove them and should not be expected to. If the plan's success criterion is "kind-branching disappears", it will fail; the criterion should be "the record's *shape* divergences become structural".

#### One thing not to do

Do not introduce a second subclass axis for payable/collectible. That is the same axis in the source-kind vocabulary — `invoice_direction_to_source_kind` (`application/invoices/_source_resolver.py:109-122`) is the declared one-way mapping, and `aeat-spanish-stem-naming` protects those two strings as the internal taxonomy. One axis, two subclasses, `kind` as the discriminator.

---

*Per-lane exhaustive site inventories still pending; four discovery lanes are running.*
