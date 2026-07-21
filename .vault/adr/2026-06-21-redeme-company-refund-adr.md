---
tags:
  - '#adr'
  - '#redeme-company-refund'
date: '2026-06-21'
modified: '2026-06-21'
related:
  - '[[2026-06-21-redeme-company-refund-research]]'
  - '[[2026-06-19-iva-compensation-override-cli-adr]]'
---

# `redeme-company-refund` adr: `Modelo 303 refund (devolución) disposition: eligibility-gated election + refund-account axis` | (**status:** `proposed`)

## Problem Statement

Modelo 303 can only express a negative result as "a compensar" (carry forward).
`_DISPOSITION_SPEC[Modelo.M303].negative` is hardcoded to `COMPENSACION`; the 303
registry has no refund result casilla; the `iva_redeme_enrolled` profile axis is
persisted but not consumed. This blocks the defining provision of a REDEME taxpayer
— the monthly refund (devolución mensual, art. 30 RIVA / LIVA art. 116) — and the
last-period refund any taxpayer may elect. A company-prism persona verification
reproduced the gap. The research grounds the fix in the bundled AEAT diseño (Tipo
Declaración `D`; the art. 30 RIVA REDEME fichero field; IBAN/SWIFT-BIC fields).

## Considerations

- The refund is a taxpayer ELECTION (LIVA art. 116: the inscribed taxpayer "podrá
  solicitar la devolución"), not an automatic consequence of a negative result. The
  diseño expresses it as the Tipo Declaración code `D` plus the signed result plus a
  refund IBAN — not a new "importe a devolver" casilla.
- Eligibility is law-determined: `D` is permitted only when the taxpayer is REDEME-
  inscribed (any period) OR it is the last filing period of the year (4T / 12).
  Outside those, only `C` (compensación) is lawful.
- The monthly cadence for REDEME/SII taxpayers already works (the deadline engine
  consumes the axis). This ADR adds only the negative-result DISPOSITION, not the
  cadence.
- A refunded period must not also carry its credit forward — refund and
  compensación are mutually exclusive for a period. This must reconcile with the
  `iva-compensation-override` decision and the casilla-110 carry.

## Constraints

- **No live AEAT submission.** Refund is expressed locally in the fichero (Tipo
  Declaración `D` + REDEME field + IBAN); a human files outside the app.
- **Law-grounded gate.** A `D` election outside eligibility MUST be refused with a
  message naming art. 30 RIVA / LIVA art. 116; never silently downgrade or upgrade
  the disposition.
- **Regulatory values in the registry, BOE-grounded.** The REDEME fichero field and
  IBAN fields are added to the 303 registry/export grounded in the bundled diseño;
  the `legal_refs` cite RD 1624/1992 art. 30 and Ley 37/1992 art. 116.
- **Active-peer-WIP sequencing.** `_result_disposition.py`, `_export.py`, the 303
  casilla fragments, the completeness manifest, and `revision.toml` are under active
  peer WIP (recargo + disposition work). Enrolment of slices that touch those files
  MUST wait for the peer change to land; it must not edit them mid-flight.

## Implementation

- **Disposition election (layered, not a spec-table rewrite).** `ResultDisposition.
  DEVOLUCION = "D"` already exists; the disposition table documents `D` as a caller-
  layered election. The calc/export caller elects `D` for a negative result when the
  eligibility predicate holds and the operator chose refund; otherwise `C`.
- **Eligibility predicate.** `redeme_or_last_period(profile, period)` =
  `profile.iva_redeme_enrolled OR period.is_last_of_year`. A refund election failing
  it is refused (new error in the error-code registry + 4-locale message).
- **Refund-account axis.** A profile axis carries the refund IBAN (Spanish IBAN
  `ES` + 24 positions, validated) and optional SWIFT-BIC for `X` (foreign transfer);
  the export reads it when the disposition is `D`/`X`. A profile axis (stable per
  taxpayer, validated once) is preferred over a per-filing input.
- **Fichero fields.** Export writes Tipo Declaración `D`, the "inscrito en Registro
  de devolución mensual" field (`1`/`2` from the axis), and the IBAN/SWIFT-BIC block,
  per the diseño positions.
- **Carry reconciliation.** A refunded period sets the carry-forward / casilla-110-
  disponible to zero and records the disposition so a later period cannot also read
  it as a prior compensación; this composes with the iva-compensation decision (a
  period is refunded OR compensated, never both).
- **All affected profiles.** The election + gate apply to every entity type
  (natural_person, legal_entity, attribution_entity) — REDEME-inscribed every
  period, plus last-period for all. Ordinary non-REDEME non-final periods are
  unchanged (the regression control).

## Rationale

The refund is law-determined and already half-modelled (the `D` enum value, the
diseño fields, the cadence). The missing piece is a small, eligibility-gated
election layered by the caller plus the fichero fields — not a rewrite of the
disposition framework. Gating on `redeme_or_last_period` keeps the common
carry-forward path untouched and refuses unlawful refunds loudly. Sourcing the
refund IBAN from a validated profile axis keeps it stable and out of the per-filing
surface. Grounding every regulatory value in the bundled diseño + RD 1624/1992
art. 30 + Ley 37/1992 art. 116 satisfies the calculation-grounding and
safety-legal-gate disciplines.

## Consequences

- **Gain:** REDEME taxpayers (companies especially) can express the monthly refund
  they are legally required to request; any taxpayer can elect the last-period
  refund. The fichero carries the correct Tipo Declaración + REDEME field + IBAN.
- **Difficulty:** the enrolment touches files under active peer WIP; it must
  sequence behind that work, so it lands incrementally, not in one commit.
- **Pitfall:** loosening the gate would let a non-eligible taxpayer file an unlawful
  refund — the eligibility refusal and a regression-control persona guard against it.
- **Pitfall:** double-counting a refunded credit as a later compensación — the carry
  reconciliation closes it; a multi-persona cross-period test asserts a refunded
  period yields no casilla 110 downstream.

## Codification candidates

- **Source:** the eligibility gate (refund only when REDEME or last-period).
  **Rule slug:** `iva-303-refund-disposition-is-eligibility-gated`.
  **Rule:** A Modelo 303 negative-result `D` (devolución) election MUST be refused
  unless the taxpayer is REDEME-inscribed or it is the last filing period of the
  year, with a refusal grounded in RD 1624/1992 art. 30 / Ley 37/1992 art. 116;
  the default negative disposition stays `C` (compensación).
