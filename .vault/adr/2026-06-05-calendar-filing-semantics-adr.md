---
tags:
  - '#adr'
  - '#calendar-filing-semantics'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-04-calendar-live-filing-integration-research]]'
  - '[[2026-06-04-calendar-live-filing-integration-reference]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
  - '[[2026-06-05-calendar-filing-semantics-reference]]'
---

# `calendar-filing-semantics` adr: `calendar separates local filing state from AEAT evidence state` | (**status:** `accepted`)

## Problem Statement

The filing calendar must not collapse internal application readiness into real
AEAT submission evidence. A local verified or filed modelo record proves an
application lifecycle state. It does not prove that AEAT has received,
registered, accepted, or returned justificante evidence for that filing.

## Considerations

The calendar live filing integration decision already binds the overview
calendar to local projection of persisted live-read state. The calendar filing
semantics reference audits the implementation boundary where local
`ModeloRecord` state, external evidence, calculation observations, and
expedientes-derived events meet the calendar projection.

Operators need both axes. Local state answers whether the application has a
verified or internally filed revision. AEAT evidence state answers whether
submitted, accepted, registered, or justificante-backed evidence has been
observed or imported.

## Constraints

Overview calendar commands remain local-only and must not initiate AEAT live
reads.

AEAT-submitted and justificante-verified states require imported or persisted
official evidence. A local filing record without external evidence cannot be
shown as AEAT submitted.

This decision is a semantic continuation of the calendar live filing
integration decision. It narrows projection meaning without introducing a new
remote capability.

## Implementation

Calendar entries carry local application filing state and AEAT submission
evidence state separately. Local `ModeloRecord` data can mark local readiness or
internal filing. External evidence or persisted live observations can mark AEAT
submitted, accepted, or justificante verified states according to the evidence
kind available.

The overview application layer keeps the merge pure: callers supply already
loaded local records and persisted live observations, and the calendar projects
them into typed fields without contacting AEAT.

## Rationale

The split prevents a legally unsafe UI claim. Internal filing state is useful
for workflow continuity, but only AEAT evidence can ground statements about
submission or justificante verification.

## Consequences

Calendar output is more explicit and may show local-ready without AEAT evidence.
Operators must import or capture official evidence before the calendar can
display AEAT submitted or justificante verified state.

## Codification candidates

- **Rule slug:** `calendar-submission-state-requires-aeat-evidence`.
  **Rule:** Calendar projection must not label a modelo as AEAT submitted or
  justificante verified unless persisted official AEAT evidence supports that
  state.
