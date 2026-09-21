---
tags:
  - '#adr'
  - '#assets-core'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:1f61f70e670f348b64d2a96a099a2bbc800a068b1d578d475c9ce9b3b79605cc'
related:
  - "[[2026-09-21-assets-core-ownership-contracts-reference]]"
  - "[[2026-09-21-assets-core-lifecycle-and-integration-research]]"
  - "[[2026-08-23-amortization-casilla-mapping-adr]]"
  - "[[2026-07-01-iva-bienes-inversion-regularizacion-adr]]"
---

# `assets-core` adr: `IRPF asset identity, claim history, allocation, and filing projections` | (**status:** `proposed`)

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
- Acquisition evidence has one canonical transaction identity.
- Forecasts, recorded claims, corrections, and filed history have different
  mutability and audit requirements.
- M130 needs a year-to-date view while M100 needs the annual amount once.
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
acquisition transaction, owns typed allocation and schedule inputs, and records
claims separately. One computed schedule projects the annual amount to M100 and
the year-to-date amount to M130. The resolver refuses competing transaction
amortization claims.

## Constraints

- The complete 2025 material/intangible source must land atomically under
  `2026-08-23-amortization-casilla-mapping-adr`.
- IVA identity and regularization remain governed by
  `2026-07-01-iva-bienes-inversion-regularizacion-adr`.
- Sensitive facts use encrypted profile persistence and append-only corrections.
- Unknown opening history, missing allocation, unsupported authority, and
  collision are explicit incomplete states, never zero.
- No frontend owns depreciation arithmetic or imports the other frontend.

## Implementation

Define a dedicated IRPF activity-asset aggregate identified independently from
its required canonical acquisition transaction reference. Asset revisions are
immutable and carry acquisition, affectation, in-service, classification,
regime, method, allocation, cost components, residual value, and opening-history
facts. Corrections append a superseding revision.

The authority-backed schedule is a deterministic projection, not a recorded
claim. Claims append separately with their asset revision, schedule fingerprint,
tax year, amount, and calculation or filing revision provenance. Unknown opening
history blocks a complete schedule. Disposal stops future charges without
claiming disposal gain or loss support.

Home allocation uses explicit ownership share, construction cost, land cost,
office area, and total area. The schedule excludes land and applies ownership
and business-area allocation exactly once. Generic household-utilities ratios
are not reused.

One resolver owns the asset-derived deduction. It exposes annual and cutoff
year-to-date views from the same schedule, refuses transaction-ledger
amortization collisions, and feeds M100 and M130 through existing typed source
mechanisms. IVA keeps its own record and may share only the canonical
acquisition transaction identity. Implementation follows
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
- M130 and M100 consume consistent views and reject duplicate transaction claims.
- Mixed-use homes fail closed when land, ownership, or area evidence is missing.
- The persisted shape and public operations become a long-lived contract and
  therefore must not land before this proposal is accepted.
- Disposal gain or loss, vehicles, foral regimes, inherited property, rental
  income, and ungrounded incentives remain outside this decision.
