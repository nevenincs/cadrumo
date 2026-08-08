---
tags:
  - '#adr'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:e010c1d08540ed087fea38e5503170d15892ba259eec30f7cd9b640c070e84a3'
related:
  - "[[2026-08-08-synced-history-consumption-research]]"
---

# `synced-history-consumption` adr: `Which pulled AEAT facts are calculation inputs` | (**status:** `proposed`)

## Problem Statement

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
