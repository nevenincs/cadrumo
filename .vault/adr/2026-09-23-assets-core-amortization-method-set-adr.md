---
tags:
  - '#adr'
  - '#assets-core'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:11d21ce8068416883663dfdf88e6c34026d3931b3a2e33bcff86d7c01f69515b'
related:
  - "[[2026-09-23-assets-core-amortization-method-set-research]]"
  - "[[2026-09-21-assets-core-lifecycle-contract-adr]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
---



# `assets-core` adr: `IRPF activity amortization method set and election contract` | (**status:** `accepted`)

## Problem Statement

The 2025 activity-asset engine enrols only the linear table maximum and the
EUR 300 election. `2026-09-23-assets-core-amortization-method-set-research`
shows that the normal modality admits four further LIS art. 12.1 methods, the
art. 12.2 intangible limits and several incentives, while the simplified
modality restricts material assets to the linear table. The current forecast
also receives its regime, class and method in a per-call selector, although
`2026-09-21-assets-core-lifecycle-contract-adr` requires the immutable
revision to carry classification, regime and method. A method whose charge
depends on the asset's position in its life cannot be chosen afresh on every
call. Linear charges also apply the rate to a base that still includes the
residual value, which RIS art. 3.2 excludes.

## Considerations

- A method is an election about the asset, and changing it must leave an
  auditable, superseding revision.
- Method admission differs by regime, asset kind and table class, and it
  belongs in typed registry authority rather than in Python branches.
- Constant percentage, sum of digits and plans depend on prior effective
  claims and on the in-service anniversary, not only on the covered interval.
- Free-depreciation amounts are chosen per tax period, within legal limits.
- The accepted day-count proration governs linear allocation. AEAT examples
  prorate by months; see the research record.

## Considered options

### Extend the per-call selector with method parameters

Rejected. It keeps the lifecycle-ADR deviation, allows a different method on
every forecast, and cannot reproduce which election a claim followed except
through the selector the caller happened to send.

### Carry the election on the immutable revision

Accepted. The revision owns regime, table class, method, its parameters and
the asset's new or used condition. A method change is a correction revision,
whose admissibility can be judged against the claims recorded under earlier
revisions.

## Constraints

- Filing-grade support remains tax year 2025, common-regime direct
  estimation, and material and intangible activity assets.
- Each admission, coefficient, threshold, weighting and window is a Modelo 100
  2025 registry parameter with legal references and AEAT manual citations.
  Absent registry rows mean unsupported. A row valued zero means excluded by
  law and refuses with its provision.
- No caller-authored rate or amount is accepted except an elected coefficient
  or free-depreciation amount bounded by registry authority, or a plan
  distribution bound to its administrative approval.
- There is no released compatibility floor; persisted histories without an
  election are not migrated.

## Implementation

`ActivityAssetRevision` gains a required amortization election (regime,
authority class key, method, method parameters, and optional ERD and
incentive evidence) and an acquired condition (new or used, with a building
construction date for used buildings). The per-call authority selector is
deleted. A forecast takes the asset, the covered interval and, for free
methods only, the elected amount.

The resolver reads the revision's election against the 2025 Modelo 100
parameters. It checks method admission for the regime and asset kind, class
admission for constant percentage and sum of digits, coefficient bounds
(maximum coefficient, the coefficient implied by the maximum period, the
multi-shift formula, the used-asset double maximum, ERD double maximum),
weighting bands with the 11% floor, R&D and charging windows, and the EUR 10
million ERD turnover threshold. It emits one typed schedule authority.

The amortizable base is the allocated basis minus residual value for every
method. Charges are exact Decimal and are rounded to cents at emission, then
capped at the remaining base.

- Linear, indefinite-life intangible, goodwill and R&D building methods
  charge the base times the resolved annual rate, times the service days in
  the interval over the tax-year days. This is the lifecycle ADR's rule.
- Constant percentage charges the percentage times the pending value at the
  start of the tax year (base less opening history and effective claims before
  that year), prorated the same way. In the tax year in which the useful life
  implied by the elected coefficient ends, the whole pending value is spread
  over the service days up to that end.
- Sum of digits assigns digits to life years that begin on the in-service
  date and on each anniversary, descending or ascending. A life year's quota
  is spread over its own days. This is the only reading in which a
  mid-year start keeps both the elected period and a total equal to the base.
- An approved plan charges the distribution the approval fixes for the tax
  year, spread over that year's service days. It applies only to tax years
  ending after the plan's submission.
- A definite-life intangible spreads the base over the days from in-service to
  the evidenced end of its useful life.
- The EUR 300, R&D and charging-infrastructure free methods claim the elected
  amount, which cannot exceed the remaining base; the EUR 300 annual cap check
  is unchanged.

A claim's election is that of the revision it references. Within one tax year
every effective claim for an asset must share one election fingerprint. A
correction may change the method only from a tax-year boundary. Constant
percentage and sum of digits are admissible only when no effective claim
under another election exists for the asset, because their formulas run
from the start of amortization.

Typed refusals cite their provision: the justified-amount method (LIS art.
12.1.e) because this decision's parent refuses caller amounts it cannot
validate; job-creating ERD free depreciation (LIS art. 102) and renewable
self-consumption free depreciation (LIS DA 17a) because no canonical average
workforce fact exists; electric vehicles (LIS DA 18a.1) because vehicles are
outside the accepted asset scope; sociedades laborales and associative
priority farms (LIS art. 12.3.a/d) because they are entity regimes; and ERD
acceleration of indefinite-life intangibles and goodwill because LIS art.
103.5 and the AEAT manual disagree on its scope.

## Rationale

Carrying the election on the revision is the accepted lifecycle contract. It
gives each life-dependent method a stable input, and it makes a change of
method an explicit, reviewable correction. Registry admission tables keep
regime and class restrictions as cited authority, so a new year or a legal
change is data, not code.

## Consequences

- CLI and TUI forecasts no longer accept an authority selector; revision JSON
  carries the election, and existing unit and acceptance fixtures must author
  it.
- Linear charges with a non-zero residual value decrease to the lawful base.
- The day-count versus monthly-proration divergence from AEAT examples
  remains a recorded inconsistency, to be resolved by amending the lifecycle
  ADR rather than by this record.
- Each refused incentive names the exact missing fact or conflicting source
  that would have to change before it can be enrolled.
