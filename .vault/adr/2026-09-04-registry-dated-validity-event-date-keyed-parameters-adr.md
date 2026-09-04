---
tags:
  - '#adr'
  - '#registry-dated-validity'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:b8231653696a9797cfdd64d1982e694e064f3172408e139869ad0505cffe0a7c'
related:
  - "[[2026-09-04-registry-dated-validity-regulatory-constant-placement-sweep-audit]]"
  - "[[2026-08-19-registry-evidence-window-axes-adr]]"
  - "[[2026-08-31-period-revision-resolution-ad-hoc-operation-date-axis-adr]]"
  - "[[2026-08-28-registry-narrow-mechanism-widening-adr]]"
---

# `registry-dated-validity` adr: `event-date keyed regulatory parameters` | (**status:** `accepted`)

## Problem Statement

Some regulated values are fixed by the law in force when an EVENT occurred rather
than by the filing period, and that event can predate every revision the owning
modelo declares. The bienes de inversion regularisation windows, threshold and
divisors are fixed at ACQUISITION, and a good acquired in 2016 stays in its
nine-year window until 2025 while modelo 303 declares revisions only from 2022.
The prorrata especial margins are sharper: one provision carries two values with
two validity windows AND two different comparison operators, and the earlier
value governs years no revision covers.

An earlier draft of this record claimed these were unreachable because a
parameter is addressed by modelo revision. **That was wrong and is corrected
here.** The address is not the obstacle. The parameter resolver is already
axis-generic: each value declares its own axis, the caller supplies a
`date_context`, and the value whose window covers that axis's date is selected,
raising when matches are not exactly one. Nothing clamps a value's window to the
revision's span — `DatedValue` validates only that `valid_to` is on or after
`valid_from`, and the revision-clamping logic applies solely to bracket tables on
the filing-period axis. A 2016 acquisition can be read from a 2022 revision today
by declaring a value on a transaction-date axis.

Two things genuinely block it. First, no caller supplies a non-filing axis:
every `date_context` in the tree is built as filing period only. Second, and
decisively, a substantive-law citation whose `effective_to` precedes the hosting
revision's `valid_from` is refused outright, so the pre-2015 prorrata wording
cannot ground a value hosted on a 2022 revision.

## Considerations

The axis vocabulary already exists and is entirely unexercised. Five axes are
declared — filing period, devengo date, transaction date, invoice date,
submission date — and measurement across the whole registry finds all 359 dated
parameter values AND all 133 bracket-table axis declarations on the filing
period. Four axes have never been used.

The second blocker is not new ground. It is the defect class an ACCEPTED ADR
already diagnosed, whose remedy it authorised and whose own Implementation
section records that the retroactive-reach axis is NOT implemented, requiring an
opt-in declared governed-period span on the legal reference that the check reads
in preference to the in-force span. A separate accepted decision one layer up
faced the same shape and chose to thread the event date into the existing call
rather than build a new route.

The IVA rate table was cited in the earlier draft as a precedent to generalise.
That was a second error. Verification shows it reads its TOML through a
standalone cached loader and never touches the validated authority during a
lookup. It is the one mechanism in the tree that BYPASSES the authority, so it is
an outlier to be brought inside rather than a template to replicate, and
replicating it would build the second parameter authority the boundary rules
forbid.

## Considered options

- **A modelo-independent, event-date-keyed parameter space. REJECTED, and this
  was the earlier draft's choice.** It solves an addressing problem that does not
  exist, and its cited precedent bypasses the validated authority.

- **Declare the figure on the legal-catalogue entry.** Genuinely attractive: the
  catalogue is already modelo-independent, already carries effective windows and
  verbatim grounding, and matches the principle that consolidation follows the
  PROVISION. Rejected because it collapses the evidence surface into a value
  surface, and one provision id cannot carry the two values and two operators the
  prorrata pair needs without inventing per-window catalogue entries.

- **Backfill revisions, or key to the filing period anyway.** Rejected: the first
  fabricates grounding, the second applies current law retroactively.

- **Author for covered years and fall back to a constant.** Rejected as the
  silent consumer-side fallback the authority-flow rule forbids.

- **Implement the accepted governed-span axis, then supply the event axis at the
  call site. CHOSEN.** No new address model, no new authority, no new value
  space. It uses the resolver that already ships and unblocks the one check that
  actually refuses.

## Constraints

Resolution stays fail-closed. A value whose event date falls in no declared
window raises; it never falls back to a literal.

An effective window states a LEGAL effect, never a data-refresh boundary. The
rate table's own header records the defect this prevents, where a refresh date
read as a legal start made two open years unvaluable.

A value expressible as a filing-period parameter MUST be authored as one.
Admission to a non-filing axis requires a declared reason naming the provision
and the axis, enumerable and gated in both directions, per the accepted standard
that a narrow registry mechanism widens only by explicit evidence-carrying
declaration.

Consolidation stays by PROVISION, never by VALUE. Several sites deliberately
refuse to merge numerically agreeing values across provisions, and merging them
would introduce defects.

## Implementation

Implement the governed-span axis the evidence-window ADR authorised: an opt-in
declared governed-period span on the legal reference, read in preference to the
in-force span by the substantive-law check that today refuses a citation whose
`effective_to` precedes the revision's `valid_from`. Amend that ADR if its scope
must widen from retroactive reach to superseded-provision reach.

Then author the blocked clusters as dated values on the EXISTING modelo
parameters with a non-filing axis, and extend `date_context` construction at the
consuming sites to supply the acquisition or operation date.

Two questions are explicitly NOT decided here and must be settled before or
alongside that work. Whether the comparison operator is registry data: the
prorrata pair differs by operator, exclusive before 2015 and inclusive from 2015,
and no dated-value field carries an operator. And whether a new axis member is
added or the transaction-date member is reused for acquisition, which is a schema
change with a parity gate behind it.

Out of scope: the SAL figures and the maritime exemption fraction, whose
consumers carry no date field at all. In scope where the event date is already a
typed field on the consumer's own record — noting that the bienes de inversion
values are reached through zero-argument enum properties, so that cluster still
needs the date threaded into two properties before it can resolve.

Separately, the IVA rate table should be brought inside the validated authority.
That is its own decision, not a consequence of this one.

## Rationale

The correction matters more than the conclusion. The earlier draft would have
authorised a parallel parameter authority to route around a mechanism that
already works, on the strength of a precedent that does the opposite of what was
claimed. Two independent reviews, one checking facts by execution and one
checking the decision, converged on the same error.

What survives is the audit's finding, narrowed to what is measurable: the axis,
the schema and the fail-closed resolver all ship; one grounding check refuses;
no caller supplies a non-filing axis. That is a much smaller problem than a
missing address model, and it is already half-authorised by an accepted decision.

## Consequences

Event-date-governed values become resolvable through the existing parameter
address with dated windows and legal references, without a new value space and
without a second authority.

Four declared date axes stop being dead capability.

The prorrata especial operator question surfaces as a distinct decision rather
than being smuggled into a value model that cannot express it.

Until the governed-span axis lands, the blocked clusters remain leaf constants
and must not be forced into parameters; the placement audit records why each is
blocked so the attempt is not repeated.
