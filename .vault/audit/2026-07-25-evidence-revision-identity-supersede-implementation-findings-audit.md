---
tags:
  - '#audit'
  - '#evidence-revision-identity'
date: '2026-07-25'
modified: '2026-07-26'
related:
  - "[[2026-07-24-evidence-revision-identity-adr]]"
  - "[[2026-07-25-evidence-revision-identity-plan]]"
---

# `evidence-revision-identity` audit: `what the supersede design meets in the code`

## Scope

Implementing S03 of the evidence-revision-identity plan — the supersede
transition the governing ADR was ruled `accepted` on. The design did not survive
contact with the code, and this document records what was found before any source
was written. No production file was changed.

The semantic index was unusable throughout: 902 chunks against 3,681 tracked
source files with `degraded_reasons` empty, and a probe naming the exact concept
returned five chunks of one unrelated module at scores from 0.06 down to 0.013.
Discovery was therefore performed by exhaustive signature sweep instead, under
the narrow substitution this repository has adjudicated once before for the
canonical-JSON consolidation: it is admissible only where a concept has a
mechanically exhaustive textual signature, so that coverage is complete by
construction rather than by diligence.

This concept qualifies. Any mechanism that opens a new calculation revision must
either construct a `CalculationRevision` or call the id deriver. Production holds
exactly three construction sites and a bounded set of deriver callers, all
enumerated and read. A supersede-like mechanism cannot exist outside that set.

## Findings

### supersede-as-specified-collides-with-its-own-id | critical | the accepted option is unimplementable as written

The ruling specified that supersede "opens a NEW draft revision from a finalized
one, carrying the same inputs and re-capturing the bundle at the next verify".
Carrying the same inputs is precisely what makes it impossible. The revision id
is content-addressed over those inputs, so a supersede that changes no value
re-derives the id it is trying to escape.

This is not speculative. The amendment path already implements exactly that
shape, and already guards it: it mints a new id from the baseline revision's
inputs plus corrected values, then refuses outright when the result already
exists, with the message that no-op overrides cannot be filed as amendments. A
supersede carrying unchanged inputs is that refused no-op by construction.

Escaping the collision requires a discriminator inside revision identity — which
is the option the same ADR reserved for operator sign-off, and which the ruling
declined to take on the implementer's judgement. So the accepted option leads
back to the decision it was chosen to avoid.

### amend-is-not-the-answer-either | high | it is post-filing and structurally unreachable in the trap

Amend looked like the existing owner of this concept and is not. It loads its
baseline from a filing record, refuses when that record carries no external
evidence, and refuses on target state. The trap occurs when export refuses, which
is before any filing record exists. Amend cannot be reached from the trapped
state at all, so it is neither the mechanism to reuse nor a duplicate to worry
about.

### a-supersede-state-already-ships | medium | the state machine already models supersession, for the filed case

`CalculationRevisionState.PRESENTADO_SUPERSEDIDO` already exists, is set when a
later verified revision is filed, and is read by roughly a dozen surfaces
including export, ledger lifecycle guards, the participation index and the IVA
wallet seed. Supersession is therefore already a modelled concept for the filed
case. A new verb introducing a second supersession notion for the pre-filing case
would have been a parallel authority over the same word — the exact hazard the
discovery mandate exists to prevent, and invisible to the degraded index.

### the-evidence-gap-belongs-on-an-identity-axis-that-already-exists | critical | a cheaper mechanism satisfies every constraint the ruling set

The refusal reads the FROZEN bundle: the deductible-evidence gate derives its gap
from `revision.ledger_filing_evidence`, and per-row it tests the evidence
references carried on the bundled row. Attaching an invoice to the live ledger
row therefore cannot move it, which is why the trap holds.

But `source_issues` is already an argument to the revision id deriver and is
already threaded at the persist site, and its documented purpose is that distinct
resolution outcomes cannot collapse to one revision. Its sole existing producer
projects a calculate-time diagnostic into a durable issue precisely so the
condition stays available to a later verification or export gate. That is the
same shape the evidence gap needs.

Recording the deductible-evidence gap as a source issue at calculate would make
the gap part of revision identity through an axis that already exists. Before the
attach the revision carries the issue; after the attach a recalculation does not,
so it derives a DIFFERENT id, mints a new draft, re-captures the bundle at verify
and exports. The trap dissolves with no new verb, no change to the deriver's
definition, no mutation of a finalized record, and no second supersession notion.

It also survives the objection that sank the evidence-digest option. That option
was rejected for reversing a documented content-addressing invariant; this one
uses that invariant exactly as designed — it changes what legitimately feeds an
existing identity axis, not what identity means.

### the-source-issue-route-does-not-fit-either | critical | third iteration, and the carrier is semantically wrong for this condition

The mechanism recommended above was pressed further before being planned, and it
does not survive either. Recording the reversal rather than leaving the earlier
recommendation standing.

`CalculationSourceIssue` cannot carry an evidence gap as it stands. Its `reason`
is a closed `Literal` admitting exactly one value, and `binding_source` is
required — an evidence gap has no binding source. Adopting this route therefore
means widening a Literal AND relaxing a required field on a strict-frozen
PERSISTED model that verification reads. That is a persisted-schema change on the
filing path, carrying roundtrip and anti-tautology obligations, not the cheap
re-use of an existing axis it first appeared to be.

The semantic objection is the stronger one and is independent of cost. That model
means, in its own words, a source observation that could not be consumed by any
declared binding, and it explicitly exists to avoid misrepresenting such an
observation as provenance for a computed output. A deductible row whose invoice
is missing was CONSUMED — it contributed to the casilla value; what is absent is
its supporting evidence, not its consumption. Forcing the condition into that
envelope would state something false about the calculation, which is the precise
misrepresentation the model was shaped to prevent.

So the option space for dissolving the trap is now bounded and every branch is an
architecture decision rather than an implementer's judgement: a discriminator
inside revision identity (reserved to the operator by this ADR), a new persisted
issue envelope of its own with its own roundtrip obligations, or widening an
existing persisted model in a way that misdescribes the condition. There is no
fourth route that is merely cheaper.

That is the honest terminus of this investigation. Three designs were taken to
the code and three failed for different structural reasons — the specified
supersede on id collision, amendment on reachability, and this one on carrier
semantics. The recurring cause is that revision identity is deliberately closed
over tax facts, and evidence is deliberately outside it. Any recovery path must
either reopen that boundary or add a record beside it, and choosing which is the
decision the governing ADR reserved from the start.

### the-sequence-frame-backlog-is-triaged-not-pending | medium | S07's work is done, and its reason code now misnames the result

S07 was carried as unblocked implementation work. Measured at HEAD it is neither
unblocked in the way assumed nor outstanding in the way assumed.

The audit that produced the step counted 72 directly-runnable display-only
frames. Thirty-three remain flagged, so roughly forty were converted by peers in
the interim. More importantly, the second half of the step is structurally
guaranteed rather than pending: `@blocked <code> <detail>` is MANDATORY beneath
every `@static` frame and the parser refuses a frame without one. The tree holds
153 static frames and 153 blocked reasons. Display-only is already a stated
constraint, which is precisely what the step asked for.

The residue is triaged, not untouched. Every one of the thirty-three carries a
measured, page-specific reason: nine because no registry revision covers filing
year 2026, five on cumulative-page filing order, three on cross-period clean
state, several cascading from a blocked parent frame, one because no CLI verb
creates an evidence bundle so no id exists to address, and FIVE that say "Do NOT
convert" outright with evidence — converting them would double an import, switch
the active profile and strand the rest of the page, or drive a real browser at
the AEAT sede.

Two of them are blocked by `REFUSED_MODELO_EXPORT_EVIDENCE_MISSING` and
`REFUSED_MODELO_FILING_EVIDENCE_MISSING` — the deductible-IVA evidence trap this
very record exists to resolve. So S07 was not independent of the blocked decision
after all, which is a correction to how it was filed and to my own statement that
it was cleanly available work.

One earlier claim of mine is withdrawn as overstated. Reading that several frames
cite "work file rejects an already-presentado revision", I concluded the premise
was stale because the idempotent re-file is implemented and returns the existing
VIGENTE record. That path is conditional: it falls through to the hard refusal
when no VIGENTE record exists, so the frames' reasons are not simply false. The
files carrying that wording are also under live peer edit and may be being
revised now.

The durable finding is the reason code itself. `unconverted` no longer means "not
yet triaged"; it means "triaged and not convertible for a stated reason", and in
five cases it means the opposite of what it says. A later pass reading the code
name rather than the detail will redo this work — the same prose-asserting-a-
guarantee-that-no-longer-holds pattern this campaign has now found five times.
Splitting it into a converted-later code and a deliberate do-not-convert code
would close that, and belongs to whoever owns the sequence corpus.

## Recommendations

The accepted ruling's chosen option should be superseded rather than built. It is
unimplementable as specified, and the alternative found here is cheaper and meets
every constraint the ruling set. Superseding is the correct move rather than an
in-place edit: the record was ruled `accepted` and executed against, so it must
stand as the historical account.

One caveat is decisive for who may take that decision, and it is why no code was
written here. Making the evidence gap feed revision identity changes the id a
recalculation derives for revisions that already exist. That is a behavioural
change on filing-grade records a human files outside the application, and the
governing ADR reserves exactly that class for operator sign-off rather than an
implementer's judgement. The mechanism is cheaper than the supersede verb; the
authority required to adopt it is not lower.

The stranded work unit, the other half of that ADR, is already closed and needed
none of this: it was independent, reachable by instinct, and is fixed.

A process note worth keeping. Every finding above was invisible to semantic
search in its degraded state and was recovered by enumerating the concept's
mechanically exhaustive signature. That substitution is narrow and does not
generalise, but where it applies it discharged the mandate's actual purpose —
establishing that no canonical owner already existed — rather than merely
satisfying its form. It found a shipped supersession state and an existing
identity axis that a blind implementation would have duplicated.

### Terminus, and what was checked to establish it

The implementable surface of this feature is exhausted. Every remaining row was
tested against the code rather than assumed blocked, and the last candidate was
checked after the rest had failed.

That candidate was the misleading-refusal defect class — the same one already
fixed on `create_work_unit`, where a refusal named a remedy that itself refused.
The export evidence refusal does NOT carry it. Its suggestion states outright that
the linking commands are only half the answer, that this revision bundled its
evidence at verify, and that attaching now does not unblock the export; the locale
text names the ordering that does work. The signposting the governing ADR
describes as landed is genuinely landed and honest.

So the position is: the trap is signposted so no operator is silently caught, the
independent half (the stranded work unit) is fixed and gated, the docs residue is
triaged, and recovery for an operator already caught requires one of three
branches — every one a persisted-schema or identity change this record's own
Constraints reserve.

What would make the remaining work implementable is a single choice among those
three, not further investigation. Four separate attempts have now run into the
same boundary from different directions, which is itself the evidence that the
boundary is real rather than a gap in the analysis.

### The decision is binary, not three-way

A correction to this record's own framing, and it makes the open decision
simpler than four passes of analysis had left it.

The three branches collapse to one. The trap is that a recalculation returns the
SAME revision, so no new bundle is captured. Only a different revision id produces
a new revision; only the deriver's parameters determine that id; and the bundle is
captured at exactly one site. A persisted record that sits BESIDE the revision —
the branch that looked like the cheap middle option — cannot change what a
recalculation returns, so it cannot dissolve the trap at all. It collapses into
the identity branch or it does nothing.

So the operator is not choosing among three mechanisms. The choice is binary:
either evidence enters what determines revision identity, in some form, or it does
not and the current signposted state stands. Everything else is a variation on the
first, differing only in which carrier does the work and how honestly that carrier
describes the condition.

That also explains why four independent attempts converged: they were not four
routes, they were four spellings of one route, and the ADR's Constraints already
named it. The reservation was correct when written and is now demonstrated rather
than asserted.

What this buys the decision-maker is that the question needs no further
investigation and no comparison table — it is a single yes or no on whether
evidence is a fact about a calculation revision. The implementation follows
mechanically from that answer.
