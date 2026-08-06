---
tags:
  - '#research'
  - '#invoice-canonical-structure'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:e53f9969a0072e9ac4a52ec1c22a6fa18c6cb447318c7af0abc08f474769940a'
related:
  - "[[2026-06-10-ledger-invoice-unification-adr]]"
---
# `invoice-canonical-structure` research: `Two invoice aggregates, one operator noun: canonicalisation scope`

Two records model one concept. The rich `Invoice`
(`src/cadrumo/domain/invoices/_models.py:469`) and the slim
`BusinessOperationInvoice`
(`src/cadrumo/application/ledger/_business_operation_invoice.py:154`) both
represent a business invoice, both are reachable from one operator noun
(`aeat app ledger invoice` and `aeat app ledger invoice catalogue`,
mounted together at `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:86-87`),
and — the fact that reframes the question — **both now feed the same Modelo 347
and Modelo 349 calculations through one resolver that unions them without
reconciling them** (`src/cadrumo/application/invoices/_source_resolver.py:200-202`).

This matters because an accepted ADR deliberately kept the split and warned
against merging it. That ADR's premise no longer describes the code. This
research establishes what changed, what the split now costs, and what an ADR
must settle; it records no decision.

Scope note: this document covers the store-and-writer surface. The
document-ingestion and inference path is under separate active decision (see
"Dependencies and exclusions") and its architecture is deliberately not
addressed here.

## Findings

### The accepted ADR's factual premise was falsified 18 days after it landed

`2026-06-10-ledger-invoice-unification-adr` (accepted) collapsed two CLI
noun-groups into one `invoice --kind`, and explicitly kept both aggregates. Its
stated architecture: "The unified command drives the **slim**
`BusinessOperationInvoice` — the operator-CRUD record. The **rich** `Invoice`
remains the calculation aggregate consumed by modelo aggregation." It called
merging them "out of scope and rejected", and recorded the two-store split as a
documented sharp edge so "a future agent does not 'unify' them by mistake".

That premise — slim is not a calculation input — held when written. Commit
`432fc96d29` (2026-06-28, "fix(modelo): feed m349 from business invoices")
introduced `_load_business_operation_invoices`
(`src/cadrumo/application/invoices/_source_resolver.py:552-570`) and the slim
observation adapter (`:579-610`), putting the slim store into the calculation
mesh 18 days later. The resolver's own module docstring now states both paths
converge in it (`:6-8`, `:13-18`).

Two readings are available and the ADR must choose between them: the commit
silently overturned an accepted decision, or the decision was always narrower
than its prose (it rejected merging as *out of scope for that campaign*, not on
the merits). The wording supports the second reading; the effect is the same
either way.

### Neither store's duplicate guard can see the other

Each store refuses duplicates within itself. The rich catalogue refuses a
re-create with the same derived identity
(`src/cadrumo/application/invoices/_creation.py:256, 284-285`). The slim store
disambiguates genuinely distinct same-content invoices
(`src/cadrumo/application/ledger/_business_operation_invoice.py:294`).

No guard spans them. `_load_business_operation_invoices` performs no dedup; its
`rich_invoice_repository` parameter is consulted only as a storage-degradation
fallback (`_source_resolver.py:567-570`). The union at `:200-202` concatenates
observations from both stores.

Dedup by identity is not merely absent but structurally impossible: the two id
derivations hash different tuples. `derive_invoice_id` folds
`(kind, invoice_number, issued_at, counterparty_tax_id, currency, grand_total)`
(`src/cadrumo/domain/invoices/_models.py:85-124`);
`derive_business_operation_invoice_id` folds a different tuple including
`source_kind` (`src/cadrumo/application/ledger/_business_operation_invoice.py:269-301`).
No correspondence exists between the two id spaces.

The consequence is two-sided and both sides are reachable by ordinary operator
behaviour, because the two entry verbs sit under one noun with near-identical
option sets:

- Record only in the slim store: the invoice reaches M347/M349 but not M369, not
  the retención store, and carries no `linked_transaction_ids` for
  reconciliation. Under-declaration, no advisory.
- Record in both: M347 and M349 count it twice. Over-declaration, no advisory,
  no guard.

The over-declaration side is the more dangerous, because it produces a
valid-looking filing and every gate on this surface watches the under-declaration
direction.

Adversarial verification returned CONFIRMED, and established two facts worse than
the code reading alone suggested.

First, the M349 duplicate is invisible. `_build_operator_clave_rows`
(`src/cadrumo/domain/calculations/registry/_invoice_bindings.py:822-859`) groups
by `(country_code, party_tax_id, clave)` with no `invoice_id` in the key, and
accumulates `bucket.base_total += observation.base_amount` (`:844`). Two
observations of one real invoice therefore do not produce two visible rows — they
produce **one row with a doubled importe**, indistinguishable from a genuinely
larger operation. On the M347 side, `_m347_declarable_party_ids` (`:557-563`)
sums per `party_tax_id` with no identity check, so the duplicate inflates the
annual total and can push a counterparty across the EUR 3,005.06 declaration
threshold that should not have been crossed.

Second, a test already performs the duplicating action and blesses it.
`src/cadrumo/entrypoints/cli/tests/test_catalogue_invoice_link_flow.py:136-160`
(`test_catalogue_create_id_differs_from_slim_invoice_add_id`) creates the same
invoice — same NIF, number, date, base — through both `invoice add` and
`invoice catalogue create`, and asserts only that the two ids differ. It never
runs the pair through `resolve()` or any binding computation. The module
docstring states "The two stores stay distinct" (`:8`). The hazardous state is
constructed, asserted upon, and never aggregated, so the suite is green over the
exact configuration that double-counts.

No test anywhere asserts additivity or non-additivity across the two stores for
one invoice. `test_source_resolver.py` exercises both repositories in one
resolver (`:237, 299, 359, 433, 493`) but every fixture puts a given invoice in
one store only.

### The two records are not substitutable, so canonicalisation is a fold, not a pick

The slim record carries no `iva_category`, no retención, no `recargo_amount`,
no `suplido_amount`, no `lines`, no `linked_transaction_ids`, no
`payment_status`, no `invoice_class`, no `operation_date`
(field list at `_business_operation_invoice.py:171-196`). The rich record
carries all of them (`_models.py:474-505`).

Everything the slim record can express, the rich record can also express. The
converse is false. Applying the substitutability pre-filter, the rich aggregate's
constraint shape is a superset, so it is the only viable canonical home; the
question an ADR must settle is not which one wins but what the fold costs and
what must be deleted rather than bridged.

Two properties are held only by the slim store and would have to be reproduced
or consciously dropped: physical partition of the two lanes into separate
documents keyed by `source_kind`
(`_business_operation_invoice.py:390-391`, services pinned at `:714, :720`), and
the flat operator-edit shape the CLI writes directly. The rich catalogue is a
single mixed-kind container (`src/cadrumo/domain/invoices/_service.py:100-118`)
whose lane discipline is enforced per-consumer at six sites
(`_models.py:856, :934`; `src/cadrumo/application/ledger/_evidence_reference.py:175`;
`src/cadrumo/application/aggregation/_renta_ledger.py:742`;
`src/cadrumo/application/aggregation/_renta_income_ledger.py:697`;
`src/cadrumo/application/aggregation/_oss_ioss.py:325`).

### The writer surface cannot supply facts the canonical model can hold

Independent of the fold, the rich aggregate's fields are largely unreachable from
single-invoice entry. `create_catalogue_invoice`
(`src/cadrumo/application/invoices/_creation.py:217-236`) accepts no retención
parameter; the only write path to `Invoice.retention_rate` /
`retention_amount` in the tree is the bulk importer
(`src/cadrumo/application/invoices/_importing.py:57-58`). `catalogue create`
(`_ledger_business_invoice_cli.py:562-576`) and `catalogue wizard` (`:638-651`)
expose no `--retention-rate`, `--retention-amount`, `--recargo`,
`--iva-category`, `--invoice-class`, or `--series`; `wizard` additionally omits
`--operation-date`, so an invoice entered through the guided path can only reach
the proxy devengo rank that commit `0b1e3f040b` was written to distinguish from a
declared one.

`iva_category` is derivable only from `--operation-type`, through a five-member
intracom map (`_ledger_business_invoice_cli.py:125-145`). Domestic reverse
charge, export, import, recargo de equivalencia, exempt and not-subject are
therefore unreachable. The in-code comment at `:129-134` records that this same
hole was found and closed once already for the service claves — the shape
recurs for every non-intracom regime.

Mixed-rate invoices collapse at two independent points: the extraction schema
carries a single scalar rate
(`src/cadrumo/application/ledger/_evidence_draft.py:235-236`) and
`build_catalogue_invoice` synthesises exactly one line unconditionally
(`src/cadrumo/application/invoices/_creation.py:113-137`, docstring `:116-119`).
The persisted model is not the constraint: `_require_lines`
(`src/cadrumo/domain/invoices/_models.py:605-610`) bounds only the empty case,
and the M303 comparison path already iterates lines
(`src/cadrumo/application/aggregation/_modelo_bindings.py:1093-1105`). This is a
two-end fix requiring no schema change.

### The M303 invoice screen is sound in design and narrow in reach

`_raise_if_m303_invoice_domestic_iva_would_be_silent`
(`src/cadrumo/application/aggregation/_modelo_bindings.py:1005-1069`) refuses an
M303 calculation when catalogue-invoice domestic IVA would exceed the
transaction-ledger IVA the filing is about to use, with an instructive
suggestion. It fails closed rather than under-declaring, and it screens both
directions of the repercutido/soportado axis — unusual and correct.

Its reach is narrower than the exposure, on four axes, all verified.

It requires `counterparty_country == "ES"` (`:1113-1123`), so intracomunitaria,
import and export invoices never enter the comparison set. It is the only
`_raise_if_*` refusal in the module and no intracom/import/export counterpart
exists.

Its screened set is four cuota bindings (`:144-149`), and recargo is dropped
before the comparison even runs: `invoice_line_to_iva_observation`
(`src/cadrumo/domain/iva/_invoice_classification.py:221-245`) takes no recargo
parameter, so `InvoiceLine.recargo_amount` never reaches the guard. Catalogue
invoices never bind to M303 casillas at all — that is by design, they are
evidence, not a binding source — but the consequence is that a recargo
discrepancy between invoice and ledger passes silently where the analogous cuota
discrepancy raises.

It early-returns for every modelo but M303 (`:1029`), and no M390 equivalent
exists anywhere in the tree.

**The M390 blocking rule cannot substitute for one, and this is structural
rather than incidental.** `modelo-390-cuota-devengada-total-equals-reconciliacion-303`
(`src/cadrumo/_data/registry/aeat/modelos/390/revisions/2010-y-siguientes/verification_expectations/0002-verification_predicates.toml:6-9`)
equates two quantities that derive from the same source. Its left side,
`iva.anual.cuota-devengada-total`, is re-aggregated for the whole year straight
from the transaction ledger via `ledger_iva_aggregation`
(`.../bindings/0001-bindings.toml:1-4, 13-16, 25-28`). Its right side,
`iva.anual.reconciliacion.devengada-303`, folds the four already-filed M303
quarters, each of which was itself computed from that same ledger. If the ledger
is under-populated because invoices were never linked into it, both sides are
wrong by the identical amount and `equals(...)` passes trivially. The rule is an
internal transport-consistency check — does M390's ledger read match what was
filed — not a check against invoice evidence or any external truth. The formula's
own comment (`.../formulas/0001-formulas.toml:14-24`) narrates exactly this
symmetry requirement from the historical recargo case.

Nor does any advisory close the gap on the calculate path. The capability to ask
"which invoices are linked to nothing" exists as an on-demand query
(`src/cadrumo/application/invoices/_queries.py:68-74`, `find_unmatched`) and as a
link-consistency warning on `ledger check`
(`src/cadrumo/entrypoints/cli/_ledger_read_cli.py:392-422`, which flags broken
links, not absent ones). Neither is wired into `calculate` or `verify`. The
`unrouted_observation` diagnostic (`_modelo_bindings.py:242-256`) covers ledger
observations no binding reads — the opposite direction from invoice evidence that
never reached the ledger.

### A second, weaker writer of the canonical aggregate exists off the entrypoint graph

`src/cadrumo/application/invoices/_importing.py` writes `Invoice` records without
going through `create_catalogue_invoice`: `parse_invoice_payload` (`:74`)
constructs via a direct `Invoice.model_validate` (`:91`) and
`import_invoices_from_path` (`:124`) persists directly (`:151`). It carries
weaker invariants than the canonical writer on three axes — no FX stamping
(`_creation.py:197` is not called, so caller-supplied totals are trusted), no
IVA-rate-slot closure, and it *silently skips* a duplicate identity
(`merge_invoice_import`, `:111-113`) where the canonical path *raises*
(`_creation.py:284-287`). Opposite failure semantics on the same condition.

It is exported from the package facade but reachable from no CLI verb; the only
callers are tests. Neither writer's constraint shape is a superset of the other,
so this is a genuine second authority with drift risk rather than a legitimate
specialisation.

### The slim clave resolver silently under-declares where the rich one does not

`_intracommunity_clave` (`_source_resolver.py:436`) resolves an M349 clave from
`operation_type` or, when that is absent, falls back to `iva_category`
(`:445-463`). `_business_invoice_clave` (`:663`) has no such fallback: absent
`operation_type`, it returns `None` and `_business_invoice_observation` (`:588-590`)
drops the invoice entirely.

A slim invoice whose IVA category implies an intracommunity clave but which
carries no explicit `operation_type` is therefore **not declared on M349 at
all**, where the equivalent rich invoice would be. This is an under-declaration
arising from the parallel implementation itself, independent of the double-count.
Whether the slim record can even hold an `iva_category` is settled — it cannot
(field list at `_business_operation_invoice.py:171-196`) — which means the
asymmetry is not closable within the slim shape.

### Two unrelated concepts share the name "category"

`InvoiceLine.category_id` is an untyped `str | None`
(`src/cadrumo/domain/invoices/_models.py:397`). The deduction taxonomy is
`SpendingCategory`, a 42-member closed enum
(`src/cadrumo/domain/categories/_spending_category.py:15-64`) with a
proportionality rule per member
(`src/cadrumo/domain/categories/_proportionality.py:170-176`), and it lives on
`Transaction`, not on any invoice. A reader encountering "category" on an
invoice line will reasonably take it for the deduction taxonomy.

Semantic discovery surfaced a third site using the same token with the enum
meaning: `src/cadrumo/application/ledger/_preflight.py:304-320` documents its
`category_id` as a `SpendingCategory`. So the token carries at least two
distinct meanings across the invoice and ledger surfaces.

### Lane is derived from bank-money direction rather than declared intent

`_invoice_kind_for(direction: TransactionDirection)`
(`src/cadrumo/application/aggregation/_iva_ledger.py:1518-1547`) maps
`INCOMING → ISSUED` and `OUTGOING → RECEIVED`, and the repercutido/soportado
split follows from it (`:1230-1234`). This is coherent for a paid domestic
invoice and incorrect for a refund or abono, a rectificativa, a reverse-charge
acquisition where no money moves in the IVA direction, and a netted settlement.

The rich `Invoice` carries `kind` as a declared, required fact whose value is
folded into the record's identity (`_models.py:115-124, :476`). The two
authorities can disagree, and nothing reconciles them.

### Purchase evidence can be confirmed as ISSUED without a plausibility check

`confirm_invoice_draft_from_evidence`
(`src/cadrumo/application/ledger/_evidence_draft.py:702-718`) takes `kind` as a
required argument and mints a catalogue invoice in either direction. The
docstring is explicit that extraction cannot infer it (`:741-742`). The reverse
gate is hard and tested — an ISSUED catalogue invoice is refused as purchase
evidence (`src/cadrumo/application/ledger/_evidence_reference.py:175-180`, write
gate at `src/cadrumo/application/ledger/_actions_common.py:521-527`) — but no
equivalent check asks whether a document being confirmed as ISSUED was plausibly
issued by this taxpayer.

On reflection this ranks lower than initially assessed: `kind` is explicit and
required, and the resulting record must satisfy every ISSUED construction
invariant. It is a missing symmetric check rather than a live path to a wrong
figure.

### Issuer status is an advisory approximation, not the lane authority

There is no issuer-status entity. The lane axis is `InvoiceKind`
(`src/cadrumo/domain/iva/_classification.py:102-119`). The one place RD
1619/2012's issuance obligation is modelled is
`src/cadrumo/application/invoices/_issuer_establishment.py`, whose
`issuer_established_in_tai` (`:86`, body `:103`) approximates TAI establishment
from IRPF residency, is deliberately over-strict (`:43-66`), and is declared
advisory weight, never a refusal (`:133-140`). The Canarias / Ceuta-Melilla
limitation is pinned by test (`tests/test_issuer_establishment.py:160`).

The lane separation an operator experiences as stringent comes from elsewhere:
structural partition in the slim store, identity-folding in the rich one, and
the six per-consumer kind gates listed above.

### The decision corpus does not protect the split, and one proposed record defers exactly this question

A full sweep of `.vault/adr/` (semantic plus filesystem enumeration, because the
vault index was stalled) establishes the governing position.

`2026-06-10-ledger-invoice-unification-adr` is **still accepted and has never
been superseded or amended** — its own `supersedes:` frontmatter is empty of any
inbound claim, and no other record names it as superseded. A new decision must
therefore supersede it explicitly on the survival point, the same way it
superseded its own predecessor.

No accepted ADR protects the slim store's M347/M349 sourcing. That wiring is an
implementation of the very taxonomy lock the 2026-06-10 ADR established, executed
under `2026-05-20-calculation-source-connectivity-adr`, and commit `432fc96d29`
has no governing vault record of its own.
`2026-07-04-counterpart-source-provider-adr` explicitly reserves
`LEDGER_TRANSACTION` and `PURCHASE_INVOICE_EVIDENCE` and does *not* own
`payable_invoice` / `collectible_invoice`, leaving them invoice-resolver-owned.
So the blast radius of removing the slim store is real but ADR-uncovered: it
falls under the same ruling being reconsidered.

`2026-08-05-ledger-invoice-decomposition-adr` (**proposed**, not accepted)
restates "rich and slim invoice aggregates both survive" as settled, and then
declines to rule on: *"Whether the slim `BusinessOperationInvoice` gains
retención fields, or issuing professionals are directed to the rich `Invoice` — a
product-surface choice between two accepted aggregates."* That is precisely the
question a canonicalisation decision answers. It must be cited and reconciled,
not bypassed.

Two hygiene observations. The dedicated duplication audits
(`2026-07-25-code-dedup-sweep-rag-inventory-audit`,
`2026-06-13-semantic-dedup-epic-audit`) do not flag this pair at all — a negative
finding worth recording, since it shows the split survived two sweeps aimed at
exactly this class. And
`2026-05-12-cli-workflow-redesign-invoice-domain-decoupling-adr`, cited by name
in the 2026-06-10 supersession clause, does not exist as a file; its content
lives in the ledger-transaction-management ADR and the apex rollup.

### A peer campaign is live on this surface

`2026-08-05-ledger-invoice-decomposition` and
`2026-08-06-llm-invoice-read-reconciliation` are both in flight, the latter
constraining itself to "must not alter the `Invoice` domain model". The working
tree carries uncommitted and staged changes under
`.vault/exec/2026-08-05-ledger-invoice-decomposition/`. Any canonicalisation
sequencing must assume concurrent edits to the same files rather than a quiet
tree.

## Dependencies and exclusions

**Under active decision elsewhere — deliberately not addressed.** The
document-ingestion and inference path may be extracted from the `cadrumo` base
package into an optional local-inference extension producing a validated
artefact the CLI consumes. Two items in this research sit on that seam and are
framed to survive either outcome: the confirm-boundary override set is stated as
a question of *who may assert a fact* (operator versus extraction pass) rather
than of where extraction runs, and the plausibility gate for confirm-as-ISSUED
belongs to the core boundary where a validated artefact arrives, whoever produced
it. The regex-versus-vision extraction fork is recorded as a duplication finding
with no resolution proposed.

If the extension split is accepted, the items needing revisit are narrow: the
reader half of the line-items question, and the extraction fork. The
store-and-writer findings — the two aggregates, the M303/M390 screen reach, the
writer-surface gaps, the category-token collision, the direction-derivation
conflict — do not touch the seam.

**Excluded, needing their own decisions.** The transport and consent posture for
document reading (which documents may be read off-host, and for whom) is a
higher-consequence question than anything here, but it is a privacy decision, not
a duplication one. The model and licence facade — default model licensing, model
selection, hardware floors — is a separate campaign with measurement still in
progress. Neither is addressed here and neither should be read as resolved by
silence.

## Open questions

- Whether the slim store's physical lane partition must be reproduced in the
  canonical home or can be consciously dropped in favour of the existing
  per-consumer gates. Not investigated.
- Whether `application/invoices/_importing.py` is dead code to delete or an
  intended bulk-JSON feature to bring up to the canonical invariant set. Its
  owner is unidentified; the answer changes whether it is a deletion or a
  routing change.
- Whether any bucket in practice holds the same invoice in both stores.
  Answerable only against real profile data; not attempted, and arguably not
  worth attempting, since the hazard is a property of the code rather than of
  any particular bucket.
- How canonicalisation sequences against the two in-flight campaigns on this
  surface, one of which constrains itself not to alter the `Invoice` model.
- Whether the M347 threshold interaction has already produced a wrong filing in
  any real profile. Not investigated; would require profile data.

Resolved during this pass and recorded above rather than left open: the
double-count (confirmed), the M390 equivalent (absent, and the blocking rule
structurally cannot substitute), and the governing record for commit
`432fc96d29` (none exists).

## Sources

Verification was performed against HEAD `0b1e3f040b`. Semantic discovery used
`vaultspec-rag` across four parallel adversarial sweeps (double-count
verification, duplication-cluster discovery, M303/M390 screen reach, and the
decision-corpus sweep), each pairing semantic queries with targeted `rg` or
direct-read confirmation.

Instrument caveat, recorded because several findings above are absence claims.
During this pass the service reported a shrunken code index (79141 of 79169
published sections, integrity verdict `shrunken`) and a stalled vault-index job,
and warned in its own words that "an absent result is not evidence that no such
code exists". Every absence claim above is therefore backed by targeted `rg` or
by filesystem enumeration rather than by semantic recall alone: the
no-M390-equivalent finding by a tree-wide `def _raise_if` grep, the
no-cross-store-dedup finding by direct read of the union and loader, and the
decision-corpus findings by enumerating `.vault/adr/` rather than trusting the
stalled vault index. Absence claims not so backed were moved to open questions.

The earlier claim that the slim store "reaches nothing" — reasoned from registry
TOML without tracing the resolver that produces its values — was falsified during
this pass and is corrected above. It is recorded here because it is the same
failure mode the index warning describes, and because the corrected reading is
materially worse than the original.

- `src/cadrumo/domain/invoices/_models.py:85-124, 397, 469, 474-505, 605-610, 856, 934`
- `src/cadrumo/domain/invoices/_service.py:100-118`
- `src/cadrumo/application/ledger/_business_operation_invoice.py:154, 171-196, 269-301, 294, 390-391, 714, 720`
- `src/cadrumo/application/invoices/_source_resolver.py:6-18, 200-202, 552-570, 567-570, 579-610`
- `src/cadrumo/application/invoices/_creation.py:113-137, 217-236, 256, 284-285`
- `src/cadrumo/application/invoices/_importing.py:57-58`
- `src/cadrumo/application/invoices/_issuer_establishment.py:43-66, 86, 103, 133-140`
- `src/cadrumo/application/ledger/_evidence_draft.py:235-236, 702-718, 741-742`
- `src/cadrumo/application/ledger/_evidence_reference.py:175-180`
- `src/cadrumo/application/ledger/_actions_common.py:521-527`
- `src/cadrumo/application/ledger/_preflight.py:304-320`
- `src/cadrumo/application/aggregation/_modelo_bindings.py:144-149, 1005-1069, 1093-1105, 1113-1123`
- `src/cadrumo/application/aggregation/_iva_ledger.py:1230-1234, 1518-1547`
- `src/cadrumo/application/aggregation/_renta_ledger.py:742`
- `src/cadrumo/application/aggregation/_renta_income_ledger.py:697`
- `src/cadrumo/application/aggregation/_oss_ioss.py:325`
- `src/cadrumo/domain/iva/_classification.py:102-119`
- `src/cadrumo/domain/categories/_spending_category.py:15-64`
- `src/cadrumo/domain/categories/_proportionality.py:170-176`
- `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py:86-87, 125-145, 562-576, 638-651`
- Commits `432fc96d29` (2026-06-28), `0b1e3f040b` (2026-08-06), `84f84166f` (referenced as an incident shape only)
