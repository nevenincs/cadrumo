---
tags:
  - '#adr'
  - '#registry-dated-validity'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:bd3d5d7bb2e78796fc8552a077f53bc058ea98a9d1f4f63f2af4c4abef083f49'
related:
  - "[[2026-09-04-registry-dated-validity-regulatory-constant-placement-sweep-audit]]"
  - "[[2026-08-19-registry-evidence-window-axes-adr]]"
  - "[[2026-08-31-period-revision-resolution-ad-hoc-operation-date-axis-adr]]"
  - "[[2026-08-28-registry-narrow-mechanism-widening-adr]]"
---

# `registry-dated-validity` adr: `event-date keyed regulatory parameters` | (**status:** `accepted`)

## Problem Statement

This record decides TWO distinct shapes together, and says so plainly because an
earlier draft bundled them under one title. The first is an event-date axis for
bienes de inversion, whose windows and divisors are fixed at ACQUISITION. The
second is pre-revision coverage for prorrata especial, which is FILING-YEAR keyed
and whose problem is GROUNDING rather than an axis: its predicate selects on the
filing year, and its earliest redaction simply predates modelo 303's earliest
revision. The remedies differ, and the sections below keep them apart.

A good acquired in 2016 stays in its nine-year window until 2025 while modelo 303
declares revisions only from 2022. The prorrata especial provision carries two
values with two validity windows AND two different comparison operators, and the
earlier value governs years no revision covers.

An earlier draft claimed these were unreachable because a parameter is addressed
by modelo revision. **That was wrong and is corrected here.** The address is not
the obstacle. The parameter resolver is already axis-generic: each value declares
its own axis, the caller supplies a date context, and the value whose window
covers that axis's date is selected, raising when matches are not exactly one.
Nothing clamps a value's window to the revision's span — the dated value
validates only that its end is on or after its start, and revision clamping
applies solely to bracket tables on the filing-period axis. A 2016 acquisition
can be read from a 2022 revision today by declaring a value on a transaction-date
axis.

Two things genuinely block it. First, no caller supplies a non-filing axis: every
date context in the tree is built as filing period only. Second, and decisively,
a substantive-law citation whose end date precedes the hosting revision's start
is refused outright, so the pre-2015 prorrata wording cannot ground a value
hosted on a 2022 revision.

## Considerations

The axis vocabulary already exists and is entirely unexercised. Five axes are
declared — filing period, devengo date, transaction date, invoice date,
submission date — and measurement across the whole registry finds all 359 dated
parameter values AND all 133 bracket-table axis declarations on the filing
period. Four axes have never been used.

The second blocker sits on a mechanism that has ALREADY SHIPPED. The legal
reference carries a declared governed-period span, an accessor returns it in
preference to the in-force span, the substantive-law check reads it, and four
catalogue entries declare it today. An earlier draft said that axis was
unimplemented; that claim was inherited from the authorising ADR's own
Implementation section, which is stale at HEAD, and was not verified. It is
corrected here.

What has NOT shipped is the DIRECTION this record needs. The declaration is
validated retroactive-only — a governed span must begin strictly before the
provision's entry into force, and the validator refuses a forward value in terms,
on the ground that it would let a stale citation ground a period its norm never
governed. That guard is correct and stays. But prorrata needs the forward
direction: a superseded provision hosted on a later revision. Expressing it
through the field as shipped would require declaring both that a 1993 provision
reaches back before its own force AND that a provision repealed in 2014 governs
2022. Both are false, and this record's own honesty constraint forbids them.

A separate PROPOSED decision one layer up faced the same shape and chose to
thread the event date into the existing call rather than build a new route. It is
supporting reasoning, not settled precedent.

The IVA rate table was cited in an earlier draft as a precedent to generalise.
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

- **Widen the governed-span check to superseded-provision reach, then supply the
  event axis at the call site. CHOSEN.** No new address model, no new authority,
  no new value space. The retroactive half already ships; this adds the forward
  half as a second explicit declaration and unblocks the one check that actually
  refuses.

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

The retroactive-only guard on the existing governed span is NOT relaxed. Forward
reach is a separate declaration, so neither can silently widen the other.

Consolidation stays by PROVISION, never by VALUE. Several sites deliberately
refuse to merge numerically agreeing values across provisions, and merging them
would introduce defects.

## Implementation

The governed-span axis ships in its retroactive direction. The work here is the
FORWARD direction: a declared superseded-reach span on the legal reference,
distinct from the existing retroactive span so neither declaration can relax the
other, read by the substantive-law check at the point it today refuses a citation
whose end date precedes the revision's start. The authorising evidence-window ADR
is amended in place to record that its retroactive axis has landed; its
retroactive-only constraint is widened HERE, not there.

The comparison operator IS registry data. A provision whose redactions differ on
the operator as well as the value cannot be expressed as two dated values
otherwise, and leaving the operator in Python preserves the year branch this
decision exists to remove. The dated value gains an explicit operator field,
defaulting to the current exclusive semantics so no existing value changes
meaning. The acquisition axis REUSES the transaction-date member rather than
adding one: the bienes de inversion consumer record already exposes a transaction
date as a typed field, and a synonym member would create two spellings of one
fact.

A parameter carries values on exactly ONE axis. Resolution requires every value's
axis to be present in the caller's date context, so a mixed-axis parameter breaks
every existing caller; and the overlap validator groups by axis and therefore
cannot see a cross-axis double match, which would surface at runtime rather than
at load. The blocked clusters are authored as NEW single-axis parameters under
the existing modelo, never by adding a non-filing value to a parameter that today
carries filing-period values, and a load-time refusal of mixed-axis parameters
lands with them.

In scope where the event date is already a typed field on the consumer's own
record. Two consumer-side changes are PREREQUISITES rather than consequences: the
bienes de inversion values are reached through zero-argument enum properties that
must take the date, and the prorrata predicate is a pure domain function taking a
year with no registry dependency at all, so routing it to a parameter is a
dependency-direction change decided at the application boundary, not inside the
domain module.

Out of scope: the SAL figures and the maritime exemption fraction, whose
consumers carry no date field at all. Separately, the IVA rate table should be
brought inside the validated authority — its own decision, not a consequence of
this one.

## Rationale

The corrections matter more than the conclusion. The first draft would have
authorised a parallel parameter authority to route around a mechanism that
already works, on a precedent that does the opposite of what was claimed. The
second draft then asserted the remedy was unimplemented when it had already
shipped, inheriting a stale claim from another record without checking it. Three
independent reviews caught these — two on the first draft, one on the second.

What survives is the audit's finding, narrowed to what is measurable: the axis,
the schema and the fail-closed resolver all ship; the governed span ships in one
direction; one grounding check refuses the other; no caller supplies a non-filing
axis. That is a much smaller problem than a missing address model. Half the
mechanism already exists; what this decides is the forward direction the shipped
half deliberately refuses, and why refusing it was right until now.

## Consequences

Event-date-governed values become resolvable through the existing parameter
address with dated windows and legal references, without a new value space and
without a second authority.

One declared date axis is exercised for the first time, and the axis vocabulary
stops being wholly unused.

The comparison operator becomes registry data, which is what makes the prorrata
pair expressible at all rather than leaving in place the year branch this
decision exists to remove.

Mixed-axis parameters become a load-time refusal, closing a gap where a
cross-axis double match would otherwise surface only at runtime.

Until the forward span lands, the blocked clusters remain leaf constants and must
not be forced into parameters; the placement audit records why each is blocked so
the attempt is not repeated.
