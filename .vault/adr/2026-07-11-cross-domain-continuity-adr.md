---
tags:
  - '#adr'
  - '#cross-domain-continuity'
date: '2026-07-11'
modified: '2026-07-11'
body_hash: 'sha256:46b474ee01f6e5700c66b7a0d2c47a7e2333315ddd228796dcc03a706d991525'
related:
  - "[[2026-07-11-cross-domain-continuity-research]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# `cross-domain-continuity` adr: `Separate Article 27 deadline posture, conditional preview, and statutory assessment` | (**status:** `accepted`)

## Problem Statement

S343 was reopened because an overdue work unit is a deadline fact, not evidence
that a statutory Article 27 recargo is due. The current calculate projection can
show an Article 27 band from a voluntary deadline and a supplied or fallback
reference date. Its `conditional` flag distinguishes an advisory from a claimed
computation, but it does not establish the facts that turn either one into a
legal assessment.

Article 27 requires a late presentation without prior administrative
requirement and applies the recargo to an amount payable. A money result also
needs the applicable historic regime and, for the over-twelve-month tail, the
Article 26 interest inputs. The current surface has no provenance-bearing proof
of absence of a prior requirement, no authoritative identity/revision/same-facts
link, and no calculation of recargo or interest money. Local filing state is not
official evidence. Calling a rate-only projection a statutory computation would
therefore overstate the application's authority.

## Considerations

The binding distinction is between a filing calendar posture, a non-binding
conditional preview, and a statutory assessment. These are different domain
claims with different evidence thresholds; a Boolean on one recargo payload
cannot make unproven primitives legally sufficient.

The calendar rule remains independently useful. The post-2021 scale keeps the
exact twelve-month anniversary at 13 percent without interest and moves to the
15-percent-plus-interest tail only on the following day. That rate boundary must
not be weakened while the assessment boundary is tightened.

A lawful assessment needs, at minimum, an actual presentation date; a positive
official or auditable amount payable; evidence that no prior requirement exists;
taxpayer identity, modelo, period, and revision linkage; and same-facts,
payment/executive, reduction, effective-dated-regime, and historic-interest
facts. Each fact must retain its source and revision. An unknown or contradictory
fact cannot be inferred from a draft, current date, or local storage.

## Considered options

1. **Keep the current deadline projection as a recargo computation.** Reject: a
   deadline, a rate band, and `conditional=False` do not prove the statutory
   prerequisites or yield a money result.
2. **Enrich the existing rate payload with three provenance fields.** Reject:
   presentation, amount, and no-prior-requirement evidence improve the payload but
   still omit the remaining Article 27 and Article 26 conditions.
3. **Adopt a phased three-outcome boundary.** Accepted: retain calendar posture,
   offer an explicitly non-statutory conditional preview, and reserve assessment
   for a complete, provenance-bearing statutory input set.
4. **Implement a complete assessment immediately.** Defer: the bundled Article
   27 corpus and historic legal/interest data are not yet sufficient to support it.

## Constraints

The statutory-assessment branch MUST fail closed to an unassessed result unless
every required fact is present, internally consistent, source-attributed, and
valid for the filing's effective legal regime. It MUST NOT substitute `today` for
an actual presentation date or treat a local filed observation as official proof.

The implementation depends on completing and reviewing the Article 27 corpus,
the Article 26 interest inputs, historic regime dates, and typed evidence
contracts. Those parent capabilities are incomplete, so no assessment behaviour
may be exposed before they are stable. The existing deadline engine and its
calendar-threshold rule are stable enough to remain the source of deadline
posture and of a clearly labelled preview.

## Implementation

The proposed architecture defines three typed outcomes:

- `DeadlinePosture` reports only voluntary-window facts: close date, in-time or
  overdue state, and days remaining or overdue. Its operator wording says the
  voluntary deadline has elapsed; it makes no recargo eligibility or liability
  assertion.
- `ConditionalRecargoPreview` reports a rate consequence only as an advisory,
  explicitly marked unassessed. It may use the governed calendar threshold, but
  carries neither a statutory eligibility claim nor a monetary settlement.
- `StatutoryRecargoAssessment` is introduced only after a dedicated evidence
  boundary validates the complete input set. It produces a provenance-carrying
  monetary recargo, any applicable interest, and reduction/payment posture; all
  incomplete or conflicting evidence produces the unassessed outcome instead.

CLI text, JSON, and persisted calculation projections will preserve this
distinction rather than converting a deadline warning into an assessed tax
consequence. Boundary tests will use independently sourced legal thresholds and
prove the exact-anniversary rule, absence of evidence, contradictory evidence,
and a fully evidenced future assessment.

## Rationale

The related research and Article 27 reference reconciliation show that the
calendar calculation and the legal assessment have different inputs and outputs.
Separating them keeps useful deadline guidance available today while preventing
the application from representing an estimate as a government determination.
The phased boundary also makes the later assessment auditable: every legal
predicate has a named evidence carrier instead of being hidden behind a Boolean.

## Consequences

If accepted, this ADR permits no immediate statutory-money output. Existing
operator language and machine contracts that imply a determined recargo will need
to migrate to posture or preview terminology, which is an intentional breaking
semantic correction. A later assessment remains blocked on legal-corpus and
evidence completion, not merely on API wiring.

The decision preserves the correct rate boundary and establishes a safe path to
a future assessed result. It does not establish that any individual filing owes a
recargo, interest, or reduction; that determination remains unavailable until
the assessment contract is implemented and the evidence validates.
