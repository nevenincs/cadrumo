---
tags:
  - '#adr'
  - '#amortization-casilla-mapping'
date: '2026-08-23'
modified: '2026-09-08'
body_schema: 'body-v1'
body_hash: 'sha256:14b9eb599b02b09a36d838cf2d0808e26e0acf5ed184ea845e8852d47828b954'
related:
  - "[[2026-08-23-amortization-casilla-grounding-research]]"
  - "[[2026-08-22-source-casilla-integration-adr]]"
---

# `amortization-casilla-mapping` adr: `validated activity-asset schedule authority for 2025 amortization casillas` | (**status:** `accepted`)

## Problem Statement

Modelo 100 activity amortization currently has competing potential authorities: transaction-ledger expense categories and an asset/amortization schedule that does not yet prove fiscal deductibility or destination identity. The decision must establish one authoritative source for activity amortization, prevent duplicate claims, preserve the separate finca regime, and define the conditions under which automated output is permitted. Grounding is provided by `2026-08-23-amortization-casilla-grounding-research`.

The previously shipped scalar activity-asset records, recorded annual amounts, repositories, and secure-storage namespace do not constitute that authoritative source. They provide neither a product acquisition path nor the validated calculation, resolver ownership, collision handling, or provenance required by this decision. Retaining that partial slice would present an incomplete persistence shape as a supported product contract. This amendment therefore withdraws the partial slice and makes end-to-end atomic delivery a condition of introducing its replacement.

## Considerations

- Activity material and intangible amortization require distinct destinations and legally validated source facts; `2026-08-23-amortization-casilla-grounding-research`.
- A recorded amortization amount alone cannot establish deductibility, destination, or compliance with the applicable annual limits; `2026-08-23-amortization-casilla-grounding-research`.
- Transaction-ledger amortization categories compete with asset-schedule ownership and cannot participate in a second aggregation path.
- Finca amortization has a different legal regime, source grain, calculation contract, and filing destination.
- The accepted connectivity architecture requires one resolver-owned authoritative source with explicit collision, absence, override, provenance, and persistence behavior; `2026-08-22-source-casilla-integration-adr`.
- The grounding supports only the 2025 activity-amortization revision window.

- A writerless persisted slice and its self-tests do not establish product reachability or source authority; `2026-09-04-reachability-burndown-reference`.
- The existing scalar records cannot be incrementally promoted into filing authority because their shape omits facts required by the accepted validation and destination contract; `2026-08-23-amortization-casilla-grounding-research`.
- Shipping storage, records, or API vocabulary ahead of the owning acquisition and calculation path creates an apparent compatibility contract around a non-authoritative representation.

## Considered options

### Retain transaction-ledger authority

Continue deriving activity amortization from expense categories and treat the asset schedule as supporting data. Rejected because transaction rows do not prove the legal calculation or the material/intangible classification required by the destination.

### Sum transaction-ledger and asset-schedule amounts

Aggregate both paths into the filing result. Rejected because the paths represent competing evidence for the same filing fact and would permit double counting.

### Apply silent precedence

Accept both paths but prefer the asset schedule whenever it is present. Rejected because hidden precedence leaves duplicate authority intact and makes persisted provenance misleading.

### Retain the scalar partial slice pending later completion

Keep the existing records, repositories, and secure namespace as preparatory infrastructure while adding the validated schedule in later changes. Rejected because the partial representation cannot satisfy the accepted legal-validation contract, has no product acquisition or resolver path, and would preserve a second apparent asset authority and compatibility surface.

### Withdraw the partial slice and land a validated asset schedule atomically

Use a complete, legally validated activity-asset schedule as the sole automated producer, refuse competing transaction-ledger amortization claims, and retain finca amortization under its own contract. Withdraw the earlier scalar records and persistence slice rather than preserving them as scaffolding or compatibility surfaces. Accept the replacement only when its acquisition, validation, calculation, persistence, resolver, collision, provenance, and filing path land together. Accepted.

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

- The withdrawn scalar activity-asset records, recorded-amount ledger, repositories, secure namespace, and API surface are not product contracts and must not be retained as compatibility aliases, dormant schemas, reserved namespaces, or migration scaffolding.
- A replacement activity-asset source must land as one coherent end-to-end slice: typed legally sufficient input, application acquisition, authoritative parameter resolution, schedule validation and computation, secure persistence, registry enrollment, resolver ownership, duplicate-authority refusal, calculation provenance, operator diagnostics, and behavioral verification.
- No subset of that slice may ship independently under a staged, deferred, implemented, ignored, or equivalent development disposition.
- A future replacement must not reinterpret payloads from the withdrawn scalar representation as validated schedule evidence. Any import from an external or historical source requires its own evidence-preserving acquisition and validation contract.
- The distinct finca amortization and bienes-inversión contracts remain outside this withdrawal and must not be renamed, merged, or reused to preserve the removed activity-asset surface.

## Implementation

Withdraw the existing scalar activity-asset and recorded-amortization slice in full, including its domain records, repositories, secure-storage declarations, public exposure, error registrations, and tests whose only purpose is to exercise that isolated slice. Do not leave aliases, readers, schema reservations, empty namespaces, or compatibility adapters behind. This withdrawal does not alter the separate finca amortization or bienes-inversión contracts.

Introduce the accepted 2025 activity-asset authority only as an atomic end-to-end source. Its typed acquisition boundary must collect every fact required by the validated schedule; its governed legal parameters and computation must establish the deductible annual amount and material or intangible destination; and its secure persistence must retain the authoritative inputs and resulting provenance needed for replay and audit.

Enroll the source through the existing registry and calculation resolver architecture in the same delivery. The resolver exclusively owns casillas `0208` and `0227`, refuses incomplete schedules, caller overrides, and competing transaction-ledger amortization claims, and emits operator-visible diagnostics and authoritative provenance. No filing value or partial product surface exists until that complete path is executable.

Keep finca amortization as a separate typed source contract, resolver, persistence path, and implementation slice for casilla `0131`. Keep bienes-inversión under its own legal and calculation boundary. Neither serves as a compatibility home for the withdrawn activity-asset representation.

## Rationale

Exclusive validated-schedule ownership is the only option that makes the filing amount depend on the facts required to establish legal deductibility while preserving one authoritative path per casilla. Explicit exclusion or refusal closes duplicate authority instead of concealing it through arithmetic or precedence. A separate finca contract preserves the materially different source and calculation boundary identified by `2026-08-23-amortization-casilla-grounding-research` and composes with `2026-08-22-source-casilla-integration-adr`.

Atomic delivery prevents persistence shape, public vocabulary, and synthetic round-trip tests from being mistaken for an authoritative filing capability. Withdrawing the scalar partial slice preserves the accepted validated-schedule direction without constraining its eventual legally sufficient model to an incomplete predecessor. It also keeps product truth in executable source ownership rather than in development-state classifications, consistent with `2026-09-04-reachability-burndown-reference`.

## Consequences

- Casillas `0208` and `0227` gain one auditable automated authority for the grounded 2025 activity scope.
- Material and intangible amortization cannot be conflated by an unclassified scalar entry.
- Duplicate transaction declarations and caller overrides become hard, diagnosable refusals.
- Partial schedules, unsupported revisions, unreadable records, and ungrounded elections remain manual or blocked rather than producing plausible but unsupported amounts.
- Existing transaction-ledger workflows must stop declaring activity-amortization categories for automated filing.
- The asset model, legal-parameter authority, schedule validation, resolver, persistence, and tests require coordinated implementation.
- Finca amortization remains visibly incomplete until its distinct casilla `0131` slice is delivered.
- The former scalar activity-asset representation and its secure-storage shape carry no compatibility or migration promise.
- Activity-asset amortization remains non-automated until the complete validated source is delivered atomically.
- Future implementation cannot claim progress by landing isolated records, repositories, namespaces, or self-tests without the owning application and filing path.
- Removal of the partial slice reduces duplicate vocabulary and prevents unvalidated recorded amounts from becoming de facto filing inputs.
- Finca amortization and bienes-inversión retain their existing independent ownership and behavior.
