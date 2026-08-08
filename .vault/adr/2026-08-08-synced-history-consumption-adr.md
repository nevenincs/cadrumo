---
tags:
  - '#adr'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:1267ae750b235d4c48add01c4d61b3e24c4d7c7d401f37d7b599f44753899e8e'
related:
  - "[[2026-08-08-synced-history-consumption-research]]"
---

# `synced-history-consumption` adr: `Which pulled AEAT facts are calculation inputs` | (**status:** `proposed`)

## Problem Statement

A brand-new profile can pull its AEAT-stored filing history. Which of those pulled facts may feed a calculation, and which must stay reconciliation or display only?

**This record was scaffolded against a premise the plan's own census falsified, and the corrected position is the one any ruling must address.** The scaffolding premise was that the pulled filing record reached only the Modelo 303 IVA wallet. Measured from the loaded registry authority: of 1253 bindings across 73 modelos and 90 revisions, **81 draw a value from a prior return, and 72 of those 81 have a pull-reachable source**. Every pulled modelo's active filed observation is written to the calculation observation repository under an official AEAT source kind, and the general carries read that store with no provenance filter.

So the question is not whether pulled facts reach calculations. They do, broadly. The question is whether they SHOULD, per channel, and what the nine unreachable ones mean.

Two consequences reshape the decision. First, the reachability is already live rather than prospective, so a ruling that some channel must not consume pulled evidence describes a change to shipped behaviour, not a feature to build. Second, the nine structurally excluded bindings are all Sociedades, because neither Modelo 200 nor Modelo 202 declares the authenticated read surface on any revision — a coverage gap in what the pull can fetch, categorically different from a wiring gap in what the engine consumes, and it must not be ruled on as though it were the same defect.

The census also records what it could not measure: reachability is a join of a measured write against a measured unfiltered read, with no run observed end to end, and three runtime gates unexercised. A ruling resting on "reaches today" inherits that limit.

## Considerations

## Considered options

## Constraints

A pulled filing is evidence of what was declared. It is not automatically an authorised input to a new computation, and the existing evidence boundary already holds local app filings distinct from AEAT filing evidence for exactly that reason: an observation persisted by the local flow carries a non-official source kind and must never satisfy the gate that external AEAT filing evidence satisfies. Any ruling that promotes a pulled fact to a calculation input must say why that promotion does not erode this distinction.

Each wired channel must use exactly one mechanism from the established one-mechanism-per-calculation-type taxonomy. Modelling one fold-in two ways at once is the defect that taxonomy exists to prevent, so a channel with no matching row requires amending the taxonomy before code lands, not inventing a second path.

A carried value must stamp its law-determined revision and re-confirm that stamp against the source context before it is trusted. The carry path is the one place a revision error compounds across years.

No ruling may authorise back-deriving ledger transactions from a pulled declared value: that invents transactions which never existed and corrupts the evidence bundle a revision is required to carry.

Revision resolution stays law-determined from modelo, filing year and period. A pulled record's stored revision id may only be asserted equal to that resolution, never injected as the selector.

## Implementation

DECISION OPEN. This record is scaffolded ahead of its ruling and is not yet authority for anything.

The ruling is the deliverable of the plan's `P02.S07`, and it cannot be authored before the plan's `P01` census establishes which channels could have consumed a pulled fact and what the denominator is. Naming the one currently-wired channel does not measure the scope of the gap, and a decision taken against an unmeasured denominator would encode this moment rather than the shape of the problem.

When the ruling lands it must open every implementing row in the same action, because a decision record ruling on code is not self-executing: otherwise the implementation debt has no owner and no row, while every later reader sees the ruling as in force and the tree carries the rejected behaviour.

Until then, treat the research document as the current state of knowledge and this record as a placeholder holding the question and the constraints any answer must satisfy.

## Rationale

## Consequences
