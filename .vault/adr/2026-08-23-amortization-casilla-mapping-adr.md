---
tags:
  - '#adr'
  - '#amortization-casilla-mapping'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ac1e64630b54eb786c49b116f275177fce8993c4697199ec25018fc5f2602419'
related:
  - "[[2026-08-23-amortization-casilla-grounding-research]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
---

# `amortization-casilla-mapping` adr: `validated activity-asset schedule authority for 2025 amortization casillas` | (**status:** `accepted`)

## Problem Statement

Modelo 100 activity amortization currently has competing potential authorities: transaction-ledger expense categories and an asset/amortization schedule that does not yet prove fiscal deductibility or destination identity. The decision must establish one authoritative source for activity amortization, prevent duplicate claims, preserve the separate finca regime, and define the conditions under which automated output is permitted. Grounding is provided by `2026-08-23-amortization-casilla-grounding-research`.

## Considerations

- Activity material and intangible amortization require distinct destinations and legally validated source facts; `2026-08-23-amortization-casilla-grounding-research`.
- A recorded amortization amount alone cannot establish deductibility, destination, or compliance with the applicable annual limits; `2026-08-23-amortization-casilla-grounding-research`.
- Transaction-ledger amortization categories compete with asset-schedule ownership and cannot participate in a second aggregation path.
- Finca amortization has a different legal regime, source grain, calculation contract, and filing destination.
- The accepted connectivity architecture requires one resolver-owned authoritative source with explicit collision, absence, override, provenance, and persistence behavior; `2026-08-22-source-casilla-integration-adr`.
- The grounding supports only the 2025 activity-amortization revision window.

## Considered options

### Retain transaction-ledger authority

Continue deriving activity amortization from expense categories and treat the asset schedule as supporting data. Rejected because transaction rows do not prove the legal calculation or the material/intangible classification required by the destination.

### Sum transaction-ledger and asset-schedule amounts

Aggregate both paths into the filing result. Rejected because the paths represent competing evidence for the same filing fact and would permit double counting.

### Apply silent precedence

Accept both paths but prefer the asset schedule whenever it is present. Rejected because hidden precedence leaves duplicate authority intact and makes persisted provenance misleading.

### Make a validated asset schedule exclusively authoritative

Use a complete, legally validated activity-asset schedule as the sole automated producer, refuse competing transaction-ledger amortization claims, and retain finca amortization under its own contract. Accepted.

## Constraints

- Scope is limited to 2025 Modelo 100 activity amortization.
- Material assets produce casilla `0208`; intangible assets produce casilla `0227`.
- Every scheduled asset must carry and validate its legal classification, amortization method, applicable coefficient, useful life, service window, accumulated amortization basis, and any claimed special election.
- Missing, incomplete, internally inconsistent, or unreadable authoritative inputs fail closed; they never become zero, partial output, or caller-provided completion.
- Unsupported revisions and special elections lacking explicit grounding remain blocked or manual.
- Transaction-ledger categories representing activity amortization must be excluded before aggregation or refused as collisions. They are never summed with, silently subordinated to, or allowed to override the asset schedule.
- A complete authoritative source owns its outputs and refuses caller overrides.
- Finca amortization remains outside this source family and continues toward casilla `0131` through the finca slice.
- The accepted registry authority, resolver enrollment, provenance, secure persistence, and no-silent-under-declaration contracts remain stable parent boundaries and must be extended rather than bypassed.

## Implementation

Introduce a typed activity-asset amortization source contract for the 2025 revision. Its validated schedule computes the deductible annual amount per asset only after resolving all required legal classification, method, rate or useful-life constraint, in-service interval, accumulated-basis limit, and supported election facts. It then partitions authoritative output by legal material or intangible classification and exclusively owns casillas `0208` and `0227`.

Enroll that source through the existing registry and resolver architecture with build-time selector validation, explicit source ownership, authoritative provenance, encrypted calculation-revision persistence, and operator-visible refusal diagnostics. The resolver emits no filing value unless the complete schedule validates.

Remove transaction-ledger amortization categories from eligible aggregation for these destinations or reject their presence as a duplicate-authority conflict before calculation. Caller values targeting source-owned outputs are likewise refused.

Keep finca amortization as a separate typed source contract, resolver, and implementation slice for casilla `0131`; no activity-asset selector, schedule, or aggregation path is reused for it. Revision windows or special elections not grounded by this decision remain non-automated until separately adjudicated.

## Rationale

Exclusive validated-schedule ownership is the only option that makes the filing amount depend on the facts required to establish legal deductibility while preserving one authoritative path per casilla. Explicit exclusion or refusal closes duplicate authority instead of concealing it through arithmetic or precedence. A separate finca contract preserves the materially different source and calculation boundary identified by `2026-08-23-amortization-casilla-grounding-research` and composes with `2026-08-22-source-casilla-integration-adr`.

## Consequences

- Casillas `0208` and `0227` gain one auditable automated authority for the grounded 2025 activity scope.
- Material and intangible amortization cannot be conflated by an unclassified scalar entry.
- Duplicate transaction declarations and caller overrides become hard, diagnosable refusals.
- Partial schedules, unsupported revisions, unreadable records, and ungrounded elections remain manual or blocked rather than producing plausible but unsupported amounts.
- Existing transaction-ledger workflows must stop declaring activity-amortization categories for automated filing.
- The asset model, legal-parameter authority, schedule validation, resolver, persistence, and tests require coordinated implementation.
- Finca amortization remains visibly incomplete until its distinct casilla `0131` slice is delivered.
