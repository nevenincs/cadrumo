---
tags:
  - '#adr'
  - '#iva-compensation-chain'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-iva-compensation-chain-audit-research]]'
  - '[[2026-04-12-modelo-303-390-adr]]'
  - '[[2026-04-17-modelo-303-formulas-adr]]'
  - '[[2026-05-19-modelo-130-relation-regression-adr]]'
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
  - '[[2026-05-19-live-iva-compensation-wallet-adr]]'
---

# `iva-compensation-chain` adr: `modelo 303 and 390 compensation balance remediation` | (**status:** `accepted`)

> **Updated 2026-05-19**: Tax-domain identifier mentions in this ADR follow the Spanish-stem terminology authority. The compensation-chain decisions (Modelo 303 casilla identities 110, 78, 87, 69; the Modelo 390 annual reconciliation fields 97 and 662; the source_period_offset_from_target previous-filing selector; and the registry-as-arithmetic-truth rule) are unaffected and require no edit.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.


## Problem Statement

The IVA calculation chain treated the prior-period compensation balance as the old Modelo 303 casilla `67` and calculated the final result as casilla `71`. The current bundled AEAT 2025 record design declares the relevant Modelo 303 result fields as casilla `110` for pending prior-period compensation, `78` for the amount applied in the period, `87` for prior-period compensation still pending for later periods, and `69` for the final autoliquidacion result.

The existing previous-filing resolver also skipped bindings that declare singular `source_output` rather than plural `source_casillas`. That makes the self-referential carry-forward binding inert when the source value is an already computed Modelo 303 output. The declared relation then asks for multiple static source periods instead of the single previous quarter, so a second-quarter calculation can incorrectly require current-quarter or future-current-period observations.

Modelo 390 has a related annual gap. It reconciles annual devengada, deducible, and regimen-general result totals from the four Modelos 303, but it does not expose the annual compensation result fields that the bundled record design identifies as casilla `97` and casilla `662`.

## Considerations

The grounding sources are already declared in the resource catalogues: LIVA art. 99 for the legal compensation right and four-year carry-forward limit, RIVA art. 71 for IVA autoliquidacion and annual summary obligations, the bundled AEAT Modelo 303 2025 record design for casillas `110`, `78`, `87`, and `69`, and the bundled AEAT Modelo 390 2025 record design for casillas `97` and `662`.

The remediation must not introduce a second hard-coded compensation engine. The registry formulas remain the source of arithmetic truth; runtime changes should only make declared previous-filing selectors resolvable.

The tests must avoid mirrored business logic. Numeric examples should instantiate the official record-design formulas directly: for Modelo 303, `[87] = [110] - [78]` and `[69] = [66] + [77] - [78] + [68] + [108]`; for the currently modelled scope, unmodelled addends default to zero. For Modelo 390, the record design distinguishes final-period compensation in `97` from generated-in-year pending compensation not included in `97` in `662`.

## Constraints

The worktree is shared and must not use git stash, reset, checkout, or other destructive worktree state mutation.

The `vault plan` CLI was not available in the local environment, so the plan artifact must be created from the Vaultspec template with stable row identifiers and the limitation recorded.

The current Modelo 303 registry does not yet model every current record-design addend for casilla `69`, notably casillas `77`, `68`, and `108`. This ADR scopes the fix to the active compensation chain and preserves those addends as zero until their own grounded formulas are implemented.

## Implementation

Add previous-filing selector support for a singular `source_output` with an optional `source_period_offset_from_target`. The direct previous-filing requirement and resolver will derive the source period from the target period using the same period-code families used by relation offsets.

Revise Modelo 303 so the compensation chain uses current AEAT casilla identities: prior-period pending balance `110`, applied compensation `78`, remaining prior-period balance `87`, and final result `69`. The bound prior balance resolves from the previous quarter's computed end-of-period balance. The applied amount is the non-negative minimum of available prior balance and the positive current regimen-general amount. The remaining prior balance is `110 - 78`, and the end-of-period carry-forward adds that remaining prior balance to a negative current result when applicable.

Revise the Modelo 303 self relation to use `source_period_offset_from_target = -1`, so `2T` depends on `1T`, `3T` on `2T`, and `4T` on `3T`.

Revise Modelo 390 to declare annual compensation reconciliation fields for casilla `97` and casilla `662`, sourced from the four Modelo 303 filings and backed by the declared AEAT 390 record design source.

Add focused tests that verify the official-field shape, direct previous-quarter resolution, and numeric outputs for the current scoped formulas.

## Rationale

This keeps legal authority and source evidence in the registry resource system, avoids an application-side IVA wallet special case, and fixes the actual runtime regression that made `source_output` previous-filing bindings inert.

Using `source_period_offset_from_target` is preferable to static `source_periods` because a carry-forward balance is a previous-quarter dependency, not an aggregate across all prior labels.

Keeping unmodelled current 303 addends at zero is narrower and safer than inventing unsupported formulas for casillas outside the audited compensation chain.

## Consequences

Downstream callers that refer to the old internal ids `iva.compensacion-anteriores` and `iva.resultado` must move to the current casilla ids. Existing persisted observations with those old ids may need a migration if they are used as previous-filing evidence.

The 390 annual compensation fields become visible to validation and snapshot consumers, but full refund-option handling remains out of scope until LIVA refund provisions and the relevant Modelo 303/390 refund casillas are audited in the same way.

Future work should add grounded formulas for the remaining Modelo 303 casilla `69` addends and enforce the LIVA art. 99 four-year caducity window as a dated balance policy rather than a simple same-year previous-quarter copy.

The broader relation-runtime closure now explicitly includes the linked Modelo 130 relation-regression ADR. That follow-up is related by implementation mechanism, not tax domain: Modelo 303 IVA compensation and Modelo 130 IRPF negative-result deductions both rely on previous-period evidence materialised into current-period bindings, but their legal rules and source casillas differ.

The live IVA compensation wallet ADR is the production authority extension for this ADR. The local previous-filing recurrence implemented here is not sufficient as the final backend authority for casilla `110`; it is the fallback and reconciliation path once the AEAT wallet read is implemented.

## Status

Accepted and in force. The compensación arithmetic this ADR establishes stands; its
carry grounding aligns to the canonical compensación-carry direction in the PHASE ADRs
(not a central apex doc): the foundational `live-iva-compensation-wallet-adr` is the
carry anchor, and the future phase-2.3 (fold-in/carry) ADR unifies the carry mechanism.
Those phase ADRs are the canonical direction.
