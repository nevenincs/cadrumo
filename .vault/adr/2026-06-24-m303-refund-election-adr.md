---
tags:
  - '#adr'
  - '#m303-refund-election'
date: '2026-06-24'
modified: '2026-06-24'
related:
  - '[[2026-06-21-m303-carry-reconciliation-adr]]'
---

# `m303-refund-election` adr: `Non-REDEME last-period refund opt-in election` | (**status:** `accepted`)

## Problem Statement

The Modelo 303 refund disposition (devolver `D` vs compensar `C`) is now a single
determined fact resolved at the calculate/file boundary by the part-2 disposition
authority (`resolve_modelo_result_disposition`); both the fichero `D` header and the
cross-period casilla-110 zero-carry derive from it, so they cannot disagree. The
eligibility gate `refund_disposition_available` already permits a refund in the last
filing period of the year (`4T`/`12`/`0A`) for ANY taxpayer, grounded in Ley 37/1992
art. 116 and RD 1624/1992 art. 30. But the resolver auto-upgrades `C` to `D` only for a
taxpayer inscribed in the Registro de Devolución Mensual (REDEME) — its standing,
always-on election. A non-REDEME taxpayer whose last-period result is a credit therefore
has NO way to elect the refund the law permits: the resolver forces carry-forward.

Removing the REDEME guard is not the fix. Auto-electing a refund for every last-period
credit would file a devolución the operator never chose — a silent wrong-filing, the
no-silent-under-declaration sibling (do not silently elect a refund). The missing piece
is an explicit, per-filing operator election.

## Considerations

- The refund choice is genuinely the operator's, per filing: carry the credit into the
  next year, or request it back. It is period-specific, unlike the standing REDEME
  inscription (which always refunds in its eligible periods).
- The disposition must stay ONE determined fact: the fichero `D` header and the
  zero-carry both read one resolver and must never disagree (the part-2 invariant). The
  election must flow through that one resolver, not a parallel path.
- Eligibility is law-determined and already implemented: the refund is available only in
  the last filing period of the year. An election outside that window is not a preference
  to honour silently — it is an operator error to surface.
- Defaulting matters: the safe, non-regressive default is carry-forward. A taxpayer who
  does nothing keeps today's behaviour.

## Constraints

- Reuses the stable, landed part-2 disposition authority (`resolve_modelo_result_disposition`)
  and the eligibility gate (`refund_disposition_available`) — both verified by M303-carry
  parts 1+2. No new legal determination is invented; only the operator-election input and
  one resolver branch are added.
- No schema or secure-storage decision is required here: the election is a non-sensitive
  per-filing closed value, NOT financial-identity data (unlike the sibling task's IBAN
  block). This keeps the change small and orthogonal.
- The CLI option for the closed election set MUST be a typed enum so the parse surface
  renders the accepted values, per the architecture-boundaries CLI-gate discipline.

## Implementation

- A closed `RefundElection` set — `COMPENSAR` (default, carry-forward) and `DEVOLVER`
  (request refund) — is the per-filing operator opt-in, threaded into the disposition
  resolver with default `COMPENSAR` so the no-election path is behaviour-identical to
  today.
- The resolver's refund-election branch upgrades `C` to `D` when EITHER the taxpayer is
  REDEME-inscribed (standing election, unchanged) OR the taxpayer explicitly elects
  `DEVOLVER` AND the period is eligible (`refund_disposition_available` true — the last
  filing period). REDEME and the explicit election are orthogonal; both route through the
  one resolver so the fichero `D` and the zero-carry stay consistent.
- An election of `DEVOLVER` for an INELIGIBLE period (not the last filing period) is
  REFUSED with an instructive, localised error (`ModeloRefundElectionNotEligibleError`)
  naming why — the refund is available only in the last filing period of the year — never
  silently carried, never silently refunded.
- The operator supplies the election through a typed `--disposition [devolver|compensar]`
  option on the calculate/file verb (default `compensar`), threaded through the filing
  action to the resolver.

## Rationale

Carry-forward as the default keeps the change non-regressive and avoids silently filing
an unrequested refund; the explicit `DEVOLVER` election is the operator's deliberate
choice; routing it through the single disposition authority preserves the fichero-`D` /
zero-carry consistency that part 2 established. Surfacing an ineligible election as an
instructive refusal — rather than silently downgrading to carry or silently filing the
refund — keeps the operator informed at the boundary. The eligibility window and the
legal basis (LIVA art. 116, RIVA art. 30) are already grounded and unchanged; this
decision adds only the operator-facing election and one resolver branch.

## Consequences

- **Gain:** a non-REDEME taxpayer can elect a last-period refund the law already permits,
  through the same single-fact resolver that guarantees the fichero header and the carry
  agree.
- **Gain:** the default (carry-forward) is unchanged, so existing filings and the REDEME
  path are behaviour-identical; the election is auditable per filing.
- **Difficulty:** the election is a new operator input on the calculate/file surface; its
  default and the eligibility refusal must be exercised by multi-persona tests so neither
  a silent refund nor a silent carry can slip through (last-period elect → `D` + zero
  carry; last-period no-election → `C`; mid-period election → refused; REDEME unchanged).
- **Pitfall:** removing the REDEME guard without an explicit election would silently file
  refunds — the refusal-plus-default-carry design is exactly what prevents it.

## Codification candidates

- **Rule slug:** `refund-election-is-explicit-and-eligibility-gated`.
  **Rule:** A Modelo 303 refund disposition (`D`) for a non-REDEME taxpayer MUST require
  an explicit per-filing operator election routed through the single disposition resolver
  and gated by `refund_disposition_available`; the default is carry-forward (`C`), and an
  election outside eligibility is refused with an instructive error — never a silent
  refund, never a silent carry.
