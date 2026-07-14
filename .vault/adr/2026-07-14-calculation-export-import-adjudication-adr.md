---
tags:
  - '#adr'
  - '#calculation-export-import-adjudication'
date: '2026-07-14'
modified: '2026-07-14'
related:
  - "[[2026-07-14-calculation-export-import-adjudication-research]]"
  - "[[2026-05-03-calculation-truth-registry-pending-adr]]"
  - "[[2026-07-14-calculation-export-import-adjudication-reference]]"
---

# `calculation-export-import-adjudication` adr: `Export and import backlog admission boundary` | (**status:** `proposed`)

## Problem Statement

Legacy plans and capability matrices identify absent export layouts and
declaration-extraction profiles, but absence is not a product requirement.
Current code already provides one validated registry authority, one generic
registry-driven export renderer/parser pair, and one generic declaration-PDF
parser. A lifecycle decision is needed to prevent stale wording, available
source artefacts, or checklist gaps from entering the implementation backlog
without proof that production work is warranted.

## Considerations

- The accepted central calculation-registry ADR remains the stable parent
  architecture: reviewed registry data feeds canonical generic engines. This
  decision governs backlog admission and does not replace that architecture.
- Current evidence authorizes zero candidate implementations. Modelo 037 is
  retired; Modelos 309 and 360 lack an outbound mandate; the other export
  candidates remain conditional and authority-windowed; extraction candidates
  require real sanitized specimens except Modelo 200's delivered-equivalent
  submitted-file path; and Modelo 100 exercise 2026 lacks current authority.
- Record designs prove only the formats and periods to which they apply. They do
  not prove product mandate, historical coverage, or declaration-PDF geometry.
- Per-Modelo renderers, submitted-file parsers, declaration-PDF parsers,
  registry authorities, and schema stores would duplicate existing ownership.

## Considered options

### Implement every absent layout or profile

Reject. This converts implementation state and source availability into product
scope, encourages unsupported temporal extrapolation, and invites duplicate
Modelo-specific engines.

### Treat the legacy omnibus plan as the backlog

Reject. Historical wording does not account for retirement, delivered generic
behavior, current authority windows, or later accepted ownership decisions.

### Admit candidates through a four-condition gate

Choose. A candidate enters a successor implementation plan only when all four
conditions are proven: a current product or filing mandate requires it;
official authority covers the exact revision and period; the canonical generic
engine has a genuine current gap; and the candidate is neither retired nor
blocked by unavailable real evidence.

## Constraints

- No production source, tests, or registry data may change for a candidate until
  it passes all four conditions.
- Applicable authority must be registered for the exact revision window; later
  designs must not be extended backwards by assumption.
- Export work must use real golden payloads and the existing generic round trip.
  Declaration extraction must use real sanitized filed bytes and the existing
  generic parser. Schema self-consistency is not sufficient evidence.
- The sealed archive remains a separate persistence boundary, not an AEAT file
  or declaration format.
- A new ADR is required only if adjudication discovers a genuinely new engine,
  authority source, or ownership boundary. Registry-data additions within the
  accepted architecture do not require another architectural decision.

## Implementation

Each bounded candidate receives an independent evidence-backed disposition.
The adjudication records mandate, exact authority window, current generic-path
state, real evidence, retirement status, and next action. Only candidates that
pass every condition may be named in a successor implementation plan, and that
plan may add reviewed registry data and real-behavior coverage only through the
canonical generic engines. When no candidate passes, the final audit records
zero successor handoff and no implementation plan is created.

## Rationale

The gate preserves the accepted central architecture while closing a lifecycle
gap that architecture intentionally did not decide: which optional capabilities
deserve backlog admission now. It distinguishes mandate from mere feasibility,
forces exact temporal and artefact grounding, recognizes delivered-equivalent
behavior, and prevents reconciliation from manufacturing duplicate code. The
companion research and Reference establish that all current candidates fail at
least one condition, so truthful application of the decision presently yields
no production work.

## Consequences

- The backlog reflects proven current product gaps instead of absent optional
  data or stale plan language.
- Candidate decisions remain auditable and can change when a mandate, authority,
  or real specimen becomes available.
- The outcome may legitimately be no successor implementation work; visible
  inactivity is an accepted consequence of evidence-based admission.
- Adjudication adds review effort and can delay otherwise feasible work while
  mandate or evidence is unavailable.
- Future implementations remain constrained to registry data and canonical
  engines unless a separately approved ADR changes authority or ownership.
