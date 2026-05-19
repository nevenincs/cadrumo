---
tags:
  - '#adr'
  - '#live-iva-compensation-wallet'
date: '2026-05-19'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
  - '[[2026-05-19-modelo-130-relation-regression-adr]]'
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
