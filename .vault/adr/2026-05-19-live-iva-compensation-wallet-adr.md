---
tags:
  - '#adr'
  - '#live-iva-compensation-wallet'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
  - '[[2026-05-19-modelo-130-relation-regression-adr]]'
  - '[[2026-05-26-securestorage-repair-policy-adr-adjudication-research]]'
  - '[[2026-06-02-live-iva-compensation-consultation-research]]'
---
# `live-iva-compensation-wallet` adr: `AEAT wallet as primary IVA compensation authority` | (**status:** `accepted`)

> **Updated 2026-05-19**: Tax-domain identifier mentions in this ADR follow the Spanish-stem terminology authority. The wallet-adapter design (IvaCompensationWalletObservation, IvaCompensationReconciliationDecision, read-only Clave Movil flow, application-level reconciliation layer, blocking-decision contract, and live-write prohibition) is already Spanish-stem aligned and unaffected.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.


## Problem Statement

The Modelo 303 compensation-chain remediation can calculate a prior balance from
locally persisted filings, but AEAT maintains an authenticated `Cartera de
Cuotas a Compensar` for IVA. Treating the balance as only a local recurrence is
a critical backend omission because the AEAT-held wallet is the best available
state for casilla `110` and for the generation-period breakdown that governs
pending, applied, and remaining compensation.

The implementation needs a live read path that can fetch, persist, and reconcile
that wallet without performing any AEAT write operation.

The architectural risk is state ownership. The backend currently has local
filing observations and relation prefills, but it lacks a state model for an
AEAT-held balance that can differ from local reconstruction. Without that model,
the code can either over-trust local recurrence or silently overwrite operator
inputs with external state.

## Considerations

AEAT exposes `Modelo 303. Consulta de la cartera de cuotas de IVA a compensar`
from the Modelo 303 procedure page. The observed authenticated path is
`/wlpl/DAI3-RUTI/CarteraCuotas` on `www1.agenciatributaria.gob.es`.

AEAT's Pre303 guidance describes the wallet as visible in the result section and
as an independent service. The wallet shows compensation by generation exercise
and period, applied amounts, and pending amounts. Casilla `110` may be prefilled
from this state when AEAT has the data.

The value is authoritative evidence but not an automatic mutation. AEAT allows
the taxpayer to modify prefilled casilla `110`; the system must therefore
support explicit taxpayer override with provenance, while still treating live
wallet evidence as the primary source for unattended calculation and review.

Manual Cl@ve approval is expected. Cl@ve Móvil requires the operator to approve
the login on their device, so the driver must run as an interactive read command
or browser-backed workflow. Offline tests must cover parsing and reconciliation
using captured fixtures, not by faking authentication or bypassing the live gate.

## Constraints

The worktree is shared and must not use git stash, reset, checkout, or other
destructive worktree state mutation.

Live AEAT submission remains permanently forbidden. The wallet driver must be
read-only, must pass through the live-read gate, and must carry structural
`mode = "read"` records.

The implementation must preserve raw evidence, parser provenance, capture time,
authenticated identity, and source locator so later reviews can distinguish an
AEAT wallet observation from a local reconstruction or a taxpayer override.

The calculation engine must not read directly from the live adapter. Live access
is an evidence acquisition step. Calculation consumes a persisted reconciliation
decision so the same inputs reproduce the same result without requiring a fresh
Cl@ve approval.

## Implementation

Implement a dedicated read-only wallet adapter under the AEAT Sede outbound
boundary. The adapter will use the existing certificate and Cl@ve Móvil session
machinery, navigate to the wallet surface, parse rows into a strict
`IvaCompensationWalletObservation`, and persist the observation as external
state evidence.

Add an application-level reconciliation layer between evidence stores and the
calculation engine. The layer consumes:

- The latest valid AEAT wallet observation.
- Local Modelo 303 recurrence reconstructed from persisted filed observations.
- Optional explicit taxpayer override.

It produces an immutable `IvaCompensationReconciliationDecision` containing the
selected authority, selected amount, wallet amount, local amount, override
amount, divergence class, blocking status, stale-evidence status, reason, and
timestamps.

The calculation prefill order for Modelo 303 prior compensation must be:

1. Use a non-blocking reconciliation decision that selected the latest valid
   AEAT wallet observation for the authenticated taxpayer and target filing
   context.
2. Use an explicit taxpayer override only when the decision records the override
   reason and evidence.
3. Use local reconstruction from filed declarations only when no fresh wallet
   evidence exists and the decision marks the value as lower-confidence fallback.

Every run must reconcile the wallet total against local reconstruction when
both are available. Divergence must be surfaced as a blocking review state for
automatic filing output unless the user explicitly records the chosen authority
and reason.

Map the code changes to existing state boundaries:

- `src/aeat/adapters/outbound/aeat/sede/_iva_compensation_wallet.py` captures
  external wallet evidence.
- `src/aeat/adapters/outbound/aeat/sede/_schema.py` defines wallet evidence and
  rows as strict read-only records.
- `src/aeat/adapters/outbound/aeat/sede/_observation_store.py` persists raw
  wallet evidence and capture artefacts.
- `src/aeat/application/calculations/_iva_wallet_reconciliation.py` produces
  reconciliation decisions.
- `src/aeat/application/calculations/_binding_prefill.py` consumes only the
  selected non-blocking decision for `modelo-303-compensacion-pendiente-anteriores`.

## Rationale

This makes live AEAT state the primary calculation authority while preserving
the registry formula graph as the arithmetic authority for Modelo 303 outputs.
The driver reads evidence; it does not calculate hidden tax rules and does not
write back to AEAT.

Separating raw evidence from the effective binding decision keeps internal state
auditable. A wallet pull does not mutate the calculation result directly; it
creates evidence, reconciliation classifies that evidence against local state,
and only a non-blocking decision becomes a calculation input.

Keeping Cl@ve as an interactive approval path matches AEAT's security model and
the existing codebase's live-auth design. It avoids pretending the backend can
silently obtain a value that is intentionally protected behind taxpayer
authentication.

## Consequences

The IVA compensation-chain plan is not complete as a production backend until
the live wallet read, persistence, and reconciliation path exists.

Local previous-filing recurrence becomes a fallback and audit comparison, not
the primary source for casilla `110`.

The user experience must expose pending reconciliation states before calculation
or export. A blocked decision is not a validation warning that can be ignored by
the calculation layer; it prevents automatic filing output until reviewed.

The Modelo 130 relation-regression work remains related by runtime mechanism
only. It does not use the AEAT IVA wallet, but both plans validate that
cross-period evidence can be safely materialised into current-period bindings.

## First-period bootstrap

### Bootstrap scenarios

Three distinct bootstrap scenarios arise when the local compensation history
pre-dates the operator's use of this tool:

**True first-period**: The operator files their first ever Modelo 303 under this
NIF. By definition, casilla `110` (compensación pendiente de períodos anteriores)
is zero — there is no prior balance to carry forward. Run `iva-wallet seed
--amount 0` for that period. The seeded record carries `status=seeded` and
`expediente_id=manual-seed`, distinguishable from filed observations.

**Mid-career carry-in**: The operator has filed Modelo 303 before but is
switching to this tool. Their last M303 filed under the prior tool or directly
with AEAT left a non-zero carry-forward balance. Run `iva-wallet seed --amount X`
where `X` is the `compensación pendiente de períodos posteriores` from their
last filed M303. Subsequent periods see this seeded value as the prior balance.

**Mid-year tool switch**: As mid-career carry-in, but the switch happens
mid-calendar-year. The operator may have earlier intra-year periods already
filed. Each already-filed period should be seeded in chronological order so the
local recurrence chain is unbroken from the seeded anchor.

### LIVA art. 99.5 grounding for zero-first-period

Under LIVA (Ley 37/1992, de 28 de diciembre, del Impuesto sobre el Valor
Añadido) art. 99.5, the right to deduct IVA quotas is born in the tax period in
which the deductible quotas are incurred. A taxpayer filing their first Modelo
303 for a new registration period has no prior period in which an IVA
compensation balance could have been generated; therefore casilla `110` is
legally zero. This is not a missing-data state — it is a legally certain state.

Treating a seeded-zero or AEAT-wallet-zero for the first registered IVA filing
period as a blocking `missing` divergence would prevent automatic output
unnecessarily. The reconciliation layer maps this case to the non-blocking
`first_period_zero` divergence instead.

### Bootstrap state shape

A seeded compensation period persists as an `IvaCompensationPeriodState` with:

- `status = "seeded"` — distinguishes bootstrap from filed records in
  diagnostics.
- `expediente_id = "manual-seed"` — synthetic provenance marker.
- `source_observation_key = "303:seed:<year>:<period>"` — namespace-prefixed
  key for namespace integrity.
- `available_end_amount = <amount>` — the declared carry-forward value.
- `generated_amount = 0` — seeded records do not generate new compensation.

### Divergence variant: first_period_zero

`IvaCompensationDivergence` carries a `"first_period_zero"` literal that the
reconciliation function emits when:

1. The caller signals `is_first_iva_period=True`, AND
2. The effective amount from the selected authority source (wallet or seeded
   local recurrence) is zero (Decimal("0")).

The resulting `IvaCompensationReconciliationDecision` has `blocked=False` and
`selected_authority="aeat_wallet"` (when wallet is available) or
`selected_authority="local_recurrence"` (when only the seeded record is
available). Calculation proceeds without operator review because the zero value
is legally certain under LIVA art. 99.5.

### CLI seed contract

`aeat app modelo iva-wallet seed` is the sole surface for declaring bootstrap
balances. The command:

- Accepts `--amount 0` for the true-first-period case (legally zero, art. 99.5).
- Accepts `--amount X` for the carry-in case (X from the last prior-tool M303).
- Requires `--confirm` as an explicit acknowledgement gate.
- Refuses if a state already exists for the period (`IvaCompensationSeedConflictError`).
- Returns the persisted `status`, `filing_year`, `period`, and `amount` in the
  standard `--output` format.

## Status

Accepted and in force, and FOUNDATIONAL — this ADR establishes the AEAT wallet as the
primary IVA compensación authority, which is the ANCHOR of the unified
compensación-carry mechanism the bindings-architecture-unification sweep coalesces
onto. The future phase-2.3 (fold-in/carry) ADR unifies the wallet decision with the
registry `previous_filing` and FIFO carry paths around this anchor. This ADR is NOT
superseded; it is the carry anchor the phase ADRs name. (Canonical direction = the
phase + foundational ADRs, not a central apex doc.)
