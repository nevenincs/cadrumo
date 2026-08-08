---
tags:
  - '#adr'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:e2f48b4cb7d712533a3d7ce4489d2564136e3b52cad46c3c84b6797e90663600'
related:
  - "[[2026-08-08-synced-history-consumption-research]]"
---
# `synced-history-consumption` adr: `Which pulled AEAT facts are calculation inputs` | (**status:** `accepted`)


## Problem Statement

A brand-new profile can pull its AEAT-stored filing history. Which of those pulled facts may feed a calculation, and which must stay reconciliation or display only?

**This record was scaffolded against a premise the plan's own census falsified, and the corrected position is the one any ruling must address.** The scaffolding premise was that the pulled filing record reached only the Modelo 303 IVA wallet. Measured from the loaded registry authority: of 1253 bindings across 73 modelos and 90 revisions, **81 draw a value from a prior return, and 72 of those 81 have a pull-reachable source**. Every pulled modelo's active filed observation is written to the calculation observation repository under an official AEAT source kind, and the general carries read that store with no provenance filter.

So the question is not whether pulled facts reach calculations. They do, broadly. The question is whether they SHOULD, per channel, and what the nine unreachable ones mean.

Two consequences reshape the decision. First, the reachability is already live rather than prospective, so a ruling that some channel must not consume pulled evidence describes a change to shipped behaviour, not a feature to build. Second, the nine structurally excluded bindings are all Sociedades, because neither Modelo 200 nor Modelo 202 declares the authenticated read surface on any revision — a coverage gap in what the pull can fetch, categorically different from a wiring gap in what the engine consumes, and it must not be ruled on as though it were the same defect.

The census also records what it could not measure: reachability is a join of a measured write against a measured unfiltered read, with no run observed end to end, and three runtime gates unexercised. A ruling resting on "reaches today" inherits that limit.

## Considerations

The denominator this ruling is taken against, measured from the loaded registry
authority and not from prose: 1253 data bindings across 73 modelos and 90
revisions. 81 of them draw a value from a prior return. 72 have a pull-reachable
source and nine do not. The nine split two `direct_annual_settlement` on Modelo
200 fed by Modelo 202, and seven `factual_evidence`, three on Modelo 200 and four
on Modelo 202. An earlier reference stated that split as three and nine, which
does not reconcile with a subtotal of nine, and it was corrected by re-deriving
each of the nine from the authority and naming it individually.

The registry already carries a non-analogical axis for this question, which is
why this ruling does not invent one. `DependencyClassificationDefinition.treatment`
is a closed field declared once per source modelo per revision, each instance
carrying its own required legal and source references. Joining all 81 carries to
the treatment governing each gives 52 `direct_annual_settlement`, 12
`factual_evidence` and 17 with no declared treatment at all. Nothing lands in
display only: every one of the 81 feeds a binding a formula or a bound casilla
reads, so that bucket is empty by measurement rather than by choice.

Four measured facts constrain any ruling, and none of them was available when this
record was scaffolded.

The 72 reachable carries are consumed TODAY, proven by execution rather than by
reading a resolver: Modelo 100 for 2024, casilla 0604, is absent on a profile with
no history and holds 1416.00 on a profile with a pulled one, both poles driven
through the live operator calculate over one law-resolved revision, with no
refusal diagnostic on the pulled pole. A ruling that a channel must not consume
pulled evidence therefore describes a change to shipped behaviour.

The registry draws a line the resolver does not stand on. `treatment` is read at
exactly one production site on the resolution path and folded into a requirement
grouping key, so it discriminates bucketing and gates nothing. A
`factual_evidence` Modelo 193 retención the taxpayer SUFFERED reaches the annual
return by the identical path a `direct_annual_settlement` Modelo 130 pago
fraccionado does.

Revision re-confirmation is not a safeguard here and this ruling does not lean on
one. The pull supplies no stamped revision id. The repository resolves the
law-determined revision itself, and the carry gate re-confirms by resolving the
same triple against the same authority: the same call returning the same answer.
That check catches a stamp a producer supplied from a snapshot it held, and there
is no such producer on this path.

One channel sits outside the aggregation taxonomy altogether. Modelo 130's
previous-year economic-activity net income declares `source = previous_filing`
with `source_modelo = 100`, a filing-year delta of minus one and no grouping. That
is a cross-modelo fold-in, whose canonical mechanism is a relation, occupying the
row reserved for a same-modelo static carry.

## Considered options

**Rule every pulled fact a calculation input**, ratifying what ships. Rejected: it
discards the registry's own declared distinction between a figure that settles a
liquidation and a fact to reconcile against, and it would make an undeclared
treatment retrospectively authoritative for 17 channels that declare nothing.

**Rule every pulled fact reconciliation-only.** Rejected: it changes shipped
behaviour on 50 live channels whose registry declaration says the source figure
settles directly, and applied naively it would strip a taxpayer of retenciones and
pagos fraccionados they are entitled to deduct, which is the over-declaration
direction this campaign already measured as unwatched.

**Defer the whole ruling until the nine Sociedades slots are settled.** Rejected:
it holds 72 measured channels hostage to nine whose answer needs one operator
action, and leaves the shipped consumption unruled in the meantime.

**Rule per the registry's own declared treatment, conditionally for the nine.**
Chosen. It is grounded per row in provisions that row already cites, it needs no
analogy between modelos, and it separates what is measured from what is not.

## Constraints

A pulled filing is evidence of what was declared. It is not automatically an authorised input to a new computation, and the existing evidence boundary already holds local app filings distinct from AEAT filing evidence for exactly that reason: an observation persisted by the local flow carries a non-official source kind and must never satisfy the gate that external AEAT filing evidence satisfies. Any ruling that promotes a pulled fact to a calculation input must say why that promotion does not erode this distinction.

Each wired channel must use exactly one mechanism from the established one-mechanism-per-calculation-type taxonomy. Modelling one fold-in two ways at once is the defect that taxonomy exists to prevent, so a channel with no matching row requires amending the taxonomy before code lands, not inventing a second path.

A carried value must stamp its law-determined revision and re-confirm that stamp against the source context before it is trusted. The carry path is the one place a revision error compounds across years.

No ruling may authorise back-deriving ledger transactions from a pulled declared value: that invents transactions which never existed and corrupts the evidence bundle a revision is required to carry.

Revision resolution stays law-determined from modelo, filing year and period. A pulled record's stored revision id may only be asserted equal to that resolution, never injected as the selector.

## Implementation

THE RULING.

**`direct_annual_settlement` carries are CALCULATION INPUTS.** 52 bindings, of
which 50 are pull-reachable. The declaration says the source modelo's figure
settles directly into the target's liquidation, each instance citing its own
provisions, and that is a calculation input by declaration. This ratifies shipped
behaviour and requires no change.

**`factual_evidence` carries are RECONCILIATION TARGETS ONLY.** 12 bindings, of
which five are pull-reachable. The declaration says the prior filing is a fact to
reconcile against rather than a figure that settles the current return, and the
retención case is why the distinction is real: Modelo 193 records what a payer
declared about the taxpayer, evidenced to the taxpayer by an income certificate,
not by a return the taxpayer never filed. Today these settle figures identically
to the settlement class. That is the change to shipped behaviour this ruling
describes, and it is owned by `P02.S17`.

The remedy is constrained, not open. It must NOT blank the value. A taxpayer is
entitled to the retención, and a silent drop is an over-declaration, which is the
failure direction the apparatus does not watch. The value is surfaced as a
prefilled reconciliation figure carrying its provenance and its treatment, so a
consumer can tell it from a settled one.

**The 17 undeclared carries are NOT RULED, and cannot be.** No treatment is
declared for them, and a treatment that is undeclared cannot later be cited as
authority for having consumed the value. Classifying them here would require the
analogy between modelos this campaign forbids, correctly, since a Modelo 720
prior-year valuation baseline and a Modelo 130 prior negative result are not the
same kind of carry. `P02.S18` declares a treatment for each, grounded per row.
Until it lands, these channels are consumed today on no declared authority, and
this record does not supply one.

**Display only is EMPTY.** Not by choice: no pulled fact on the census exists
merely to be shown.

**The nine unreachable carries are ruled CONDITIONALLY, with the trigger stated.**
Whether AEAT serves Modelo 200 and 202 at the authenticated consulta surface
cannot be established from this repository, and inferring it from our own registry
silence is the error the fetch investigation refused to make. The trigger is one
authenticated read-only operator run of the filed discovery verb, which reads the
register's own modelo combobox through a reader this application already ships.

If 200 or 202 appears among the offered modelo options, our registry is missing a
live cross reference, the nine become reachable, and each is ruled exactly as its
treatment class above: the two `direct_annual_settlement` are calculation inputs
and the seven `factual_evidence` are reconciliation targets. If neither appears,
the nine are correctly unreachable, and the outcome is a recorded refusal naming
AEAT's coverage rather than a fix to our tree. Either way the operator's single
action resolves it without reopening this decision. `P02.S19` owns it.

**The Modelo 130 cross-modelo carry is not classified while it sits outside the
taxonomy.** It is the one renta carry reading another modelo's annual return, so
it is exactly the channel a pulled Modelo 100 history feeds, and ruling on a
channel whose mechanism is undecided would ratify the violation. `P02.S16` brings
it onto a canonical mechanism, preferring a relation with the cross-model-output
kind, or amends the taxonomy naming the rejected design. Its classification
follows from its declared treatment once its mechanism is settled.

MECHANISM PER WIRED CHANNEL, from the existing taxonomy, amended by none of this.
A cross-modelo fold-in uses a relation. A same-modelo static carry uses a direct
`previous_filing` binding. The Modelo 390 compensación partition uses the IVA
wallet decision. No channel ruled here needs a mechanism the taxonomy does not
already carry, which is why this record amends the taxonomy nowhere. The single
exception is the Modelo 130 carry, which is not a new mechanism but a channel on
the wrong existing one.

WHY THIS DOES NOT ERODE THE NON-OFFICIAL-EVIDENCE BOUNDARY. That boundary decides
whether a filing is PROVEN: an observation persisted by the local flow carries a
non-official source kind and cannot satisfy the gate external AEAT evidence
satisfies. This ruling decides what a proven filing's figures are FOR. The two are
independent, and nothing here promotes a locally-filed observation to official.
A pulled fact that is ruled a calculation input is one AEAT itself confirmed, and
it enters through the same official source kinds that boundary already recognises.

IMPLEMENTING ROWS, all opened in this same action. `P02.S16` the Modelo 130
taxonomy violation. `P02.S17` making the treatment distinction gate consumption.
`P02.S18` declaring a treatment for the 17. `P02.S19` the conditional ruling on
the nine. `P02.S20` the scoping precondition below.

A PRECONDITION, NOT A RECOMMENDATION. Feeding the pulled observation to the
existing divergence primitive is the obvious reconciliation mechanism, both sides
already live in the same bucket, and it is never wired. It stays blocked. A
freshly onboarded profile computes zero nearly everywhere, so reconciling every
pulled figure against it raises a mismatch on essentially every casilla, which is
the alert-fatigue failure the unconsumed-declarable-IVA rule exists to prevent. A
condition separating a local calculation populated enough that a divergence means
disagreement from one that is merely empty does not exist and may not be derivable
from what is persisted. `P02.S20` determines whether it is derivable and refuses
to wire the detector without one.

## Rationale

The registry's own `treatment` field is the only grounding available that is both
per-row and non-analogical. Every alternative required either transferring one
modelo's rationale to another, which AEAT surfaces do not support, or inventing a
classification axis this ruling has no authority to create. Using the declaration
also makes the ruling checkable: each classification can be read back off the
loaded authority together with the provisions that row cites.

Ruling the 72 now and the nine conditionally follows from what is measured versus
what is not. The consumption is measured, by execution on both poles. AEAT's
coverage of Sociedades filings at the consulta view is not, and no amount of
reading our own registry can establish it. Recording a conditional ruling with its
trigger keeps both halves honest and costs the operator one read-only action.

The remedy constraint on `factual_evidence` exists because the obvious
implementation is the harmful one. Making the treatment gate consumption by simply
not supplying the value would remove figures a taxpayer is entitled to, silently,
in the direction no gate here watches. The distinction must be visible to a
consumer without the value disappearing.

## Consequences

Shipped behaviour changes for the `factual_evidence` class, five reachable
channels today. Nothing changes for the 50 reachable settlement channels, which
this ruling ratifies.

17 channels are consumed on no declared authority until `P02.S18` lands. That is
stated rather than smoothed over: this record does not retrospectively authorise
them, and a later reader must not cite it as having done so.

The nine Sociedades carries remain unresolved by design, with a stated trigger and
a stated outcome for each branch. A reader must not treat their absence from the
ruled set as a ruling that they are out of scope.

The Modelo 130 carry remains unclassified until its mechanism is settled, which is
the one place this record declines to rule on a channel that is reachable and
consumed today.

Every ruling above maps to an opened row, and every row id was verified to resolve
in the plan before being cited here.
