---
tags:
  - '#adr'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:50e34a8963c58909a0b67d856a44dac625aa7c002b493f106ff8e74ee3a0a5a6'
related:
  - "[[2026-09-21-assets-core-ownership-contracts-reference]]"
  - "[[2026-09-21-assets-core-lifecycle-and-integration-research]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
  - "[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]"
  - '[[2026-09-23-assets-core-proration-and-incentive-scope-research]]'
---

# `assets-core` adr: `IRPF asset identity, claim history, allocation, and filing projections` | (**status:** `accepted`)

## Problem Statement

The accepted 2025 activity-amortization authority requires an atomic validated
schedule but leaves four implementation-defining contracts open: asset identity
and acquisition linkage, forecast versus recorded history, Modelo 130
projection, and mixed-use-home allocation. Those commitments must be fixed
before the persisted model and public operations are introduced. Grounding is
in `2026-09-21-assets-core-ownership-contracts-reference` and
`2026-09-21-assets-core-lifecycle-and-integration-research`.

## Considerations

- The new source must remain distinct from IVA bienes-inversion and stock.
- Acquisition evidence has one canonical transaction lineage whose current ID
  may change after an ID-affecting edit.
- Forecasts, recorded claims, corrections, and filed history have different
  mutability and audit requirements.
- M130 needs an additive year-to-date expense component while M100 needs the
  annual amount once at distinct material and intangible destinations.
- Construction, land, ownership, and business use cannot collapse into one
  generic percentage.
- Existing source-mesh ownership and collision rules must be extended.

## Considered options

### Extend the IVA register

Rejected. It excludes valid IRPF-only acquisitions and would merge independent
legal lifecycles.

### Introduce one universal asset aggregate

Rejected. It makes tax-specific eligibility, history, and corrections implicit
and contradicts the accepted separation of IVA bienes-inversion.

### Use transaction categories plus manually entered annual charges

Rejected. It retains the proven full-acquisition-cost path and cannot validate
schedule authority, accumulated basis, or duplicate claims.

### Use a separate IRPF aggregate with shared acquisition identity and projections

Proposed. A dedicated immutable IRPF asset revision references the canonical
acquisition transaction lineage, owns typed allocation and schedule inputs, and
records non-overlapping tax-period claims separately. One computed schedule
projects those same effective claims to M100 and M130. Scoped collision refusal
blocks competing depreciation deductions without deleting acquisition evidence.

## Constraints

- The complete 2025 material/intangible source must land atomically under
  `2026-08-23-amortization-casilla-mapping-adr`.
- IVA identity and regularization remain governed by
  `2026-07-01-iva-bienes-inversion-regularizacion-adr`.
- Sensitive facts use encrypted profile persistence and append-only corrections.
- Unknown opening history, missing allocation, unsupported authority, and
  collision are explicit incomplete states, never zero.
- No frontend owns depreciation arithmetic or imports the other frontend.
- Initial filing-grade support is tax year 2025, common-regime direct normal or
  simplified estimation, and material and intangible activity assets. Other
  years and regimes remain unsupported until separately grounded and enrolled.

## Implementation

Define a dedicated IRPF activity-asset aggregate identified independently from
its required canonical acquisition transaction linkage. The linkage stores the
transaction ID observed by the asset revision and resolves later IDs through
the existing edit-lineage chain. An ID-affecting acquisition correction marks
dependent asset revisions and unfiled claims stale; the operator must append a
superseding asset revision after reviewing the changed tax facts. Historical
claims keep the original transaction ID, lineage event, and evidence
fingerprint needed for reproduction. No second transaction identity is minted.

The first supported acquisition shape is one primary purchase transaction with
one canonical invoice/evidence relationship. Split or multiple payments,
capitalizable ancillary-cost transactions, produced assets, and historical
acquisitions without canonical evidence refuse as unsupported rather than being
silently folded into that primary transaction.

Asset revisions are immutable and carry acquisition, affectation, in-service,
classification, regime, method, allocation, cost components, residual value,
and opening-history facts. Corrections append a superseding revision.

The authority-backed schedule is a deterministic forecast, not a recorded
claim. Only the explicit application operation to record an amortization charge
creates a claim; calculate, preview, verify, and export are read-only consumers
and never create charges. A claim identity is derived from asset revision,
schedule fingerprint, authority generation and source references, tax year,
non-overlapping covered date interval, and charge amount. The claim also records
the creating operation and any calculation or filing revision that later
consumes it.

An exact replay returns the existing claim. A replay for the same asset and
covered interval with different amount, schedule, authority, or source refuses
as a conflict. A correction appends a superseding claim; only the latest valid
claim in each non-overlapping interval is effective for accumulated and
remaining basis. Superseded claims remain auditable and never consume basis a
second time. M130 and M100 reference the same effective claim IDs: form-specific
projections are not claims and do not create additional deductions. Unknown
opening history blocks a complete schedule. Disposal stops future charges
without claiming disposal gain or loss support.

Every stored cost declares its basis as whole-property cost; a pre-allocated
transaction amount is not accepted as that basis. Home allocation uses explicit
ownership treatment, construction cost, land cost, office area, and total area.
Sole or fractional direct ownership uses its validated legal share once before
the office-area ratio. Community or spousal property is a distinct ownership
mode and is never blindly multiplied by one half; it remains unsupported until
its applicable authority resolver is enrolled. Other ownership modes refuse.
The schedule excludes land and applies ownership and business-area allocation
exactly once. Existing transaction `business_pct`, category usage ratios, and
household-utilities multipliers are evidence consistency checks only and cannot
be applied again to the asset base.

For M130, the existing casilla-02 expense resolver remains the sole owner and
adds effective asset-claim observations to ordinary deductible-expense
observations before its one cumulative year-to-date sum. Asset integration does
not replace ordinary expenses and does not register a second casilla owner.
For M100, the asset source exclusively owns 0208 for material assets and 0227
for intangible assets under the parent decision.

A canonical acquisition transaction retained only as evidence is valid. A
transaction that also routes an amortization-labelled deductible amount for the
same asset/year is a competing claim and blocks filing-grade calculation. The
diagnostic identifies the asset, transaction, category, period, and remediation:
retain the acquisition evidence but reclassify or reverse only its competing
depreciation treatment. Unrelated ordinary expenses and stock remain outside
the collision scope.

The annual lawful charge is calculated at exact Decimal precision. The
in-service date is the first included service day; the out-of-service boundary
is the first excluded day. A disposal or withdrawal input must resolve to that
exclusive boundary before filing-grade calculation. Every recorded claim,
partial-year M100 annual projection, and M130 period or year-to-date projection
multiplies the full-year charge by the actual service days in the intersection
of its covered interval and that half-open service window, divided by 365 or 366
calendar days for the tax year. Only emitted claim, period, annual, and
remaining-base amounts use canonical euro-cent rounding; the final charge is
capped to the remaining lawful base. IVA keeps its own record and shares only
canonical acquisition lineage. Implementation follows
`2026-09-21-assets-core-ownership-contracts-reference`.

## Rationale

Only the separate aggregate distinguishes legal identity from evidence identity
while preserving the accepted IVA boundary. Separating deterministic forecasts
from append-only claims provides both recalculation and auditability. A single
schedule with annual and cutoff projections eliminates duplicate calculators,
and typed home components preserve the allocation facts required by
`2026-09-21-assets-core-lifecycle-and-integration-research`.

## Consequences

- Product code gains one authoritative IRPF asset lifecycle and one acquisition
  evidence link without turning the IVA register into a universal store.
- Recalculation can change forecasts without rewriting recorded or filed claims.
- M130 and M100 reference the same effective claims without recording or
  consuming depreciation twice.
- Mixed-use homes fail closed when land, ownership, area, or supported ownership
  treatment is missing; common spousal property is not approximated.
- The persisted shape and public operations become a long-lived contract and
  therefore must not land before this proposal is accepted.
- Disposal gain or loss, vehicles, foral regimes, inherited property, rental
  income, and ungrounded incentives remain outside this decision.
