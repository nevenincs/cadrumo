---
tags:
  - '#adr'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:d7bbe998def789d9ec9e49e2baa3246a8a3260666fa2c13426029ce9f98c95b3'
related:
  - "[[2026-08-06-invoice-canonical-structure-research]]"
  - "[[2026-06-10-ledger-invoice-unification-adr]]"
  - "[[2026-08-05-ledger-invoice-decomposition-adr]]"
---
# `invoice-canonical-structure` adr: `One canonical invoice aggregate; delete the slim store`

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
   `test_catalogue_invoice_link_flow.py:136-160` creates one invoice in both
   stores and asserts only that the ids differ. It never aggregates the pair. The
   suite is green over the exact configuration that double-counts.

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

- **The two records are not substitutable, so this is a fold, not a pick.**
  Everything the slim record expresses, the rich record also expresses; the
  converse is false (`_business_operation_invoice.py:171-196` versus
  `domain/invoices/_models.py:474-505`). Applying the substitutability
  pre-filter, the rich aggregate's constraint shape is a superset. There is no
  symmetric choice to agonise over.
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
- **A peer campaign constrains sequencing.**
  `2026-08-06-llm-invoice-read-reconciliation-adr` (proposed) binds itself to
  "must not alter the `Invoice` domain model", and the working tree carries live
  changes under `.vault/exec/2026-08-05-ledger-invoice-decomposition/`. This work
  must sequence around concurrent edits rather than assume a quiet tree.

## Constraints

- The canonical aggregate MUST remain the encrypted bucket-scoped secure object
  it is today; no plaintext sidecar, no parallel write path
  (`composition-service-no-parallel-write-path`).
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

**D-B — The operator noun collapses to one CRUD surface over the canonical
aggregate.** `aeat app ledger invoice {add,view,list,update,remove}` and
`aeat app ledger invoice catalogue {create,wizard,...}` become one set of verbs
over one store. The `catalogue` sub-noun disappears, since there is no longer a
second thing for it to distinguish. `--kind issued|received` is retained as the
prior ADR established it.

**D-C — Before any deletion, the slim store's declarable coverage is proven
reproducible on the canonical path.** Specifically the M347 per-party totals and
the M349 operator rows. The clave asymmetry is resolved in the canonical
direction: the `iva_category` fallback that `_intracommunity_clave` already
carries is the behaviour that survives.

**D-D — The double-count is closed by construction, not by a guard.** Once one
store exists there is nothing to reconcile. No cross-store dedup is built,
because building one would institutionalise the split this ADR removes. The
blessing test `test_catalogue_invoice_link_flow.py:136-160` is retired with the
store it describes.

**D-E — The writer surface is extended to reach the canonical model's fields.**
`create_catalogue_invoice` and the CLI entry verbs gain retención
(`--retention-rate` / `--retention-amount`), `--recargo`, an explicit
`--iva-category`, `--invoice-class`, `--series`, and `--operation-date` on every
entry verb including the guided one. This is the D2 decision from the joint
scope, and it is stated as an assertion-authority question: **these are facts the
operator may assert, independent of whether any extraction pass can read them.**

**D-F — Retención is not added to the extraction draft.** A received invoice's
retención is a fact about the taxpayer's own retenedor obligation, not a header
field an extraction pass may assert. Recorded as a decision, with its reason, so
it is not later added as an apparent omission. This is D3, and it is orthogonal
to D-E rather than in tension with it: D-F governs who may assert, D-E governs
where the operator supplies. Both hold at once.

**D-G — Mixed-rate invoices are fixed at the writer end within this campaign.**
`build_catalogue_invoice` (`application/invoices/_creation.py:113-137`) stops
synthesising exactly one line and accepts a supplied line set. No persisted-schema
change is authorised or needed: `_require_lines`
(`domain/invoices/_models.py:605-610`) already bounds only the empty case and the
M303 comparison path already iterates lines
(`application/aggregation/_modelo_bindings.py:1093-1105`). The reader half is out
of scope; see Dependencies.

**D-H — `application/invoices/_importing.py` is routed through the canonical
writer or deleted.** It is a second `Invoice` writer with weaker invariants — no
FX stamp, no rate-slot closure, and it silently skips a duplicate identity
(`:111-113`) where the canonical path raises. It is reachable from no CLI verb.
Which of the two dispositions applies is an open question this ADR does not
settle; what it settles is that both writers may not persist.

**D-I — The M303 invoice screen's blind spots are closed, and M390 gains an
equivalent.** The screen (`_modelo_bindings.py:1005-1069`) is extended past its
`counterparty_country == "ES"` filter (`:1113-1123`) and its four-cuota screened
set (`:144-149`) to cover recargo, and an M390-scoped equivalent is added. The
`modelo-390-cuota-devengada-total-equals-reconciliacion-303` blocking rule cannot
substitute: both of its sides derive from the same ledger, so consistent
under-population passes it trivially. That rule is an internal
transport-consistency check and is left as one.

**D-J — `InvoiceLine.category_id` is renamed.** It is an untyped `str | None`
(`domain/invoices/_models.py:397`) that reads as the deduction taxonomy and is
not (`SpendingCategory`, `domain/categories/_spending_category.py:15-64`, lives on
`Transaction`). Renamed to state what it is; no type change is authorised here.

**D-K — A plausibility gate is added at the confirm boundary.**
`confirm_invoice_draft_from_evidence` (`application/ledger/_evidence_draft.py:702-718`)
gains a check that a document being confirmed as ISSUED was plausibly issued by
this taxpayer, mirroring the hard gate that already refuses an ISSUED invoice as
purchase evidence (`_evidence_reference.py:175-180`). The gate belongs to the core
boundary where a validated artefact arrives, whoever produced it.

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
and shares its subject matter, but it is severable: it touches neither store's
shape and could be lifted into its own campaign without disturbing D-A through
D-H.

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
- **A migration is not required and must not be written.** Pre-release, no
  released data (`no-legacy-compatibility`). Any slim-store records in a
  developer bucket are discarded with the store.
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

Named so they are not lost to silence:

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

- Whether the slim store's physical lane partition is reproduced in the canonical
  home or consciously dropped in favour of the six existing per-consumer gates.
- Whether `_importing.py` is deleted or routed (D-H settles that both may not
  persist, not which).
- How this sequences against the two in-flight campaigns.
- Whether D-I is executed here or lifted into its own campaign.
