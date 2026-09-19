---
tags:
  - "#adr"
  - "#invoice-canonical-structure"
date: '2026-08-06'
related:
  - '[[2026-08-06-invoice-canonical-structure-research]]'
  - '[[2026-08-06-invoice-canonical-structure-lane-discovery-sweep-research]]'
  - '[[2026-08-06-invoice-canonical-structure-audit]]'
  - '[[2026-08-06-invoice-canonical-structure-naming-and-capability-reference]]'
  - '[[2026-06-10-ledger-invoice-unification-adr]]'
  - '[[2026-08-05-ledger-invoice-decomposition-adr]]'
  - '[[2026-08-06-llm-package-split-adr]]'
  - '[[2026-08-06-llm-invoice-read-reconciliation-adr]]'
supersedes:
  - '2026-06-10-ledger-invoice-unification-adr'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:aafc7fca0a42022f9579bd55287e7cdebb166413c69b8ce283ac2bb0e924dd7d'
---
# `invoice-canonical-structure` adr: `One canonical invoice aggregate; delete the slim store` | (**status:** `accepted`)

## Supersession

This ADR **supersedes** `2026-06-10-ledger-invoice-unification-adr` on one point:
its ruling that both invoice aggregates survive. Everything else that ADR decided
— the unified `invoice --kind` operator surface, the locked
`payable_invoice` / `collectible_invoice` source-kind taxonomy, the CLI backend
boundary — is carried forward unchanged and reaffirmed.

That ADR anticipated this moment and warned against it: it recorded the two-store
split as a documented sharp edge "so a future agent does not 'unify' them by
mistake". That warning is honoured by engaging it rather than by leaving the
split alone. What follows states what it decided, why, what has changed, and why
the balance now falls the other way.

**What it decided and why.** It collapsed two CLI noun-groups into one and kept
both aggregates, on the stated ground that they serve different layers: "The
unified command drives the **slim** `BusinessOperationInvoice` — the operator-CRUD
record. The **rich** `Invoice` remains the calculation aggregate consumed by
modelo aggregation." Given that division, two stores are not duplication; they
are a read model and a write model, and merging them buys nothing. **That
reasoning was correct on the facts as they stood.**

**What changed.** The division of labour it rests on no longer exists. Commit
`432fc96d29` (2026-06-28, "fix(modelo): feed m349 from business invoices"), landed
18 days later, put the slim store into the calculation mesh:
`_load_business_operation_invoices`
(`src/cadrumo/application/invoices/_source_resolver.py:552-570`) and the slim
observation adapter (`:579-610`) now feed M347 and M349 alongside the rich
catalogue, unioned at `:200-202`. The resolver's own docstring records the
convergence (`:6-18`). The slim record is a calculation input. The premise is
falsified in the code, not merely contested in argument.

The commit has no governing vault record. It was an implementation of the
taxonomy lock this ADR is superseding, executed under
`2026-05-20-calculation-source-connectivity-adr`, and nothing at ADR level
protects it independently.

**What the prior ADR did not weigh.** Three consequences follow from the changed
premise, none of which its Consequences section addresses. It reasoned about an
id-space confusion at the `link` verb; it did not reason about two stores feeding
one aggregation.

1. **An unguarded double-count.** Each store refuses duplicates within itself
   (`_creation.py:284-287` raises; `_business_operation_invoice.py:294`
   disambiguates) and neither can see the other. The two id derivations hash
   disjoint tuples (`domain/invoices/_models.py:85-124` versus
   `_business_operation_invoice.py:267-298`), so no id correspondence exists and
   dedup by identity is structurally impossible. The same real invoice recorded
   in both stores is counted twice. On M349 it does not even surface as two rows:
   `_build_operator_clave_rows`
   (`src/cadrumo/domain/calculations/registry/_invoice_bindings.py:822-859`)
   groups by `(country_code, party_tax_id, clave)` with no invoice id in the key
   and accumulates at `:844`, producing one row with a doubled importe. On M347
   it inflates the per-party annual total (`:557-563`) and can push a
   counterparty across the EUR 3,005.06 declaration threshold.
2. **An under-declaration from the parallel implementation itself.**
   `_intracommunity_clave` (`_source_resolver.py:436`) falls back from
   `operation_type` to `iva_category` (`:445-463`); its slim twin
   `_business_invoice_clave` (`:663`) has no fallback and drops the invoice
   (`:588-590`). The slim record cannot hold an `iva_category` at all, so the
   asymmetry is unclosable within its shape.
3. **A test that constructs the hazard and blesses it.**
   `src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_link_flow.py:136-160`
   creates one invoice in both stores and asserts only that the ids differ. It
   never aggregates the pair. The suite is green over the exact configuration
   that double-counts.

**Why the balance falls the other way.** The prior ADR traded a maintenance cost
against an operator-ergonomics cost and chose correctly for the architecture it
described. The trade is now between a maintenance cost and a **filing-correctness
cost in both directions**, on informativas that name third parties by NIF. That
is a different trade. It is also worth recording that two dedicated duplication
audits (`2026-07-25-code-dedup-sweep-rag-inventory-audit`,
`2026-06-13-semantic-dedup-epic-audit`) passed over this pair without flagging
it — the split reads as intentional to a sweep, which is precisely why it needs
an ADR to retire it rather than a cleanup pass.

**Relationship to `2026-08-05-ledger-invoice-decomposition-adr` (proposed).** That
record restates two-aggregate survival as settled and explicitly declines to rule
on "whether the slim `BusinessOperationInvoice` gains retención fields, or
issuing professionals are directed to the rich `Invoice` — a product-surface
choice between two accepted aggregates". This ADR answers that deferred question:
neither. The slim store is deleted and issuing professionals use the canonical
aggregate. If that record is accepted before this one, its deferral stands
resolved by this ADR rather than contradicted; if this one is accepted first, its
deferral is moot. Either ordering is coherent; both records should not
independently decide it.

## Problem Statement

Two records model one concept, both reachable from one operator noun, both
feeding the same calculations, with no reconciliation between them. The
consequences are set out above and evidenced in
`2026-08-06-invoice-canonical-structure-research`.

Beyond the duplication itself, the canonical aggregate's own fields are largely
unreachable from single-invoice entry, so choosing a canonical home does not by
itself make the surface usable. Both problems are in scope because fixing only
the first leaves an operator with one store they still cannot express a retención
or a regime in.

## Considerations

- **The rich record is the richer *schema*, but it is NOT a constraint-shape
  superset, and the fold is a narrowing.** An earlier draft of this record
  claimed superset status by citing the substitutability pre-filter
  (`aeat-swarm-audit-cadence`). That was the pre-filter run backwards: it
  compares *field presence*, and the pre-filter is about *constraint
  permissiveness*. Run correctly, the rich model carries at least four
  constraints the slim model does not — a required non-empty
  `counterparty_name`, a required two-letter `counterparty_country`, at least
  one line item, and an exact invoice-level totals identity — where the slim
  model carries **no `model_validator` at all**, only three field validators.
  The pre-filter's verdict on a site in this shape is "NOT promotable without
  documenting the mismatch", so the mismatch is documented here rather than
  asserted away.

  **This does not weaken the decision to canonicalise; it changes what the
  decision costs.** The rich model being stricter is the point — the weaker
  surface currently sits behind the *more discoverable* verb, which is a
  validation asymmetry on a filing path. But there is a real cost, it is an
  operator-visible narrowing of the input contract, and P03 must decide
  explicitly what the fold does with a slim shape the rich model refuses. The
  live proof is in the tree: `test_catalogue_invoice_link_flow.py:143-155`
  writes an `invoice add` record with no counterparty name, no country and no
  lines, and it passes today.

  Direction of travel: the slim record is a **strict subset in three fields**
  — `eu_iva_id`, `created_at`, `updated_at` — which the rich aggregate lacks
  (verified by `rg` against `src/cadrumo/domain/invoices/`). One of them is
  load-bearing; see D-O.
- **Two properties are held only by the slim store.** Physical partition of the
  lanes into separate documents keyed by `source_kind`
  (`_business_operation_invoice.py:390-391`, services pinned at `:714, :720`), and
  a flat operator-edit shape. The rich catalogue is a single mixed-kind container
  (`domain/invoices/_service.py:100-118`) whose lane discipline is enforced at six
  per-consumer sites. Reproducing the partition is possible but is not obviously
  worth its cost; dropping it must be a stated decision, not an oversight.
- **`no-legacy-compatibility` governs in full.** The pre-release regime is
  confirmed active by `2026-07-09-compatibility-lifecycle-adr`, and no ADR carves
  out an invoice-specific exception. Delete, do not bridge; no alias, no
  deprecation window, no re-export.
- **The source-kind strings stay.** `payable_invoice` and `collectible_invoice`
  remain load-bearing in registry TOML, `BucketEventType`, storage key grammar and
  `BindingSourceKind`. Deleting the slim *store* does not touch the *taxonomy*;
  the canonical aggregate's `kind` maps onto it through the existing contractual
  function (`_source_resolver.py:109-122`).
- **Capability conservation outranks every other constraint here** (D-R). No
  capability of either store may be lost, across all three evidence lanes, and no
  deletion precedes a proven replacement.
- **A separate team executes `2026-08-06-llm-package-split-adr` in this same
  worktree, and the file boundary between us is settled.** They own the
  `InvoiceDraft` model and the extraction path — the line-carrying draft
  structure, the per-rate breakdown their deterministic parsers produce, and the
  draft-side recargo slot — mapping onto `InvoiceLine` directly rather than
  inventing a parallel shape. This record owns the invoice stores, the writer, the
  confirm *function's* parameter list and gate, and the M303/M390 screens.
  `_evidence_draft.py` is edited by both lanes and this boundary is what keeps
  them out of each other's way. Ordering: D-G's multi-line writer lands before
  their producer Step; their draft recargo slot lands before D-M's confirm-side
  half. Both lanes have recorded the partition and each other's Step ids in
  their own plans, so a receiving pair can reconcile without either coordinator.
- **A correction accepted from that lane, recorded because this record asserted
  the wrong thing.** An earlier reading of `evidence add` called its
  clock-bearing derived id a straight breach of
  `single-subject-mutation-is-idempotent-guarded`. It is not, and the remedy is
  **not** to drop `created_at`: `derive_purchase_invoice_evidence_id`
  (`application/ledger/_evidence.py:162-202`) records in its own docstring that
  `created_at` plus the `disambiguator` ordinal **preserve a genuine-duplicate
  case the ledger deliberately supports** — two evidence records for the same
  file must keep distinct ids. Removing the clock would silently collapse real
  duplicates, a worse defect than the one being corrected. The rule already
  supplies the right shape, and it is the one that lane is building: a
  caller-supplied idempotency key yielding a clock-free id and a guarded no-op on
  retry, with the keyless path remaining deliberately `non_idempotent_append` and
  documented as such. Any surface in this campaign that calls that verb uses the
  keyed path.
- **A peer campaign constrains sequencing.**
  `2026-08-06-llm-invoice-read-reconciliation-adr` (proposed) binds itself to
  "must not alter the `Invoice` domain model", and the working tree carries live
  changes under `.vault/exec/2026-08-05-ledger-invoice-decomposition/`. This work
  must sequence around concurrent edits rather than assume a quiet tree.

## Considered options

- **Fold onto the rich aggregate and delete the slim store — CHOSEN.** Closes the
  double-count by construction rather than by a guard, and lands on the record the
  calculation layer already consumes most deeply. Cost, honestly stated: it is a
  *narrowing* of the operator input contract, not a re-home, and it requires three
  fields to migrate onto the canonical model first (D-O).
- **Fold onto the slim record — rejected.** The slim record cannot hold an
  `iva_category`, has no line concept, and carries no cross-field consistency
  validation at all. Folding onto it would discard the mixed-rate, regime and
  provenance capability the tax domain needs, and would deepen the very
  under-declaration the campaign exists to close.
- **Keep both stores and build cross-store dedup — rejected.** It would
  institutionalise the split, and it is not merely costly but structurally
  impossible as posed: the two id derivations hash deliberately disjoint tuples,
  so no id correspondence exists to reconcile on. Any dedup would have to invent a
  fuzzy identity between two records that were designed not to share one — a new
  failure mode on a filing path.
- **Keep both stores and guard the aggregation instead — rejected.** A guard a
  later refactor can bypass, protecting an invariant that one store's deletion
  makes unnecessary. It also leaves the clave asymmetry unclosable, since it lives
  in the slim record's *shape*, not in the aggregation.
- **Defer the whole question and fix only the writer surface — rejected as a
  standalone outcome, and it is the specific failure this campaign guards
  against.** P02 alone makes the rich writer more attractive while the shorter,
  more discoverable verb still writes the weaker store, so it *raises*
  double-count exposure. It is retained as a phase, never as an endpoint.
- **Stage or defer the fold on evidence — RETAINED AS A LIVE OPTION.** Per D-R,
  if the capability inventory finds a capability with no canonical replacement, or
  the capability-parity proof cannot be written, the fold is staged or deferred
  with the missing pieces named. This is not a fallback for failure; it is the
  option the parity proof exists to choose between.

## Constraints

- The canonical aggregate MUST remain an encrypted secure object with no
  plaintext sidecar and no parallel write path
  (`composition-service-no-parallel-write-path`,
  `sensitive-financial-data-secure-storage-only`).

  **Storage scope, corrected.** An earlier form of this constraint asserted the
  canonical aggregate is "bucket-scoped". It is not, and the sentence described
  the store being *deleted*. The two stores differ on scope, and the fold moves
  records across that difference:

  | | slim (`LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE`, deleted) | canonical (`INVOICE_CATALOGUE_NAMESPACE`, survives) |
  |---|---|---|
  | namespace scope | `BUCKET_LOCAL` | `PROFILE_LOCAL` |
  | object-key grammar | `{bucket_id}:{source_kind}` | `catalogue` — one document per profile |
  | `bucket_id` on the record | required, and a key component | `BucketId \| None`, an optional field |

  Both are `FINANCIAL` sensitivity and `STRUCTURED_CUSTODY`
  (`adapters/persistence/storage/_namespace_registry.py`). The consequence the
  fold must own is therefore **not** a confidentiality downgrade but an
  *attribution* one: bucket identity stops being a structural key component that
  the store cannot represent a record without, and becomes an optional field a
  writer may omit. Nothing in the storage layer refuses the omission.

  This is why `P01.S35` exists and why it is a precondition of the fold rather
  than a cleanup: the fold is the event that widens the producer set onto the
  permissive model. It is resolved in favour of **declaring** an unattributed
  invoice rather than refusing it — the projection admits it, and
  `InvoiceCatalogueRepository` still refuses a row naming a *different* bucket,
  so cross-bucket isolation is unchanged. Silently dropping such a record from
  M347/M349 was the failure mode, and it is closed.

  Custody carry is unaffected, and was checked rather than assumed:
  `application/user_profile/_custody_carry.py` registers an explicit
  natural-key resolver for both slim namespaces and none for the canonical one,
  but the canonical namespace declares `default_object_key`, so the carry
  supplies a fixed resolver for it; a populated carried namespace with no
  resolver raises fail-closed rather than dropping silently. Deleting the slim
  namespaces removes two resolver registrations that will then have no
  namespaces to serve.
- M347 and M349 MUST continue to be sourced correctly across the transition. No
  step may leave a window in which invoices reaching those modelos today reach
  them no longer.
- The CLI root surface stays at `config` / `app`; the operator noun stays
  `aeat app ledger invoice`.
- Every symbol relocation lands as one atomic explicit-path commit including
  consumer updates, fixture updates and `__all__` updates
  (`aeat-architecture-boundaries`).
- This ADR does not decide the document-ingestion architecture. See Dependencies.

## Decision

**D-A — The rich `Invoice` is the canonical invoice aggregate. The slim
`BusinessOperationInvoice` is folded into it and deleted.** Deleted means removed
from the tree: the model, the two services, the repository, the namespace, the
CLI verbs that write it, its payload schemas and its locale leaves. No alias, no
bridge, no compatibility shim. The `payable_invoice` / `collectible_invoice`
source-kind strings survive untouched.

Two sub-decisions the fold cannot leave implicit, both flowing from the corrected
constraint-shape Consideration above:

- **A-i — The fold rule is declared per refused invariant.** For each of the four
  canonical invariants the slim model does not carry — non-empty
  `counterparty_name`, two-letter `counterparty_country`, at least one line, and
  the exact totals identity — the fold states whether it **synthesises** a value,
  **defaults** one, or **refuses** the record. Any refusal must name the missing
  invariant and the accepted form. Leaving this to whoever writes the code is how
  a narrowing becomes a surprise at the operator's keyboard.
- **A-ii — The lane partition is decided, not dropped.** The slim store physically
  partitions the two lanes into separate documents keyed by `source_kind`; the
  canonical catalogue is a single mixed-kind container whose lane discipline is
  enforced per-consumer. Whether the partition is reproduced or consciously
  dropped is a decision this record requires be **stated**, with the surviving
  per-consumer gates enumerated and what each still guarantees named. Silence
  here is the oversight the Consideration warned about.

**D-B — The operator noun collapses to one CRUD surface over the canonical
aggregate.** `aeat app ledger invoice {add,view,list,update,remove}` and
`aeat app ledger invoice catalogue {create,wizard,...}` become one set of verbs
over one store. The `catalogue` sub-noun disappears, since there is no longer a
second thing for it to distinguish. `--kind issued|received` is retained as the
prior ADR established it.

**D-C — Before any deletion, the slim store's declarable coverage is proven
reproducible on the canonical path.** Specifically the M347 per-party totals and
the M349 operator rows. The gate is **declarable coverage** — every declarable
fact the slim store contributes today is reachable on the canonical path — and
explicitly **not** output-equality with the two-store union. For a bucket
exercising both stores with the same real invoice, the union's totals are
*doubled*; a gate demanding the canonical path reproduce the union would demand
it reproduce the defect. Any restatement of this decision that says "the same
totals the two-store union produces today" is a mis-translation and must be
corrected to this wording.

The clave asymmetry is resolved in the canonical direction: the `iva_category`
fallback that `_intracommunity_clave` (`_source_resolver.py:436`) already carries
is the behaviour that survives. Scope note: the asymmetry is **M349-only**.
`_business_invoice_observation` returns the M347 observation *before* the clave
check (`:586-587`), so M347 is unaffected by the drop at `:588-590`. Because the
canonical path already carries the fallback and the slim record cannot hold an
`iva_category` at all, the asymmetry closes **by the deletion in P03**, not by
any change to `_source_resolver.py` — a Step claiming to "make the fallback
surviving" would be a Step with nothing to do.

**D-D — The double-count is closed by construction, not by a guard.** Once one
store exists there is nothing to reconcile. No cross-store dedup is built,
because building one would institutionalise the split this ADR removes. The
blessing test
`src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_link_flow.py:136-160`
is retired with the store it describes — and the *other* tests in that module,
which exercise the surviving `link` verb, are kept.

**D-E — The writer surface is extended to reach the canonical model's fields.**
`create_catalogue_invoice` and the CLI entry verbs gain `--recargo`, an explicit
`--iva-category`, `--invoice-class`, `--series`, and `--operation-date` on every
entry verb including the guided one. Stated as an assertion-authority question:
**these are facts the operator may assert, independent of whether any extraction
pass can read them.**

Two corrections to an earlier draft of this decision. First, **retención has
already landed** — `--retention-rate` / `--retention-amount` are present on both
`catalogue create` and `catalogue wizard` at HEAD, added by `ef0438561d`, the
same commit that landed this ADR. The assertion that the writer accepted no
retención parameter was false when committed; what remains open is only the
encrypted-roundtrip proof that the two fields persist. Second, **this is not the
joint-scope D2 decision.** D2's subject is the confirm-boundary override set, a
different surface entirely; it is now decided at D-L. Labelling D-E as D2 made an
undelivered, jointly-top-prioritised item look delivered.

Every option added here lands inside the peer totals identity pinned by
`2026-08-05-ledger-invoice-decomposition-adr` (D10, amended 2026-08-06):
`grand_total == base_total + iva_total + recargo_amount`, with retención
*outside* `grand_total`. `--recargo` in particular is a term inside that
identity. The two records must not disagree about what `grand_total` contains.

**D-F — Retención is not added to the extraction draft.** A received invoice's
retención is a fact about the taxpayer's own retenedor obligation, not a header
field an extraction pass may assert. Recorded as a decision, with its reason, so
it is not later added as an apparent omission. This is D3, and it is orthogonal
to D-E rather than in tension with it: D-F governs who may assert, D-E governs
where the operator supplies. Both hold at once.

**D-G — Mixed-rate invoices are fixed at the writer end within this campaign,
at BOTH synthesis sites.** `build_catalogue_invoice`
(`application/invoices/_creation.py`) stops synthesising exactly one line and
accepts a supplied line set. **`application/invoices/_bulk_import.py` carries a
second synthesis site** — its own docstring records that it "synthesises a single
line item exactly as `build_catalogue_invoice` does" — and it is the *live*
import surface, reachable from `catalogue import`. Fixing only `_creation.py`
leaves the bulk path collapsing mixed rates. Both are in scope.

No persisted-schema change is authorised or needed: `_require_lines`
(`domain/invoices/_models.py:660`) already bounds only the empty case and the
M303 comparison path already iterates lines
(`application/aggregation/_modelo_bindings.py`).

**Recorded plainly, because the source finding says it and this record must
not bury it:** the collapse happens at both ends, and per `LANES` *"closing
either alone changes nothing"*. The reader half (per-rate extraction) is out of
scope here; see Dependencies. So D-G as scoped ships **no operator-visible
behaviour change on the extraction path** — it makes the writer capable of
carrying what a later reader will supply, and it makes an operator-supplied
multi-rate invoice expressible today. A reader of this decision should not
expect a mixed-rate PDF to start working because of it.

**D-H — `application/invoices/_importing.py` is DELETED, not routed.** It is a
second `Invoice` writer with weaker invariants — no FX stamp, no rate-slot
closure, and it silently skips a duplicate identity (`:111-113`) where the
canonical path raises. It is reachable from no CLI verb; it is exported from
`application/invoices/__init__.py` `__all__` and called only by its own tests.

An earlier draft left "deleted or routed" open. It is now settled, on a fact the
earlier pass did not look at: **a routed bulk importer already exists.**
`application/invoices/_bulk_import.py` is the live CSV/XLSX import surface —
reachable from `catalogue import` — and it already routes through
`build_catalogue_invoice` / `create_catalogue_invoice`. Routing `_importing.py`
would therefore produce a *third* import surface duplicating `_bulk_import.py`,
which is the outcome this campaign exists to prevent. Delete is the only
disposition consistent with `no-legacy-compatibility`. Its own tests are deleted
with it; a test asserting the behaviour of a deleted module is not coverage.

This also corrects a cited fact carried into the campaign from `LANES` G2: the
"bulk CSV/XLSX importer" named there as the sole retención write route is
`_bulk_import.py`, not `_importing.py`, and `_bulk_import.py` has **no** retención
support at all. The cited route was dead and the live one could not write
retención — G2 was understated when written, then closed outright by `ef0438561d`.

**D-I — The M303 invoice screen's blind spots are closed, and M390 gains an
equivalent.** The screen (`_modelo_bindings.py:1005-1069`) is extended past its
`counterparty_country == "ES"` filter (`:1113-1123`) and its four-cuota screened
set (`:144-149`) to cover recargo, and an M390-scoped equivalent is added. The
`modelo-390-cuota-devengada-total-equals-reconciliacion-303` blocking rule cannot
substitute: both of its sides derive from the same ledger, so consistent
under-population passes it trivially. That rule is an internal
transport-consistency check and is left as one.

**D-J — `InvoiceLine.category_id` is renamed.** It is a `str | None`
(`domain/invoices/_models.py:428`) that reads as the deduction taxonomy and is
not (`SpendingCategory`, `domain/categories/_spending_category.py`, lives on
`Transaction`). Renamed to state what it is; no type change is authorised here.

Two corrections to an earlier draft. It called the field "untyped", which
overstates: it is untyped *as to taxonomy*, but it does carry a validator
rejecting a blank value (`_models.py:458-465`). The direction of the decision is
unaffected. And the research recorded a **third** site — a preflight path using
`category_id` with the `SpendingCategory` meaning — which this decision did not
mention. The rename must establish first whether that site shares a serialised
key with the invoice-line field or is an unrelated homonym; renaming on the
assumption that they are unrelated, when they cross a boundary, breaks the
preflight silently. Sweep the data consumers, not only the callers.

**D-K — A plausibility gate is added at the confirm boundary.**
`confirm_invoice_draft_from_evidence` (`application/ledger/_evidence_draft.py:702-718`)
gains a check that a document being confirmed as ISSUED was plausibly issued by
this taxpayer, mirroring the hard gate that already refuses an ISSUED invoice as
purchase evidence (`_evidence_reference.py:175-180`). The gate belongs to the core
boundary where a validated artefact arrives, whoever produced it.

**D-L — The confirm-boundary override set mirrors the WRITER, not the reader.
This is the real joint-scope D2.** `confirm_invoice_draft_from_evidence`
(`application/ledger/_evidence_draft.py:702-719`) today accepts overrides for
`counterparty_tax_id`, `counterparty_name`, `invoice_number`, `invoice_date`,
`taxable_base`, `iva_rate` and `currency`, plus `kind`, `counterparty_country`
and `notes` — that is the *extraction draft's* field set, minus `iva_amount`,
which the draft carries and the confirm boundary cannot override. Every writer
field beyond it is unreachable at confirm: `retention_rate`, `retention_amount`,
`recargo_amount`, `invoice_class`, `series`, `rectifies_invoice_number`,
`iva_category` and `operation_date`. An operator confirming a rectificativa, a
retención-bearing professional invoice or a recargo invoice from evidence must
abandon the evidence path and re-enter the invoice by hand.

The override set takes the **writer's** field set because confirm is an
*operator assertion*, not an extraction result. This resolves the apparent
tension with D-F rather than contradicting it: D-F governs what an **extraction
pass** may assert, and retención is not a header field a document can be read
for; the confirm boundary is the operator speaking, and the operator may assert
it. The two decisions partition on *who is speaking*, not on *which field*.

Both source agents agreed this item should ship **first**, on the ground that it
is independently shippable and unblocks the most fields per unit of work. An
earlier draft of this record labelled D-E as D2, which made an undelivered
top-priority item look delivered. That label is withdrawn.

**D-M — Recargo gains a representable slot on the extraction draft. This is the
joint-scope D4, and it is the one place reader-side and writer-side answers
deliberately diverge.** The module says it plainly: *"The recargo has nowhere to
go on this path, so the record silently understates the document by exactly that
surcharge"* (`_evidence_draft.py:488-490`). A peer change has since landed
`PrintedTotalDiscrepancy` (`:501-514`), which *detects* the divergence and
surfaces it as an advisory — so the under-declaration is no longer silent. But
detection without a remedy is worse than it looks: the operator is told the
document totals more than the record and has no field to put the difference in.
An advisory that fires with no available resolution is the shape that trains
operators to ignore advisories.

Recargo therefore diverges from retención (D-F): a printed `base + cuota +
recargo` **is** a header fact the document states, LIVA art. 161, and reading it
is not an inference about the taxpayer's own obligations. It gets a draft slot,
a confirm-boundary override (D-L), and it must satisfy the peer totals identity
`grand_total == base_total + iva_total + recargo_amount`. Companion:
`iva-cuota-devengada-includes-recargo-equivalencia`.

**D-N — `source_jurisdiction` on the invoice models is named, and scoped out
with a reason.** It is required on `Transaction` and is mandatory for IRNR and
art. 93 impatriado treatment, and it exists on **neither** invoice model. An
earlier draft of this record dropped it in silence, which the "Named so they are
not lost to silence" heading forbids. It is named here.

It is scoped out because it is a *jurisdiction-axis* gap, not a duplication one:
adding it to the canonical aggregate would not be affected by, and would not
affect, the fold — it is equally absent from both records, so it is neither
caused by the split nor closed by removing it. Folding it in would widen the
campaign onto the IRNR path for no structural gain, exactly the reasoning that
scopes out T2. It belongs with the same jurisdiction-axis campaign that owns T2
and the `LANES` G6 observation that no single record carries both the IVA and
the jurisdiction axis. **Recorded as deferred, not as absent.**

**D-O — Three fields migrate onto the canonical aggregate BEFORE the slim store
is deleted, and `eu_iva_id` is a hard precondition.** The slim record carries
`eu_iva_id`, `created_at` and `updated_at`; the rich aggregate carries none of
them (verified by `rg` against `src/cadrumo/domain/invoices/` at HEAD). The fold
is therefore a *migration of three fields onto rich*, not a pure deletion.

`eu_iva_id` is load-bearing on a filing path. `_business_invoice_party_tax_id`
(`application/invoices/_source_resolver.py:675-679`) reads
`(invoice.eu_iva_id or invoice.counterparty_nif)`, **preferring the EU VAT ID**
as the declared M349 party id, and `_business_invoice_country_code` (`:682-689`)
derives the M349 country prefix from it, including the EL→GR mapping. The rich
projection (`:409-411`, `:425-427`) passes `party_tax_id=invoice.counterparty_tax_id`
with no such preference and no prefix derivation. For an EU counterparty holding
both a domestic NIF and an EU VAT ID, the slim store records both and declares
the correct one; the rich aggregate cannot. **Deleting the slim store before
rich carries `eu_iva_id` silently degrades M349.** That is the failure mode D-C's
coverage gate exists to catch, and it is named here so the gate is not the only
thing standing between the deletion and a wrong filing.

`created_at` / `updated_at` are audit metadata, not declarable facts. They are
carried onto the canonical aggregate for parity, or their absence is recorded as
a deliberate loss in the fold Step — either is acceptable, silence is not.

**AMENDMENT (2026-08-07, on execution).** The `eu_iva_id` precondition was
discharged by a different and stronger mechanism than the migration this
decision specified, and the field was deliberately NOT added.

`created_at` / `updated_at` did migrate onto the canonical aggregate as written.
`eu_iva_id` did not. The reason is that the canonical model COUPLES
`counterparty_country` to `counterparty_tax_id`: a non-ES country validates the
tax id against that country's published NIF-IVA pattern, so the only
representable party identity is already the one M349 must declare. The premise
above — that "for an EU counterparty holding both a domestic NIF and an EU VAT
ID, the slim store records both and declares the correct one; the rich aggregate
cannot" — is true of the slim record precisely BECAUSE nothing there coupled the
two fields, which is what forced it to carry a second identity and prefer it at
projection time. The canonical aggregate refuses that shape outright.

Adding `eu_iva_id` would therefore install a SECOND party-identity authority on
the record: two fields that can disagree about who was invoiced, on the axis
where a disagreement is a mis-declared intra-community operator. That is the
duplication this campaign exists to remove, not a gap in it.

The EL→GR mapping this decision was most concerned about survives in the core
identity layer and was measured rather than assumed: country `GR` with
`EL123456789` is accepted, country `GR` with `GR123456789` is refused naming the
expected `EL` + 9 digits form, and country `DE` with `DE345678901` is accepted.
The capability is conserved and the wrong prefix now fails loudly where the slim
path would have accepted a mismatched pair.

Both mechanisms are exercised: `test_canonical_invoice_refuses_the_tax_id_country_mismatch_slim_permits`
pins the coupling, and the M349 declarable-coverage proof pins the declared party
identity against a fixture-derived contract.

Recorded because D-O otherwise reads as an unmet hard precondition, and a reader
checking it against the tree finds an absent field with no explanation.

**D-P — `InvoiceObservation.source_kind` loses its default.** The field carries
`= BindingSourceKind.COLLECTIBLE_INVOICE` (`_invoice_bindings.py:86`). A direction
axis with a silent default means an observation constructed without an explicit
direction declares as *issued* — the shape `no-silent-under-declaration` exists to
prevent. The default is removed and the field made required. This is independent
of the fold and of any rename.

**D-Q — Two duplicate direction types are retired; the two large ambiguous names
are NOT renamed.** The direction axis — is the taxpayer owed, or does the taxpayer
owe — is declared four times. `BindingSourceKind.PAYABLE_INVOICE` /
`.COLLECTIBLE_INVOICE` (`core/aggregation.py:326-327`) is canonical and correct as
it stands. Two of the other three are pure duplicates over the same canonical
strings and are retired:

- `BusinessOperationInvoiceDirection`
  (`application/ledger/_business_operation_invoice.py:67`) — member values
  byte-identical to `BindingSourceKind`; its own docstring concedes the point.
  Retired; consumers move to `BindingSourceKind`. It dies with the slim store in
  any case, so this is bookkeeping on the deletion rather than separate work.
- `InvoiceKindOption` (`entrypoints/cli/_ledger_business_invoice_cli.py:70`) — its
  own docstring says "Mirrors `InvoiceKind`", and the CLI already round-trips
  through `InvoiceKind(kind.value)`. Retired; the CLI types `--kind` directly on
  `InvoiceKind`. Thirteen sites, zero test sites.
- `InvoiceKind` (`domain/iva/_classification.py:102`) — **relocated** to
  `domain/invoices/`, keeping the name. Its home should follow its meaning; this
  is the shape `binding-names-reserved-for-registry-input` set the precedent for.

**The bare `Invoice` (596 sites) and `InvoiceCatalogue` (386) are deliberately NOT
renamed.** The ambiguity they carry is caused by the duplication, not by the
names: once the slim store is retired there is only one invoice schema and the
bare name stops being ambiguous by construction. Retiring the duplicate is both
the cheaper and the more honest fix, and a 596-site rename is the most expensive
thing this campaign could do. Recorded as a decision so it is not revisited as an
apparent omission.

Unchanged and operator-directive-protected: the `payable_invoice` /
`collectible_invoice` source-kind tokens and the English operator noun `invoice`
with `--kind issued|received` (`aeat-spanish-stem-naming`). The CLI verb-tree
inversion — the bare, most discoverable noun writing the impoverished schema — is
fixed by **repointing the verb** at the canonical store (D-B), never by renaming
it.

Each retirement and the relocation land as one atomic explicit-path commit
carrying the canonical-site move, every consumer, every fixture and every
`__all__` update, subject-tagged `relocation:<symbol>`
(`aeat-architecture-boundaries`), with `python -m dev.docs.apidocs scaffold` run
in the same commit (`aeat-docs-scaffolding-cli`). Enum member changes reconcile
their consumers first (`retired-enum-members-need-consumer-reconciliation`).

**D-R — Capability conservation is the governing law of this campaign, and it
outranks the fold.** The migration is **engineered, not executed: no capability
loss may occur.** Invoices are the evidence base for three distinct concerns —
**income** (issued, collectible), **business operations** (received, payable) and
**purchase evidence** — and no calculation in this project is legally valid
without them. Operator directive; treated as the highest-stakes decision here.

Four bindings follow, and they are not advisory:

- **A three-lane capability inventory precedes the fold.** Every field, validator,
  CLI verb, downstream binding, and persistence or custody behaviour of *both*
  stores, sectioned by all three lanes, each entry carrying its named canonical
  replacement and the test that proves the replacement works. **A proof covering
  only the payable path is not a proof.**
- **Nothing is deleted until its replacement is proven by a test that fails when
  the capability is absent.** A capability with no named replacement **blocks the
  fold**; it is not waived, and it is not deferred to execution.
- **No silent coercion.** Because the filings' legal validity rests on this
  evidence, a lost, silently-altered or silently-reidentified invoice invalidates
  every downstream calculation. Every value crossing the fold traces to what the
  source record actually held. Where the canonical model needs a value the slim
  record never had, that is a **refusal or an explicit operator input, never a
  synthesised guess**, and a record that cannot be represented fails **loudly at
  migration**. This is why D-A/A-i enumerates the unmigratable classes rather than
  leaving them to whoever writes the fold.
- **The campaign retains authority to stage or defer the fold.** The deciding
  instrument is a **capability-parity proof**: one bucket exercising every
  capability of both stores, run through the canonical path, asserting identical
  M347, M349, M303 and M390 outputs and an identical export/import roundtrip. **If
  that test cannot be written, the fold is not ready and this record says so.** An
  honest "not yet, and here is what is missing" is a successful outcome; shipping
  a capability loss is not.

**D-S — The custody roundtrip proof is strengthened, and a relayed premise is
corrected on the record.** It was reported that `InvoiceCatalogueRepository` has
no custody registration and that canonical invoices are therefore excluded from
profile backup today — making the fold a total loss of the evidence base. **That
is refuted at HEAD**, and the correction is recorded here because a plan built on
it would have encoded a false premise for a team with no context to catch it:

- `INVOICE_CATALOGUE_NAMESPACE`
  (`adapters/persistence/storage/_namespace_registry.py:906-916`) declares
  `custody_disposition=STRUCTURED_CUSTODY` with a `default_object_key`.
- The registry that appeared to lack an entry is a **natural-key resolver map, not
  an inclusion list**. `_custody_carry.py:468-471` falls back for precisely this
  shape — *"Single-document / catalogue stores have a fixed natural key"*. The
  slim repository has an explicit resolver because it is a per-record bound
  repository; the catalogue does not need one.
- A namespace with neither resolver nor default key raises `ProfileExportError`
  (`:472-476`). Custody failure is **loud, not silent**.
- Coverage already exists end to end:
  `application/user_profile/tests/test_custody_store_matrix.py:1001` enrols the
  canonical namespace and verifies it survives the carry.

**The real defect is weaker and different, and it is actioned.** That
verification asserts only that the reloaded catalogue is non-empty (`:319-320`),
which passes even when the boundary drops a field and the loader re-defaults it —
the exact blindness `aeat-roundtrip-discipline` exists to catch, sitting on the
aggregate about to absorb a second store's entire capability set. It is
strengthened to a strict save→export→import→load equality roundtrip with **every
defaultable field populated non-default**, plus the mandated anti-tautology proof
(mutate the exported payload to drop a field; assert refusal or strict
inequality). Consequently custody **does not block the fold on its own** — but
after the fold the slim namespace must be removed from the custody definitions
leaving no dangling namespace, and a capability that survives the deletion but not
the roundtrip is still a capability lost.

**D-T — The canonical writer must reach parity with the canonical model before
the fold.** `invoice_class`, `series`, `rectifies_invoice_number` and
`recargo_amount` exist on the model but have **no parameter** on
`build_catalogue_invoice` or `create_catalogue_invoice`, so every canonically
written invoice is `ORDINARIA` with no series and no recargo **by construction**,
and a **rectificativa is unrepresentable through any production path today**.
Folding onto the canonical aggregate does not even reach parity with what that
aggregate already claims to model until these land. This is a precondition of the
fold, not a nicety of D-E.

## Implementation

A high-level shape, not a plan; the executable ordering lives in
`2026-08-06-invoice-canonical-structure-plan`.

The work layers in five movements, and the ordering between the first and third
is the whole safety property.

**Conserve, then close the gaps.** A three-lane capability inventory of both
stores — income, business operations, purchase evidence — establishes what exists
and what replaces it, and doubles as the gate on deletion. In parallel the
canonical side closes the gaps the inventory names: `eu_iva_id` and the M349
party-identity preference that rides on it, the lifecycle timestamps, the four
writer parameters without which the canonical aggregate cannot express what its
own model declares, the removal of the observation direction default, and the
declared per-class fold rule for records the canonical model refuses. The
capability-parity proof closes this movement and decides whether the fold opens
at all.

**Make the surviving surface usable.** Additive work on the writer and the
confirm boundary: the regime and provenance options, the guided verb's missing
devengo input, multi-line synthesis at both sites that currently collapse it, and
the confirm-boundary override set widened from the reader's field set to the
writer's. None of this touches the resolver, so it runs alongside the first
movement.

**Fold, then delete, in that order.** The operator verbs are repointed at the
canonical store first, the lane-partition decision is recorded, the two-store
union is removed from the resolver, and only then do the model, services,
repository, namespace, payload schemas, locale leaves and the blessing test leave
the tree. Deleting before repointing would leave the operator with no CRUD
surface; deleting before the union is removed would leave a resolver reading a
store that is gone.

**Close the second-authority and vocabulary gaps.** These are independent of the
fold: the dead second writer is deleted rather than routed, the misleading
category token is renamed after settling whether a preflight site shares its
serialised key, the confirm-boundary plausibility gate lands, and the two
duplicate direction types over the canonical source-kind strings are retired
while `InvoiceKind` relocates to the domain it describes. Each relocation is one
atomic explicit-path commit with its consumers, fixtures, `__all__` updates and a
regenerated API scaffold.

**Close the screen blind spots.** The invoice-versus-ledger screen is extended
past its ES-only and cuota-only reach to cover non-domestic counterparties and
recargo, and an annual-modelo equivalent is added — after first answering whether
an invoice-only bucket can reach a filed annual return through the existing gap,
because a negative answer re-scopes that work rather than embarrassing it.

Cross-lane: a separate team owns the extraction draft's shape and its parsers,
mapping onto the canonical line type directly. The file they share with this work
is the evidence-draft module, and the ownership boundary inside it is recorded in
Considerations.

**D-U — The invoice decomposition contract must keep functioning through the
fold, and the fold routes a new population into it for the first time.**
`domain/invoices/_decomposition.py` is calc-facing and is a first-class row in
the capability inventory. It takes a **rich** `Invoice`; slim records have never
reached it. So the obligation is not merely "do not break it" — the fold hands it
a population that lacks what it reads.

**Grounded at HEAD, with three corrections to the characterisation this decision
was commissioned from.** The module declares `InvoiceComponents`,
`InvoiceDecomposition`, `InvoiceDecompositionPartition` and
`InvoiceDecompositionDefect` (`:74`), projecting
`total = base + cuota + recargo + suplido` and `cash = total − retención`
(`:295-311`). That much holds. The corrections:

1. **The consumer set is larger than one.** There are **two** production
   consumers, not just the renta ledger: `_renta_income_ledger.py:711` runs the
   **full** `is_grounded` check and refuses the invoice as sales evidence with a
   typed `SalesInvoiceEvidenceRefusal.UNGROUNDED_DECOMPOSITION`; and
   `application/invoices/_source_resolver.py:286` — the same module that performs
   the two-store union — runs it for **M349**, narrowed to
   `_M349_SELF_CONTRADICTION_DEFECTS` (`:224-228`).
2. **Decomposition does NOT partition on `recargo_amount`, `suplido_amount`,
   `retention_amount` or the line set.** It reads each with an `or Decimal("0")`
   default (`:294-297`), so a record lacking them decomposes cleanly on those
   axes. The concern that an ex-slim record would decompose into a different
   *shape* than a natively-rich one on those fields is **refuted**.
3. **Decomposition computes the totals identity; it does not validate it.** The
   identity is enforced at `Invoice` construction, so a non-reconciling slim
   record never becomes an `Invoice` at all. That hazard belongs to the fold rule
   (D-A/A-i), not to decomposition.

**The real hazard is narrower and lands on exactly one lane.** The defect gate
returns early on `iva_category is None`, yielding
`IVA_TREATMENT_UNDECLARED` (`:341-344`), and **the slim record cannot hold an
`iva_category` at all**. So every ex-slim record folded without an explicitly
supplied category decomposes as ungrounded. Where that lands:

- **M347 — harmless.** Deliberately not checked; the module records why, that
  M347's declared figure is the total contraprestación under RD 1065/2007 art. 34,
  which no IVA category conditions, and that running the contract there would drop
  real above-threshold operations out of an informativa on an unrelated missing
  field.
- **M349 — harmless.** Absence is deliberately excluded from the disqualifying
  set, on a measured reason: `IntracomOperationType.S` and `I` map to no
  `IvaCategory` member, so treating absence as disqualifying would drop an entire
  lawful operation class out of the recapitulativa.
- **Renta income — NOT harmless.** The full `is_grounded` check applies, so an
  ex-slim issued invoice, correctly linked to its transaction, would be refused as
  sales evidence. This is a genuine capability change on the **income** lane, one
  of the three the conservation law names.

Mitigating, and worth stating because it changes the severity: that refusal is
**typed and surfaced**, not silent — `UNGROUNDED_DECOMPOSITION` is an explicit
refusal reason, and the partition deliberately carries its excluded half so a
consumer cannot drop a record invisibly (`:249-266`). So the feared "silent move
from aggregated to excluded" does not occur on this surface. It is a visible
capability change, which still blocks the fold for that record class until
decided.

**A stale justification found while grounding this, on this campaign's own
surface.** `_m349_incoherent_verdict`'s docstring (`_source_resolver.py:271-280`)
justifies excluding an absent `iva_category` from the M349 disqualifying set on
the *measured* ground that intra-community **services** map to no `IvaCategory`
member, "because the enum names goods, acquisitions and triangulation but not
services." That is false at HEAD: `INTRA_COMMUNITY_SERVICE_SUPPLY` and
`INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE` exist
(`domain/iva/_schema.py`), added by `7502ee65ed` — *"represent intra-community
services, which no category could express"* — on the same day the docstring still
asserted they could not be expressed.

The guard may still be correct; its **reason** is not, and a filing-path guard
resting on a premise the tree refutes is a live hazard rather than a wart. It
already propagated: a peer campaign read that docstring, treated the enum gap as
real, and was about to record an out-of-scope warning telling future readers not
to "fix" a gap that no longer exists. Re-decided by a Step, with both outcomes
open — correct the reasoning and keep the behaviour, or change the behaviour with
its filed-output consequence surfaced. Now that services *are* expressible, an
absent category on a services invoice is a gap in the **record**, not in the
**enum**, which changes the remedy.

**Also settled here: the evidence path cannot ground at all today.**
`confirm_invoice_draft_from_evidence` has no `iva_category` parameter, so every
invoice minted through the evidence path decomposes ungrounded by construction
and the renta sales-evidence path refuses all of them. This is not a future risk
from folding; it is the current state, and it is the sharpest instance of D-U's
point that decomposition depends on a field the upstream surface cannot supply.
D-L's widening of the override set (which already includes `iva_category`) is
what closes the receiving half; the producing half — mapping a structured
document's own tax-category code onto the enum — belongs to the peer lane, which
owns the parsers.

**What this decision requires.** Decomposition is a capability-inventory row with
its two consumers and the modelos each serves. The capability-parity proof gains a
**decomposition-parity** half: an ex-slim record and a natively-rich record
carrying identical economic facts must decompose to identical components and the
same partition side. And the per-class fold rule (D-A/A-i) is extended to state,
per class, what decomposition does with it afterwards. If a class cannot be made
to decompose equivalently, that is a legitimate reason to **stage or defer the
fold for that class** under D-R.

## Rationale

The decision reduces to one observation: the reason for keeping two stores was
that they served different layers, and they no longer do. Once both feed the same
calculation, the second store contributes nothing that the first cannot express
and contributes two correctness defects the first does not have. Deletion is
cheaper than reconciliation, and reconciliation would in any case require
inventing an id correspondence between two deliberately disjoint hash spaces.

The writer-surface work (D-E, D-G) is bundled rather than deferred because
canonicalisation without it produces one store an operator still cannot express a
retención, a regime, or a mixed-rate invoice in — which is the state that made the
second store look attractive in the first place.

D-I is bundled because it is the highest filing-consequence item on this surface
and shares its subject matter. It is severable — it touches neither store's shape
and could be lifted into its own campaign without disturbing D-A through D-H —
but severable means **liftable into a named successor campaign, not droppable**.
The source sweep ranked it first and asked that it be acted on first; an earlier
version of the plan ranked it last with no Steps and no verification criterion,
which is how a top-ranked finding disappears without anyone deciding to drop it.

One question inside D-I is genuinely unanswered and must be settled before its
priority is final: *whether an invoice-only bucket can reach a filed M390 through
the screen gap*. The source sweep flagged that if it can, it outranks everything
else on this surface. D-I asserts the fix without that answer, so the plan makes
answering it a Step that precedes the M390 screen work, and a negative answer
legitimately re-scopes that work rather than embarrassing it.

## Consequences

- **One store, so the double-count cannot recur.** Closed structurally rather
  than by a guard that a later refactor could bypass.
- **The M349 clave asymmetry resolves in the permissive direction**, so invoices
  currently dropped for want of an `operation_type` begin to be declared. This is
  a *change in filed output* for any affected bucket and must be surfaced, not
  landed quietly.
- **The M347 threshold interaction changes for any bucket that held duplicates.**
  Totals will fall. This is a correction, and it will look like a regression to
  anyone comparing against a prior filing.
- **The operator input contract narrows, visibly.** `aeat app ledger invoice add`
  today accepts an invoice with an empty counterparty name, no country code, no
  line items, and a `total_amount` inconsistent with base plus IVA. Once the noun
  collapses onto the canonical aggregate, **all four are refused.** This is the
  cost the corrected superset Consideration exposes, and it is recorded here
  rather than discovered by an operator. It is a *desirable* narrowing — the
  weaker surface currently sits behind the more discoverable verb — but it is a
  behaviour change on the entry path and the refusals must be instructive,
  naming the missing invariant and the accepted form rather than surfacing a
  bare validation error.
- **A migration is not required and must not be written.** Pre-release, no
  released data (`no-legacy-compatibility`). Any slim-store records in a
  developer bucket are discarded with the store. Note that this is true of
  *stored data* and says nothing about the input contract above — the two were
  conflated in an earlier draft.
- **The fold must synthesise a line, and single-line synthesis is itself being
  changed.** A slim record has no line set, so folding it into the canonical
  shape requires synthesising one — which is exactly the mechanism D-G is
  rewriting. The two decisions are about the same code and must be settled
  together, not independently.
- **The prior ADR's warning is honoured, not overridden.** It asked that a future
  agent not unify the stores *by mistake*. This unifies them on stated evidence,
  with the premise change named.
- **Sequencing risk is real.** Two campaigns are live on this surface and one has
  bound itself not to alter the `Invoice` model. Landing D-A before those settle
  would collide.

## Dependencies

The document-ingestion and inference path is under active decision: it may be
extracted from the `cadrumo` base package into an optional local-inference
extension emitting a validated artefact the CLI consumes. **This ADR does not
decide that architecture**, and two of its decisions are framed to survive either
outcome — D-E and D-F as assertion-authority questions rather than
where-extraction-runs questions, and D-K as a core-boundary gate independent of
the producer.

If the extension split is accepted, what needs revisiting is narrow: the reader
half of D-G (per-rate extraction), and the regex-versus-vision extraction fork,
which is recorded in the research as a duplication finding with **no resolution
prescribed here**. Everything else — D-A through D-D, D-H through D-K — is
store-and-writer work that does not touch the seam.

## Deliberately out of scope

Named so they are not lost to silence.

**An honesty note on this section.** A fresh-context review found that an earlier
version of this list was a short list that omitted the inconvenient items: three
source findings were lost to exactly the silence the heading forbids — the
jurisdiction axis (`source_jurisdiction`, absent from both invoice models), the
recargo loss on the extraction draft, and the real confirm-boundary override-set
question, the last two being items the source agents jointly agreed and
explicitly sequenced first. All three are now dispositioned: the first at D-N as
a reasoned deferral, the second at D-M and the third at D-L as decisions. The
list below is what remains genuinely out of scope.

- **The jurisdiction axis on invoice records.** `source_jurisdiction` is required
  on `Transaction` and mandatory for IRNR and art. 93 impatriado, and exists on
  neither invoice model. Deferred with its reason at D-N; it belongs with the
  same campaign that owns T2 below.

- **The transport and consent posture for document reading** — which documents
  may be read off-host, and for whom. Higher consequence than anything in this
  ADR, but a privacy decision, not a duplication one. It needs its own ADR.
- **The model and licence facade** — default model licensing, model selection,
  hardware floors. Separate campaign, measurement in progress.
- **The regex-versus-vision extraction fork** — a stated duplication finding whose
  resolution depends on the pending ingestion decision.
- **Merging `PurchaseInvoiceEvidence` into the canonical aggregate.** It is a
  document record, not an invoice record, and nothing in the evidence indicates
  it is duplicative. Explicitly not proposed.
- **T2, lane derived from bank-money direction.**
  `_invoice_kind_for` (`application/aggregation/_iva_ledger.py:1518-1547`) derives
  the repercutido/soportado split from `TransactionDirection`, which is wrong for
  a refund, a rectificativa, a reverse-charge acquisition, and a netted
  settlement. It is a real defect and it is *not* a duplication defect; folding it
  into a canonicalisation campaign would widen the blast radius across the whole
  IVA ledger path for no structural gain. Recorded for its own campaign.

## Codification candidates

None. The governing rules already exist (`no-legacy-compatibility`,
`composition-service-no-parallel-write-path`,
`single-subject-mutation-is-idempotent-guarded`,
`no-silent-under-declaration`) and this ADR is an application of them rather than
a source of new ones. Codification is retired by operator directive in any case.

## Open questions this record does not settle

Three of the four questions an earlier draft left open are now settled, and are
recorded here as closed rather than deleted so the record of what was open is
preserved.

- **CLOSED — whether `_importing.py` is deleted or routed.** Deleted; see D-H. The
  fact that settles it (a routed bulk importer already exists) was determinable
  from code the earlier pass did not read.
- **CLOSED — whether the lane partition is reproduced or dropped.** Neither is
  pre-decided here, but it is no longer *open*: it is assigned to a Step in the
  plan's fold phase that must record the decision and enumerate what each
  surviving per-consumer gate still guarantees. The ADR's requirement that this be
  "a stated decision, not an oversight" is now enforced by a Step rather than by
  hope.
- **CLOSED — whether D-I is executed here or lifted into its own campaign.**
  Executed here, in its own phase, with its own Steps and its own verification
  criteria. Severable means liftable into a named successor campaign, not
  droppable. The source sweep ranked it the highest-consequence finding it
  carried; a phase with no Steps ranked it last and ungated, which is how a
  top-priority finding disappears.
- **STILL OPEN, and it is the one that decides the campaign — whether the fold is
  ready at all.** D-R makes the capability-parity proof the deciding instrument
  and this record does not pre-judge its result. If the inventory turns up a
  capability with no canonical replacement, or the parity proof cannot be written,
  the correct outcome is a staged or deferred fold with the missing pieces named.
  That is a success condition of this ADR, not a failure of it.
- **STILL OPEN — how this sequences against the two in-flight campaigns.**
  `2026-08-06-llm-invoice-read-reconciliation-adr` binds itself not to alter the
  `Invoice` domain model, and D-O alters it. That is a genuine collision requiring
  coordination, not a technical question this record can answer alone.
