---
tags:
  - '#adr'
  - '#modelo-130-relation-regression'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - '[[2026-05-19-modelo-130-relation-regression-research]]'
  - '[[2026-05-19-iva-compensation-chain-adr]]'
  - '[[2026-05-19-iva-compensation-chain-plan]]'
  - '[[2026-05-19-live-iva-compensation-wallet-research]]'
---

# `modelo-130-relation-regression` adr: `same-year negative-result relation remediation` | (**status:** `accepted`)

## Problem Statement

The IVA compensation-chain verification uncovered a non-IVA regression in the
same cross-period relation machinery. Modelo 130 declares a same-model relation
for prior negative results, but the broader cross-dependency suite reported
failures around relation contract shape, formula-bearing revision consumption,
and edge-year observation aggregation for `modelo-130-rel-self-prior-quarter-negative`.

This is part of the same implementation risk family as Modelo 303's previous
IVA compensation relation: a current filing relies on prior AEAT filing evidence
materialised into a current binding. It is not part of the same tax rule. Modelo
130 must remain grounded in IRPF payment-on-account law and AEAT Modelo 130
instructions.

## Considerations

AEAT Modelo 130 instructions ground the carry-forward: casilla `15` contains
prior same-year negative results from casilla `19` that have not already been
deducted, only when casilla `14` is positive, and never above that positive
casilla `14` amount.

Real Decreto 439/2007 article 110 is the legal basis for IRPF payments by
instalment. It is related to the calculation, but the concrete casilla-level
carry-forward behavior must be grounded in the AEAT Modelo 130 instructions and
record design.

The existing IVA remediation added support for `source_output` previous-filing
selectors and target-relative period offsets. Modelo 130 should use the shared
relation-runtime capability where it fits, but it must not import IVA wallet
semantics or four-year IVA compensation behavior.

## Constraints

The worktree is shared and must not use git stash, reset, checkout, or other
destructive worktree state mutation.

The `vault plan` CLI is unavailable in this worktree, so the related plan is
authored from the Vaultspec template with stable identifiers and an explicit
CLI-unavailable note.

The broader cross-dependency verification is currently masked by the
`_brackets_overlap_in_same_window` registry-loading NameError. That blocker must
be cleared before the Modelo 130 relation failures can be fully measured again.

## Implementation

Add a Modelo 130 remediation wave that first restores registry loading and then
audits the current relation against the AEAT casilla rule. Revise the relation
shape only after deciding whether the source requirement is truly the immediate
previous quarter or the aggregate of any prior same-year negative casilla `19`
amounts not already deducted.

If the rule requires aggregate same-year consumption, introduce or reuse a
relation selector that can source multiple prior same-year periods and apply the
current-period cap through the registry formula graph, not through ad hoc
application code.

Add tests that import the real registry, calculate prior Modelo 130 periods, and
verify casilla `15`, `17`, `19`, and `saldo-negativo-fin-periodo` through the
production calculation path. Tests must not mirror business logic or use fakes,
stubs, monkeypatches, skips, or xfails.

## Rationale

Treating Modelo 130 as its own wave prevents the IVA wallet work from hiding an
IRPF regression, while still keeping the relationship explicit: both validate
the same cross-period relation abstraction.

The shared runtime should support both domains, but the registry must declare
domain-specific semantics. IVA compensation uses an AEAT-held wallet and Modelo
303 casillas `110`, `78`, `87`; Modelo 130 uses same-year negative casilla `19`
deductions into casilla `15`, capped by casilla `14`.

## Consequences

The current IVA plan is no longer the complete relation-runtime closure. It
needs a linked Modelo 130 wave before the relation engine can be considered
healthy across periodic filings.

The remediation may require changing the Modelo 130 relation from a simple
prior-quarter copy to a same-year unused-negative-result aggregate. That decision
must be made from the official casilla instructions and record design, not from
the current failing test shape.

The `_brackets_overlap_in_same_window` loader NameError is a prerequisite repair
for trustworthy broad-suite measurement and should be tracked in the Modelo 130
plan as an enabling step.
