---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:5aa00f67b3f1ccfeed7df7cb0ca897bc4845051f9fbb2615adfb47b0fce8f7da'
step_id: 'S05'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# declare `IdentifierNamespace` as a closed StrEnum split into AEAT-issued and app-derived groups, each member documented with the concept it names

## Scope

- `src/cadrumo/core/identity/_namespace.py`

## Description

- Declare `IdentifierNamespace` as a closed `StrEnum` in a new module, re-exported from the identity facade.
- Split the members into an `AEAT_*` group (external, issued by AEAT, shape bounded by observed behaviour rather than by a published specification) and an `APP_*` group (minted by this application, clock-free).
- Document every member with the concept it names and with where its alias lives today, including the members whose aliases have not yet been relocated into this package.
- Record the three deliberately-excluded free-text sub-populations as a comment beneath the enum: AEAT-printed adjudicated-case prose, counterparty-issued document numbers, and identifiers from non-AEAT issuing authorities.

## Outcome

Landed in `c272504f9d`. Verified by direct search beforehand that no `IdentifierNamespace` symbol existed anywhere in the tree, so this closes a genuinely open concept rather than adding a second one.

The enum is declared complete rather than incrementally, so the taxonomy is honest about its own staging: a member whose alias has not yet been relocated says so in its own docstring instead of being omitted, which would have made a partial surface read as a closed one.

## Notes

**The enum has no live consumer and this is disclosed rather than presented as enrolled.** Its first consumer is the shape resolver, which sits in a Phase escalated to the operator, so at the moment this record is written the enum is declared capacity with nothing reading it. That is named in the ledger every tick rather than allowed to pass as complete. Manufacturing a consumer to retire the label would be worse than carrying it.

**Alias placement deviates from the row's literal file scope.** The row scopes only the enum module while the aliases were also declared there rather than in the facade. The governing record asks for the aliases to live in the identity package, not in a specific file, and keeping each alias beside the namespace member it carries prevents the two drifting apart. Both files landed in one commit, so no intermediate state exists in which a member and its shape disagree.
