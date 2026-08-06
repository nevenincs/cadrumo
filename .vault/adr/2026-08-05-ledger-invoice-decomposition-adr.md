---
tags:
  - '#adr'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:9b2e11097a7ff9782065fb37dd6a63eb238c1692c44ee86363b51a7e30a0ef42'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-reference]]"
  - '[[2026-08-05-ledger-invoice-decomposition-research]]'
---
# `ledger-invoice-decomposition` adr: `Invoice decomposition and income grounding` | (**status:** `proposed`)

## Problem Statement

Two coupled hardening sites, escalated deliberately by the operator, need one coherent
ruling. Grounding: `2026-08-05-ledger-invoice-decomposition-reference` (claims there
marked MEASURED/REASONED; each verified twice).

**Site 1 — ledger ingestion.** The income pipeline gross-folds bank-credited cash into
the income casilla when no invoice substrate is recorded, and the error changes
direction with the invoice: a rated invoice over-declares (cash ≈ 1.06 × base at 21%
IVA / 15% retención), an IVA-exempt professional service under-declares 15% of base and
simultaneously drops the offsetting retenciones credit. The expense side deliberately
refuses exactly this gross-fold (`MISSING_TAXABLE_BASE`); the income side has no
equivalent issue reason. The operator's position, ruled on here: a partial invoice
declaration is ambiguous and must be excluded from calculations, but must NOT disappear
silently — advisories must ride both the ledger surface and the calculation engine.

**Site 2 — calculation backend.** How a single invoice decomposes into base, IVA
repercutido, retención and total as a function of invoice type and operation territory
— including currency normalisation — and how domestic, intracomunitaria and
foreign/overseas categories change WHICH components exist and how each feeds the tax
calculation.

Two pending findings are folded in rather than left loose: **F26** (the renta-income
selector `fact` defaults to the legally-weaker measure) and **F27** (income-side
missing-substrate advisory, keeping the fallback).

## Considerations

- The defect chain, the selector-default exposure, the legal grounding for the income
  measure, and the coverage state are established in
  `2026-08-05-ledger-invoice-decomposition-reference` and are not re-argued here.
- MEASURED (this record, 2026-08-05, live BOE cross-check the reference called for): the
  previously non-bundled accounting step of the IVA-exclusion chain is confirmed against
  live consolidated BOE text of RD 1514/2007 (PGC, BOE-A-2007-19884). NRV 12.ª: "El IVA
  repercutido no formará parte del ingreso derivado de las operaciones gravadas por
  dicho impuesto". NRV 14.ª: "Los impuestos que gravan las operaciones de venta de
  bienes y prestación de servicios que la empresa debe repercutir a terceros como el
  impuesto sobre el valor añadido y los impuestos especiales, así como las cantidades
  recibidas por cuenta de terceros, no formarán parte de los ingresos." The reference's
  REASONED IVA-exclusion claim is thereby upgraded: LIRPF art. 27 / art. 28.1 → IS rules
  → resultado contable → PGC NRV 12.ª/14.ª. These PGC excerpts are NOT yet in the
  bundled corpus; bundling them is an implementation obligation before any registry
  `legal_refs` cites them.
- MEASURED (live BOE, same pass): RD 439/2007 (RIRPF) art. 95.1 — professional
  retención is "15 por ciento sobre los ingresos íntegros satisfechos", 7 por ciento in
  the inicio-de-actividad window; the retención base is the ingresos íntegros, not the
  IVA-inclusive total. Art. 110.3.a — retenciones practicadas are deducted from the
  pago fraccionado for professional activities in estimación directa, confirming
  casilla 01 income must be pre-retención or the retención counts twice.
- MEASURED: the renta-family fact `gross_income_sum` appears in NO committed registry
  binding; the registry's only `gross_income_sum` selector is Modelo 210's
  (`modelos/210/revisions/2025/bindings/0001-bindings.toml`), whose observations sum
  the DECLARED `M210IncomeClassification.gross_income_amount`, not raw cash — the name
  is accurate there and misleading only in the renta and impatriado families, which sum
  `abs(raw.amount)`. One stale comment in the M130 cumulative-income fragment names
  "the gross_income_sum path" and must ride any rename.
- MEASURED: the `taxable_base_sum` fact coerces a missing base to zero
  (`observation.taxable_base_amount or Decimal("0")`,
  `domain/calculations/registry/_ledger_bindings.py`), and M130 casilla 01 carries two
  committed `taxable_base_sum` bindings — a second, distinct silent under-declaration
  surface inside an already-committed binding.
- MEASURED: the withheld-amount inference requires BOTH `taxable_base` and `iva_amount`
  non-None, so a declared-exempt invoice (legitimately cuota-less) can never recover
  its retención through inference as coded.
- MEASURED: the payer-side retención flow already has a canonical authority — the
  `retenciones_aggregation` binding family
  (`domain/calculations/registry/_retenciones_bindings.py`) materialises scalars from
  a dedicated per-perceptor retención store into committed Modelo 111 bindings
  (schemes `rendimientos_trabajo`, `actividades_economicas`,
  `actividades_profesionales`, `premios`, …). Retención on a RECEIVED invoice is a
  liability of the taxpayer-as-retenedor and belongs to that store's authority; this
  record must route into it, never fork a second retención path.
- Accepted decisions this record must compose with, not contradict:
  `2026-05-27-source-jurisdiction-axis-adr` (M100/M130 never filter on jurisdiction;
  per-modelo scope filters live downstream), `2026-07-01-modelo-151-beckham-source-scope-adr`
  (per-family classifiers are the accepted duplication cost; ES-gated),
  `2026-07-10-m210-irnr-phase-2-engine-adr` (declared classification only, no inference
  from generic categories; a bound value has one writer),
  `2026-06-09-modelo-iva-routing-carry-adr` (advisories fire only on cuota-bearing
  categories, consumed as the named frozenset), `2026-06-04-llm-ledger-classification-adr`
  (LLM selects, system derives; no numeric tax field may be LLM-emitted; IRPF/retención
  category grounding deferred to its own decision), `2026-04-17-invoice-catalogue-adr`
  (invoice-level totals exact, `derive_invoice_id` input set fixed, reconciliation
  suggest-only), `2026-06-10-ledger-invoice-unification-adr` (rich and slim invoice
  aggregates both survive; locked source-kind strings), `2026-07-21-ledger-fx-conversion-adr`
  (one FX acquisition path, refusal over approximation),
  `2026-06-19-silent-zero-base-aggregation-adr` (an untagged expense is surfaced rather
  than gross-folded; a regulated base casilla aggregates from a grounded mechanism or
  is deferred by ADR, never silently zero).
- Project rules bearing directly: no-silent-under-declaration (and its mirror: the
  reference records that over-declaration harms the taxpayer and nothing watches that
  direction today), cli-notices-are-the-only-diagnostic-channel,
  aeat-schema-central-config, aeat-calculation-grounding,
  no-tautological-calculation-tests, aeat-safety-legal-gates (the app never files),
  binding-source-kind-single-taxonomy, no-legacy-compatibility (pre-beta: rename by
  deletion, no alias).
- A clean bank import with no invoice records is a plausible, common operator state;
  the gross-fold is only dangerous in known-direction cases (exempt services). Severity
  must weigh operator ergonomics against the exempt-services hazard.

## Considered options

**Site 1 — grounding contract and outcome classes**

1. Status quo: keep the silent gross-fold. Rejected — it is the defect; the expense
   side already refuses it, so the asymmetry is also incoherent.
2. Exclude every substrate-less income row from aggregation (full mirror of the gasto
   `MISSING_TAXABLE_BASE` exclusion). Rejected — income and expense are not symmetric:
   dropping untagged income silently UNDER-declares by the whole row, which is worse
   than mis-measuring it, and it would punish the common clean-bank-import state.
   (This is also the F27 keep-the-fallback ruling.)
3. **Chosen:** a third outcome class — *declarable-but-ungrounded* — alongside eligible
   and excluded-with-issue. Bank rows lacking substrate stay IN the sum via the
   existing per-observation fallback but are flagged, on both the ledger preflight
   surface and the calculate path's typed notice channel. Partial invoice RECORDS
   (an `Invoice`/`BusinessOperationInvoice` failing its decomposition contract) are
   excluded from enrichment and calculation but surfaced — excluded-but-visible, per
   the operator's position.
4. Severity blocking-at-verify for every ungrounded row. Rejected as the default —
   it makes the common state unfileable; kept as the targeted escalation for the
   known-direction hazard (see Implementation, D3).

**Site 2 — decomposition model**

1. Per-category fact taxonomy replacing the per-family one. Rejected — the accepted
   per-family module shape (`2026-07-01-modelo-151-beckham-source-scope-adr`,
   `2026-07-10-m210-irnr-phase-2-engine-adr`) encodes SCOPE (which modelo a measure
   feeds, under which legal regime); the IVA category encodes which COMPONENTS exist.
   Collapsing the two axes into one taxonomy would re-couple regulatory-distinct
   bindings the corpus deliberately separated.
2. Free-form per-resolver component logic (status quo, grown case by case). Rejected —
   scattered inline knowledge of which categories carry a cuota is exactly what the
   named frozensets were created to end.
3. **Chosen:** a two-axis model, with the component axis keyed by the PAIR
   (`IvaCategory`, invoice kind). Axis A (declared data in `domain/iva` beside the
   existing named frozensets): a component-expectation table stating, per category AND
   kind (issued/collectible — money received — versus received/payable — money paid),
   whether cuota is required/forbidden, who declares it, whether recargo may exist,
   and whether retención is expected/possible/not-expected and in WHICH ROLE (credit
   of the taxpayer on issued invoices; liability of the taxpayer-as-retenedor on
   received ones), each row carrying `legal_refs`. Axis B (per-family, unchanged
   shape): each ledger family's observation builder and fact vocabulary consumes
   Axis A when decomposing a row for its modelo.

**Retención derivation**

1. Always require declared retención. Rejected — the existing bounded inference
   (invoice gross minus cash, capped by the registry max rate) is measured, correct
   when substrate exists, and matches how the paper trail actually looks.
2. Derive base from cash by inverting an assumed rate (base = cash / (1 − r)).
   Rejected outright — selecting r (15% vs 7% vs sectoral rates) is a per-row legal
   fact the system cannot infer; inventing it is fabricated legal behaviour.
3. **Chosen:** declared-first, bounded-inference-second, inversion-never. Inference
   precondition is relaxed from "base AND iva_amount both present" to "base present
   AND cuota determinable from the declared category" (zero for the cuota-less set,
   rate-derived otherwise), so declared-exempt invoices recover their retención.

## Constraints

- The eight LIVA articles the routing-carry ADR names (arts. 7, 13, 15, 17, 20, 22,
  25, 26) are still absent from the legal catalogue/corpus; any Axis-A row grounding
  export, intra-community or import treatment is gated on bundling them
  (`legal-grounding-verifies-bundled-authoritative-corpus`). The PGC NRV 12.ª/14.ª
  excerpts verified live in this record are likewise not yet bundled.
- Registry values (retención rates 15%/7%, IVA rates, component expectations) land in
  the registry/central config with `legal_refs`, never as feature-module literals.
- The LLM boundary is structural: no schema may let a model emit `retencion_rate`,
  `retencion_amount`, `taxable_base` or `iva_amount`
  (`2026-06-04-llm-ledger-classification-adr`).
- A registry-bound value has one writer; the advisory channel reports, it never
  mutates values (`composition-service-no-parallel-write-path`,
  `2026-07-10-m210-irnr-phase-2-engine-adr`).
- The pull path and calculate path share one aggregation
  (`one-aggregation-path-pull-equals-calculate`): the third outcome class and its
  advisory must surface identically on both.
- Gate ordering inside the income classifier is pinned by
  `2026-07-05-ledger-latency-budget-adr`; the new substrate check must slot after the
  existing cheap gates, not reorder them.
- The rich `Invoice` totals discipline (line tolerance 0.01, invoice-level exact) and
  the fixed `derive_invoice_id` input set must not be silently altered: retención
  stays OUTSIDE `grand_total` because it is a settlement-side deduction, not a price
  component. AMENDED 2026-08-06 (D10): the identity is
  `grand_total == base_total + iva_total + recargo_amount`. The earlier restatement
  omitting the recargo term was not a simplification but a defect — it refused the
  truthful invoice of a supplier selling to a comerciante minorista and accepted the
  falsified one, so the model selected for wrong data. Recargo is a price component
  under LIVA art. 161 and sits INSIDE the total, on the opposite side from retención.
- `IrpfCategory`/retención-type closed-enum authoring was explicitly deferred to its
  own decision by `2026-06-04-llm-ledger-classification-adr`; this record does not
  pre-empt it (see Consequences — operator questions).
- The severity escalation (D3) must not create a filing deadlock for taxpayers whose
  ledger genuinely has no invoice-level substrate; the escalation is scoped to
  declared-category rows only, where the operator has already asserted the treatment.

## Implementation

High-level shape; the named change list an implementation plan must cover.

**D1 — minimum calculation-grounded shape (Site 1).** An actividad-económica income
row is *calculation-grounded* iff it declares: (a) an IVA treatment — an `IvaCategory`
other than `UNKNOWN`/`ERRONEOUS_INVOICE`; (b) `taxable_base`, EUR-native or carrying a
resolved FX pair; (c) a cuota consistent with (a): explicit `iva_amount` for rated
categories, structurally zero for members of the cuota-less set; and (d) retención
substrate — a declared withheld amount, or the D5 inference precondition satisfied, or
the Axis-A expectation "not-expected" for the row's category. The ambiguity boundary
is the CATEGORY axis, not the amounts: a base with `iva_amount` zero and category
`DOMESTIC_EXEMPT` is grounded exempt income; the same amounts with no category are
ambiguous (untagged vs exempt are indistinguishable) and the row is ungrounded.
Counterparty residency/tax identity remains an invoice-record concern, not a row
grounding requirement. This grounding contract is deliberately income-side (issued
invoices / money received): the received side already has its grounding refusal (the
gasto `MISSING_TAXABLE_BASE` exclusion, `2026-06-19-silent-zero-base-aggregation-adr`)
and this record aligns with it rather than restating it; what D4 adds for the
received side is the component matrix (IVA soportado role, retenedor liability), not
a new eligibility gate.

**D2 — third outcome class and dual advisory (Site 1, rules F27 ACCEPTED).** Add a
*declarable-but-ungrounded* class to the income pipeline. Ungrounded bank rows keep
contributing through the existing `ingresos_integros_sum` per-observation fallback —
the fallback is KEPT; removing it would silently drop untagged income entirely — but
each such row emits a typed missing-substrate signal: a new income-side issue/advisory
reason (the long-missing mirror of the gasto `MISSING_TAXABLE_BASE`), surfaced (i) on
the ledger preflight surface and (ii) on the calculate path as a non-blocking notice
through the envelope notice channel, with transaction ids and the count/sum of
cash-fallback contributions in `Notice.context`. The observation model grows an
explicit grounding marker (substrate-declared vs cash-fallback) so the advisory, the
evidence bundle, and tests key on a fact, not on field-nullness heuristics. Partial
invoice RECORDS failing their decomposition contract are excluded from
enrichment/aggregation and surfaced through the same channel (excluded-but-visible).
Additionally `taxable_base_sum` stops coercing a missing base to zero: a base-less row
in a `taxable_base_sum` window joins the ungrounded class and the advisory instead of
silently contributing nothing.

**D3 — severity (RECOMMENDATION; operator ratifies).** Default severity is ADVISORY at
calculate/draft/export: filing on cash-derived income stays possible after a visible
notice, because a clean bank import with no invoice records is a plausible common
state. Escalate to BLOCKING at verify only for the known-direction hazard: a row whose
declared category is cuota-less/exempt AND that lacks `taxable_base` — there the
under-declaration direction is certain, the magnitude is unquantifiable without
substrate, and the operator has already engaged with the row (a category was
declared), so demanding the base is proportionate. Undeclared-category rows never
block. Trade-off stated: this leaves the silent-under-declaration window open for the
exempt freelancer who never tags anything — that residual risk is exactly what the
always-on advisory exists to surface, and closing it fully would make the common
state unfileable.

**D4 — decomposition identity and the (category, kind) component matrix (Site 2).**
Canonical per-invoice identity, valid for BOTH kinds with roles inverted:
`total (contraprestación) = taxable_base + cuota IVA [+ recargo]`;
`cash = total − retención`. Retención is not a price component and never enters
`grand_total`. Component existence is Axis-A declared data keyed by the PAIR
(`IvaCategory`, kind) — a component-expectation table in `domain/iva` beside (and
derived from, where applicable) the existing named frozensets, each row with
`legal_refs`.

Kind semantics: an ISSUED (collectible) invoice means money is received — its base
feeds the income measure, its cuota is IVA repercutido/devengado, its retención is
withheld BY the payer and is the taxpayer's CREDIT (RIRPF art. 110.3.a on the pago
fraccionado; the retenciones casilla on M100/M130). A RECEIVED (payable) invoice
means money is paid — its base feeds the gasto measure, its cuota is IVA soportado
(deducible per M303 rules, or cost per PGC NRV 12.ª when non-deducible), and when the
supplier is a resident professional the taxpayer is the obligated RETENEDOR: the
retención is a LIABILITY settled to AEAT, whose canonical home is the existing
per-perceptor retención store feeding the `retenciones_aggregation` family
(M111/M190 committed bindings) — this record routes into that authority and forbids
a second parallel retención path.

Per-category rows (each stated for both kinds where they differ): domestic rated
categories carry base + cuota (+ optional retención for professional services, in
the role the kind dictates); `DOMESTIC_EXEMPT` (LIVA art. 20) carries base, no
cuota, retención possible in either role; `INTRA_COMMUNITY_SUPPLY` (art. 25, issued
side) and the export categories (arts. 21/22) carry base only, zero cuota —
cuota-less is NOT substrate-less, their bases still feed base-only casillas — with
retención not-expected (REASONED: the withholding obligation falls on
Spanish-resident payers and permanent establishments; a foreign payer without PE is
generally outside it — to be confirmed against LIRPF art. 99 / RIRPF art. 76 when
the corpus entries land); reverse-charge and intra-community-acquisition categories
invert who declares: on the received side the taxpayer self-assesses the cuota (both
devengada and, where deducible, soportada), on the issued side (LIVA art. 84.Uno.2.º
supplies) the invoice carries base only; `IMPORT_THIRD_COUNTRY` (received side)
carries base with cuota settled at customs. Operation origin/target is expressed BY
the (category, kind) pair plus the invoice record's counterparty country — no
separate territory axis is invented. Selecting the category for a cross-border
service is governed by the place-of-supply rules (LIVA arts. 68–70); that selection
is a declared judgement (operator, or LLM-selection under the closed-list guard),
NEVER derived by the system from counterparty country alone.

**D5 — retención (Site 2).** Declared-first: an invoice or row that knows its
retención declares amount (and optionally rate), and a DECLARED amount or rate is
accepted even when nonstandard — real-world retención rates are not a closed set the
system may enforce (sector schemes, reduced rates, contractual and IRNR/convenio
cases exist); the registry catalogue is an expectation, not a straitjacket. When a
declared rate diverges from the registry expectation for the row's declared scheme,
the engine surfaces a non-blocking divergence advisory — never a silent correction,
never a block. Derivable-second: the existing bounded inference (invoice gross minus
cash, capped by the registry maximum supported rate) remains the only derivation,
with its precondition relaxed per Considered options so cuota-less categories
qualify; derived values carry derivation provenance. Inversion-never: no path may
reconstruct base from cash by assuming a retención rate. The registry retención
catalogue is authored from RIRPF Título VII with `legal_refs` per scheme — the
professional 15% / inicio-de-actividad 7% pair is live-verified (2026-08-05, RD
439/2007 art. 95.1); further schemes (trabajo, arrendamientos, capital, agrícolas,
premios — the scheme axis the retenciones store already names) are authored with the
same discipline, each figure live-checked at authoring time; the IRNR 24%/19% family
stays governed by the M210 ADRs. Rates are never feature-module literals and never
LLM-emitted. IVA rates continue to resolve through the existing registry rate lookup
(`2026-06-04-llm-ledger-classification-adr`). CORRECTED 2026-08-05 (coordinator
measurement at HEAD): the rich-invoice `IvaRate` enum and the registry rate table
ALREADY AGREE exactly — both declare {0, 4, 10, 21} for the served window
(registry ES coverage starts 2024-01-01), and the transient 2022-2024 5% rate is
INTENTIONALLY absent from both sides per the enum's own docstring, to be added only
in sync with a registry rate entry if pre-2025 ingestion ever lands. The ruling is
therefore a PARITY GATE only (enum members ≡ registry-declared rate set for the
served window, drift in either direction fails loudly), NOT a new member; adding
`RATE_5` unilaterally would create a member the registry cannot resolve. Whether the
registry's pre-2024 rate coverage window should be extended for historic ingestion
is an operator scope question (see Consequences), not an enum reconciliation.

**D6 — territory and the income measure (Site 2).** The per-family fact vocabularies
stay (resident M100/M130 unfiltered per the source-jurisdiction axis; M151 ES-gated;
M210 declared-classification-only). Territory changes which FAMILY a row can feed and,
via the category, which COMPONENTS exist — it does not change the resident income
measure. The renta income measure for casilla 01/0171 remains ingresos íntegros:
IVA-exclusive (PGC NRV 12.ª/14.ª chain, now live-verified) and pre-retención (RIRPF
art. 110.3.a).

**D7 — currency.** All components of one invoice normalise through the single ECB FX
path with one rate/date pair (`2026-07-21-ledger-fx-conversion-adr`); a row or invoice
whose conversion cannot be resolved is refused from grounding (existing predicate),
never approximated, and joins the visible-exclusion surface.

**D8 — F26 ACCEPTED, extended.** Remove the `fact` default from the renta ledger
income selector so the field is required and an omitting binding fails registry
validation loudly; zero behaviour change (all six committed bindings are explicit —
MEASURED in the reference). Extend the same requiredness to the impatriado selector
(its default is the stronger measure, but a silent default on one sibling and not the
other re-creates the divergence F26 closes); the IRNR selector's single-member
Literal is structurally not a choice and is untouched. Additionally rename the
renta-family and impatriado-family fact `gross_income_sum` → `cash_received_sum`
(honest name for what it computes: `abs(raw.amount)`); MEASURED: no committed binding
uses it in either family, so the rename is a zero-registry-impact deletion-rename per
no-legacy-compatibility — sweeping the one stale M130 fragment comment — while
Modelo 210's accurately-named `gross_income_sum` (summing the declared classification
amount) is expressly out of scope.

**D9 — canonical IVA rate mechanism (operator-raised, ruled 2026-08-05).** IVA rates
are law-per-window DATA, never code constants: they depend on the item's tier, the
member state, and the governing law effective at the operation date (transient
windows exist — the 2022-2024 5% and 0% measures are the standing example). The
canonical mechanism ALREADY EXISTS and is hereby ratified as the sole one
(MEASURED): the date-windowed registry rate table (`registry/aeat/iva/rates.toml`;
rows keyed member_state + kind + pct + effective window, each row carrying
`legal_refs` — LIVA art. 90 for general, art. 91 for the reduced tiers) → typed
`load_iva_rate_table()` → the single `lookup_rate(member_state, kind, on_date)`
authority, resolved at the operation's devengo date. Rates derive from BOE-published
law per window, authored into the registry with live-verified figures per
`registry-calculation-legal-grounding`; a transient rate is a new WINDOWED ROW citing
the RDL/ley that set it — never an edit to a constant, never a feature-module
literal. Two-level model, made explicit: the TIER KIND (`IvaRateKind` — general /
reduced / super-reduced / zero, plus the exempt/not-subject treatment markers) is
the stable legal concept and stays a closed enum; the PERCENTAGE is time-varying
registry data and must never be a hardcoded axis. Consequences for invoice records
(rich, slim, AND the expense-invoice evidence records alike): the declared substrate
converges on tier kind + operation date, with the numeric percentage
registry-resolved at that date; a declared numeric that does not equal the resolved
one is an error state under D1/D2 — IVA rates, unlike retención rates, ARE closed by
law per window, so divergence means a wrong kind, a wrong date, or an erroneous
invoice, and the row joins the excluded-but-visible surface for operator resolution,
never silent acceptance and never silent correction. The rich-invoice numeric
`IvaRate` enum is accordingly a transitional projection of the served window: it
MUST NOT grow hardcoded members (the parity gate of item 12 holds it in lockstep
with the registry), and its retirement in favour of kind + resolved percentage is
plan-level work gated on operator question 5 (coverage window). Out of scope,
stated honestly: the ITEM-to-tier assignment (which goods and services sit in which
tier per window — the LIVA art. 91 lists and the transient RDLs that move items
between tiers) remains a declared category-selection judgement (operator, or
LLM-selection under the closed-list guard); authoring per-window item lists as a
registry axis would be its own decision with its own corpus ingest.

**D10 — the devengo date is the operation date, and it is a recorded fact (ruled
2026-08-06).** Every period attribution — which quarter a cuota is declared in, which
filing year an annual reconciliation sees — resolves on the LIVA art. 75 devengo date.
That date is when the operation occurred: for entregas de bienes "cuando tenga lugar su
puesta a disposición del adquirente", for prestaciones de servicios "cuando se presten,
ejecuten o efectúen las operaciones gravadas" (bundled corpus, read verbatim; AEAT
concurs). The invoice date appears nowhere in art. 75.Uno. Art. 75.Dos moves devengo to
collection for pagos anticipados, "por los importes efectivamente percibidos", excluding
art. 25 entregas.

Three consequences bind implementation:

*No derivable proxy is authoritative.* A B2B invoice may be issued up to the fifteenth of
the following month while still being declarable in the earlier period, so the issue date
is wrong at exactly the month and quarter boundaries where attribution changes. The bank
movement date is wrong for the general regime and right only for a prepayment. The devengo
date is therefore a RECORDED fact, never inferred. Where a fallback chain exists it MUST
declare which rank produced the date — operation-date-declared, issue-date-proxy,
movement-date-proxy — through the same grounding-marker discipline D2 established for the
income measure, so a proxy is never mistaken for the fact.

*The general regime is the regime that needs it.* Criterio de caja is the regime where
collection governs; the general regime is bound to the operation date. Gating the devengo
field on criterio de caja therefore withheld it from the only regime whose law requires
it. LANDED (commit `8a783e869e`): `operation_date` is recordable on any regime, still
required under criterio de caja, span-aware, and opt-in — a row without one keeps filing
on its movement date, so nothing already recorded changes quarter.

*Payment timing is not uniformly wrong.* A change making the operation date universally
authoritative would break art. 75.Dos. Pagos anticipados are not representable at all
today and are named work, not an assumption.

**D11 — the invoice is a legally-grounded canonical schema (ruled 2026-08-06).** The
record has been extended field by field as each defect surfaced, and the accumulated shape
now fails a class of cases rather than isolated ones: four separate findings are all "the
law describes a property of a Spanish invoice the record cannot hold". Piecemeal extension
is rejected; the invoice becomes one typed canonical schema whose field set is derived from
what the law requires an invoice to state, not from what consumers have so far needed.

Scope of the schema, each axis typed and none free-form: identity (number, series, issue
date, operation date where it differs per RD 1619/2012 art. 6.1.f, invoice class —
ordinaria, simplificada, rectificativa); directionality (issued/received, and the roles
that inverts per D4); counterparty (name, tax id, country, with the simplificada carve-out
that no tax id exists); the money identity in full —
`grand_total == base_total + iva_total + recargo_amount`, `cash == grand_total −
retention_amount`, plus the suplido term which joins total and cash while joining neither
base nor cuota (LIVA art. 78.Tres.3); per-line tier kind and operation date resolving the
percentage through `lookup_rate` per D9; retención rate and amount in the role the kind
dictates; the IVA category and its Axis-A components; FX; payment lifecycle; and the
amendment linkage a rectificativa needs to name what it corrects (LIVA art. 89).

Two constraints on the shape. It MUST remain a classifier-not-refusal boundary in the sense
D2 established: a partial invoice is a real document the taxpayer holds, so construction
keeps accepting it and the decomposition contract renders the verdict. And the identity
guards MUST refuse the FALSIFIED document rather than the truthful one — the recargo defect
is the worked example of getting that backwards, and every new term on the identity is to
be checked against that failure mode explicitly.

Corpus obligation, gating: RD 1619/2012 art. 6 (mandatory content) and art. 11 (issuance
deadline) are NOT bundled — only art. 2 is. The mandatory-content list is the authority
from which this schema's field set is derived, so bundling it precedes authoring the
schema, per `legal-grounding-verifies-bundled-authoritative-corpus`.

**Named change list for the implementation plan.**

1. Registry selectors: `fact` required (no default) on the renta and impatriado
   income selectors; registry-validation error message lists the accepted facts.
2. Fact rename `gross_income_sum` → `cash_received_sum` in the renta and impatriado
   families (code, docstrings, the stale M130 fragment comment, tests); M210 untouched.
3. Income pipeline: new missing-substrate issue/advisory reason; observation grounding
   marker (substrate-declared vs cash-fallback); preflight surface entry; calculate
   path notice with context; identical surfacing on pull and calculate.
4. `taxable_base_sum` stops or-zero coercion; base-less rows join the advisory.
5. Withheld inference precondition relaxed to category-determinable cuota; exempt
   invoices recover retención; existing max-rate bound retained; declared-vs-expected
   retención-rate divergence advisory (non-blocking, never a silent correction).
6. Axis-A component-expectation table in `domain/iva`, keyed by the
   (`IvaCategory`, invoice kind) pair, with `legal_refs`, derived from/beside the
   named frozensets (never a third inline set); retención role (credit vs
   retenedor-liability) declared per row.
7. Registry retención catalogue keyed by the existing retención scheme axis, authored
   from RIRPF Título VII with legal catalogue entries (art. 95 professional pair
   live-verified; every further figure live-checked at authoring time); corpus
   bundling: PGC NRV 12.ª/14.ª excerpts; LIVA arts. 7/13/15/17/20/22/25/26
   (Tier-2 gate of `2026-06-09-modelo-iva-routing-carry-adr`); LIVA arts. 68–70
   (place of supply) for the category-selection grounding; LIRPF art. 99 / RIRPF
   art. 76 for the retención-expectation grounding.
8. Invoice records: consistency validator for `retention_rate`/`retention_amount` on
   the rich `Invoice` (against `base_total`, retención outside `grand_total`, both
   restated deliberately); partial-invoice decomposition contract with
   excluded-but-visible surfacing; slim-invoice retención fields pending the operator
   question below.
9. Verify-stage escalation rule per D3 (behind operator ratification).
10. Tests: grounded against AEAT workbooks/manual worked examples and the bundled
    corpus (a worked example with retención and an exempt-services example are the
    two anchor cases); anti-tautology per no-tautological-calculation-tests; roundtrip
    coverage for every new persisted field per aeat-roundtrip-discipline.
11. Received-invoice retención routes into the existing per-perceptor retención store
    behind the `retenciones_aggregation` family (M111/M190); the linkage mechanism is
    plan-level design, the prohibition on a second retención path is not.
12. `IvaRate`-vs-registry parity GATE only (CORRECTED: the sets already agree at
    {0, 4, 10, 21}; the 5% "gap" premise was wrong — `RATE_5` stays deliberately
    absent until a registry rate entry for pre-2025 ingestion exists; no enum
    member is added and no pre-2024 rate history is backfilled under this item).
    LANDED: `test_rate_parity.py`, commit stamped P02.S19.
13. Per D9: converge invoice records (rich, slim, expense-evidence) on declaring
    tier kind + operation date with the percentage resolved via `lookup_rate` at
    devengo date; declared-numeric divergence joins the excluded-but-visible
    surface; retire the numeric `IvaRate` members once operator question 5
    (coverage window) is answered. Direction ruled here; convergence is
    plan-level.
14. Bundle RD 1619/2012 art. 6 and art. 11 into the corpus from BOE consolidated
    text (only art. 2 is bundled today). Art. 6 is the authority the D11 field set
    derives from, so this precedes schema authoring, not follows it.
15. Per D11: author the canonical invoice schema against art. 6's mandatory-content
    list — invoice class (ordinaria / simplificada / rectificativa), series, operation
    date, suplido term, amendment linkage for the rectificativa, and the simplificada
    carve-out on `counterparty_tax_id`. Every identity guard carries a test proving it
    refuses the FALSIFIED document and admits the truthful one, the recargo failure
    mode stated explicitly.
16. Per D10: thread the operation date from the invoice into period attribution with a
    declared rank marker (operation-declared / issue-proxy / movement-proxy), surfaced
    on both the pull and calculate paths per `one-aggregation-path-pull-equals-calculate`.
    A proxy-attributed row is visible, never silently equated with a declared one.
17. Per D10: represent pagos anticipados (LIVA art. 75.Dos) so a prepayment devengues on
    collection for the amount received, with the art. 25 exclusion honoured. Nothing in
    the tree expresses this today.
18. Cross-modelo multi-period acceptance tests: one accumulative invoice life driven
    through M303 and M390 and through M130 and M100 across several periods, asserting the
    same operation lands in one period on both the quarterly and annual sides; plus an
    adversarial suite of deliberately degraded invoices (missing base, missing cuota,
    recargo dropped from the total, retención netted into the total, operation date
    contradicting the issue date, rectificativa with no referent, simplificada above the
    threshold) each asserting the specific refusal or advisory rather than merely that
    something failed.

## Rationale

- **Included-but-flagged for bank rows, excluded-but-visible for invoice records** is
  the only combination that honours both halves of the operator's position at once:
  ambiguous partial declarations do not feed calculations (the invoice record is the
  declaration; a bare bank row declares nothing beyond its cash), and nothing
  disappears silently. Full exclusion of bank rows would convert a mis-measurement
  into a total omission — a strictly worse silent under-declaration, which is why F27
  keeps the fallback.
- **The category axis as the ambiguity boundary** is the knockout for Site 1: amounts
  cannot distinguish exempt from untagged (both show base with no IVA), but a declared
  `DOMESTIC_EXEMPT` versus an absent category is exactly that distinction, already
  typed, already closed, and already grounded per member. No new axis is invented.
- **Two axes rather than one taxonomy** wins Site 2 because the corpus has already
  decided both halves separately: per-family modules encode regulatory scope (three
  accepted ADRs), and the named cuota-less frozensets encode per-category component
  law. The gap was never a missing taxonomy — it was that component knowledge is not
  yet declared data with `legal_refs`. Axis A fills precisely that gap.
- **Declared-first retención with bounded inference** follows the measured reality:
  the existing gross-minus-cash inference is correct and capped when substrate exists;
  the failure was its precondition (requiring a cuota that legally does not exist for
  exempt services), not its mechanism. Rate inversion is rejected on
  aeat-safety-legal-gates grounds: it manufactures a per-row legal fact.
- **D3's targeted escalation** puts the blocking cost exactly where the danger is
  measured to be (the reference's exempt-services case: 15%-of-base silent
  under-declaration) and where the operator has already engaged with the row, while
  the common clean-import state files with a visible advisory. The advisory also
  closes, for this surface, the unwatched over-declaration direction the reference
  flags: the same notice fires whichever direction the cash-fallback error runs.
- **F26 with the rename** is accepted because a required field plus an honest name
  removes both halves of the prospective exposure: no binding can silently inherit the
  weakest measure, and no author can mistake cash for gross income. Both are
  zero-behaviour-change today (MEASURED), which is the cheapest moment to land them.

## Consequences

- GAINS: the income side stops being the outlier — every declarable-but-ungrounded
  euro is visible on both operator surfaces; the exempt-services silent
  under-declaration acquires a targeted gate; the over-declaring rated-invoice
  fallback acquires its first watcher; component existence per category becomes
  auditable registry-grounded data; retención handling gains a legal anchor
  (live-verified rates) and loses its exempt-services blind spot; two latent
  silent-zero surfaces (`taxable_base_sum` or-zero, selector default) close with zero
  behaviour change today.
- DIFFICULTIES: corpus bundling is the long pole — eight LIVA articles, the PGC
  excerpts, and the retención-obligation articles gate the full Axis-A grounding;
  until they land, Axis-A rows for intra-community/export/import treatment carry
  provisional grounding and must say so. The advisory must be tuned to fire once per
  aggregation with aggregate context, not once per row, or it will train operators to
  ignore it (the routing-carry ADR's crying-wolf lesson).
- PATHWAYS: the Axis-A table is the natural home for future OSS decomposition and for
  the recargo supplier-side flow the silent-zero ADR scoped out; the grounding marker
  on observations gives the evidence bundle a per-row substrate story exports can
  render.
- PITFALLS: do not let the third outcome class leak into the gasto pipeline's
  semantics — the expense-side exclusion is deliberate and correct (no silent
  over-declaration of gastos) and has an anti-normalisation control; do not re-derive
  a local cuota-less set anywhere (consume the named frozensets); do not let the
  verify escalation fire on undeclared-category rows; do not fork a second retención
  write path — the per-perceptor store behind `retenciones_aggregation` is the sole
  home for retenedor-side liabilities; do not enforce the registry retención
  catalogue as a closed set against declared values — declared wins, divergence is
  an advisory; do not derive an IVA category from counterparty country alone —
  place-of-supply selection is a declared judgement.
- **Operator questions this record declines to rule on**, each because it is a product
  or legal-authority judgement rather than an architecture one:
  1. RATIFY OR AMEND D3's severity split (advisory default; verify-blocking only for
     declared-cuota-less rows without base). Architecture supports either severity;
     the filing-ergonomics-versus-hazard weighting is the operator's.
  2. Whether the slim `BusinessOperationInvoice` gains retención fields, or issuing
     professionals are directed to the rich `Invoice` — a product-surface choice
     between two accepted aggregates (`2026-06-10-ledger-invoice-unification-adr`).
  3. Whether to author the deferred `IrpfCategory`/retención-type closed enum now.
     The registry rate parameters (D5) need only a minimal
     professional/inicio-de-actividad axis; the full enum grounding was deferred to
     its own decision by `2026-06-04-llm-ledger-classification-adr` and remains so.
  4. The foreign-payer no-retención expectation (D4): the live RIRPF art. 76 text
     (retrieved 2026-08-05) confirms the "not-expected" default with two
     load-bearing carve-outs — non-residents WITH permanent establishment are
     obligados a retener, and non-residents without PE are obligated for
     rendimientos del trabajo and certain TRLIRNR art. 24.2 deductible-expense
     income. The carve-outs are recorded as a `scope_note` (a default is not a
     prohibition); the operator confirms whether counter-cases among their
     counterparties warrant "possible" rather than "not-expected" for the
     intra-community/export categories.
  5. Registry IVA-rate coverage window: ES rate rows start 2024-01-01, so a
     pre-2024 invoice resolves NO rate at all (not merely the transient 5%). Is
     historic (pre-2024) ingestion in scope? If yes, the rate table — and, for
     2022-2024 rows, the `IvaRate` enum in sync with it — must be extended
     backward with live-verified figures; until then nothing backfills rate
     history, and the parity gate (item 12) holds the two sides equal.
