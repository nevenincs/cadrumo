---
tags:
  - '#adr'
  - '#m303-carry-reconciliation'
date: '2026-06-21'
modified: '2026-06-21'
related:
  - "[[2026-06-21-redeme-company-refund-adr]]"
  - "[[2026-06-21-redeme-company-refund-research]]"
---

# `m303-carry-reconciliation` adr: `Modelo 303 refunded period generates zero carry-forward: disposition feeds compensacion-disponible` | (**status:** `proposed`)

## Problem Statement

The Modelo 303 refund (devolución, Tipo de declaración `D`) election now emits the
refund in the fichero header for a REDEME company's negative period, but the
period's credit is STILL carried forward. The end-of-period available credit
`iva.compensacion-disponible-fin-periodo` is generated unconditionally from the
negative result — `available = casilla 87 (pendiente posterior) + max(0, -casilla
69 (resultado))` — so a refunded period both requests the money back AND carries
the same credit into the next period's casilla 110. The credit is double-counted:
the fichero says "devolución" while the cross-period carry says "compensación".
This is the pitfall the refund ADR flagged. The grounding pass confirmed it is a
real gap reachable through the app's own file-then-recalculate flow.

## Considerations

- The carry is produced by TWO mechanisms, neither disposition-aware: a registry
  FORMULA computes `iva.compensacion-disponible-fin-periodo` on the calculate path
  (the value persisted in `CalculationRevision.observations` and read next period),
  and `derive_303_compensation_available` (`domain/iva_compensation/_carry_forward`)
  recomputes the same quantity on the filed-history path
  (`iva_compensation_state_from_filed_observation`). This duplication touches the
  one-canonical-aggregation-mechanism discipline; the disposition signal must reach
  whichever mechanism is authoritative for the carry the next period reads.
- The disposition (refunded vs carried) is currently determined only at EXPORT time
  (`_apply_refund_election`), from the profile REDEME axis + the eligibility gate.
  It is not a persisted fact, so the calculate/carry path cannot see it.
- For a REDEME taxpayer the refund is DETERMINISTIC (the inscription is the standing
  monthly-refund election), so "refunded" is recomputable from
  `(redeme_enrolled, modelo == 303, result < 0, eligible)` wherever the redeme axis
  is in scope — it need not be an operator choice.
- The 303 registry has NO devolución casilla; the refund is the disposition, not a
  box. So the filed-observation casillas alone cannot recover "was this refunded" —
  the AEAT-pull path would need the justificante Tipo de declaración, a separate
  recovery concern from the app's own local-file path.

## Constraints

- **No double mechanism drift.** Whatever carries the disposition into the carry
  derivation must keep the calculate path and the filed-history path in agreement
  (the pull-equals-calculate discipline); a fix on one mechanism only re-opens the
  drift.
- **Behaviour-preserving default.** The carry derivation's new disposition input
  MUST default to "carried" (the current behaviour), so every existing non-refund
  filing and every carry regression test is unchanged; only a refunded period zeroes
  the generated carry.
- **Grounded, not heuristic, for official data.** The AEAT-pull path must recover
  the disposition from the filed artefact (justificante Tipo de declaración), never
  from the CURRENT profile's REDEME flag applied to a historical filing — a taxpayer
  may not have been REDEME in the pulled year. The local-file path may recompute it
  from the revision's own profile context.
- **Carry-forward correctness is cross-compounding.** A wrong carry injects into
  every later period that folds it in (the carried-observations discipline), so the
  fix needs a multi-persona cross-period regression, not a single-period assertion.

## Implementation

- **Disposition becomes a determined fact at calculate/file time.** Compute the
  M303 negative-result disposition (`devolver` vs `compensar`) once from the profile
  REDEME axis + the eligibility gate at the calculate/file boundary, persist it on
  the revision's observation context, and have BOTH the export (fichero `D`) and the
  carry derivation read the same determined fact — collapsing the export-only
  determination into one shared source.
- **Carry derivation gains a refunded input.** `derive_303_compensation_available`
  and the registry compensación-disponible derivation take a `refunded` signal;
  when refunded, the generated component is zero (`available = posterior` only, which
  for a full monthly refund is also zero), so the refunded period carries nothing.
- **Two paths, one contract.** The local-file path supplies `refunded` from the
  determined disposition; the AEAT-pull path recovers it from the justificante Tipo
  de declaración. A parity regression asserts both paths agree for a shared period.
- **Reconcile with the IVA-wallet decision.** A refunded period must also not be
  read as a prior compensación by the wallet reconciliation (casilla 110); the
  determined disposition feeds that gate so a period is refunded OR compensated,
  never both.

## Rationale

The grounding pass established the gap is real and that its root is a missing fact:
the disposition lives only at export, so the carry cannot honour it. Making the
disposition a determined fact shared by the export and the carry is the minimal
change that keeps the two carry mechanisms in agreement and the common
carry-forward path untouched. Defaulting the carry input to "carried" makes the
change non-regressive; recovering official-data disposition from the justificante
(not the live profile) keeps historical pulls correct. Grounded in RD 1624/1992
art. 30 / Ley 37/1992 art. 116 (a refunded credit is returned, not carried).

## Consequences

- **Gain:** a REDEME company's refunded period stops double-counting its credit; the
  fichero disposition and the cross-period casilla 110 finally agree.
- **Difficulty:** the disposition must be threaded to two carry mechanisms and two
  file paths; the AEAT-pull recovery needs the justificante Tipo de declaración,
  which is a parsing concern beyond the local-file fix.
- **Pitfall:** fixing only the calculate-path formula (or only the history function)
  re-opens pull-vs-calculate drift; the parity regression guards it.
- **Pitfall:** applying the current profile's REDEME flag to a historical pulled
  filing would mis-zero a legitimately-carried prior period; the official path must
  read the filed artefact.

## Codification candidates

- **Rule slug:** `m303-refunded-period-carries-nothing`.
  **Rule:** A Modelo 303 period filed as a refund (Tipo de declaración `D`) MUST
  generate zero `iva.compensacion-disponible-fin-periodo`; the disposition that
  drives the fichero `D` and the disposition that drives the cross-period carry MUST
  be the one determined fact, never computed twice and never allowed to disagree.
