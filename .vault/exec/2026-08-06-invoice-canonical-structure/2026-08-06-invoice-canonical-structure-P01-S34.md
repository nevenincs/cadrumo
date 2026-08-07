---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:491a24a7883e561445a1b949f41bd94f7da0a771a18a8b024957b253964719db'
step_id: 'S34'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Re-decide the M349 treatment of an absent iva_category now that its stated justification is stale, the enum having gained intra-community service members in 7502ee65ed while the resolver docstring still says services map to no member, and either correct the reasoning while keeping the behaviour or change the behaviour, never leaving a filing-path guard resting on a false premise

## Scope

- `src/cadrumo/application/invoices/_source_resolver.py`

## Description

- Confirmed the refuting facts at `HEAD` before deciding: both service category members exist, and the same module maps them to their claves.
- Traced how the clave is actually resolved, which produced a stronger justification than the one being replaced.
- Re-decided the guard, keeping the behaviour and replacing the reasoning.
- Pinned BOTH premises as executable tests rather than as prose.

## Outcome

**Behaviour unchanged; justification replaced. The unchanged behaviour is the decision, not the absence of one.**

The guard narrowing M349's decomposition check to self-contradiction defects justified itself on a measured-sounding claim: that an intra-community prestación or adquisición de servicios "maps to no `IvaCategory` member at all, because the enum names goods, acquisitions and triangulation but not services".

That is false, and refuted by the same module that states it. Both service members exist, and `_intracommunity_clave` maps them to claves S and I roughly 180 lines below the docstring. A filing-path guard was resting on a premise its own file contradicts — and the campaign record shows a reader in a peer lane already reasoned from it.

Making absence disqualifying would alter filed M349 output, so it needs its own evidence and its own ruling rather than arriving as a side effect of correcting prose. The behaviour therefore stands, deliberately.

**The replacement justification is stronger, and it was found by measurement rather than by repairing the old sentence.** `_intracommunity_clave` consults an explicit `operation_type` FIRST and returns without ever reading `iva_category`. So a record carrying a directly declared clave legitimately carries no category at all — an absent category usually means the clave came from the other route, not that the operation was inexpressible. Since this guard runs only after the clave is settled, treating absence as disqualifying would drop exactly the records whose clave the operator stated most explicitly: the least ambiguous rows in the store.

Two properties of that reasoning matter beyond this Step:

- It is **independent of what the category enum contains**, which is precisely how the old justification failed. A reason that depends on an enum's membership goes stale the moment the enum grows, and nothing reds when it does.
- The change that refuted the old reason **strengthens** the new one. Services being expressible means a services invoice can reach its clave by either route, so absence is even weaker evidence of an unrepresentable operation than it was.

Both premises are now executable: an explicit operation type resolving a clave with no category at all, and both service members resolving to their own claves. The justification reddens if either stops holding, rather than quietly becoming false again.

## Verification

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_source_resolver.py -p no:randomly -q --no-header
    29 passed in 31.91s

    uv run --no-sync ruff check .../_source_resolver.py .../test_source_resolver.py
    All checks passed!

The refuting facts, measured rather than recalled:

    rg -n "INTRA_COMMUNITY_SERVICE" domain/iva/_schema.py
    57: INTRA_COMMUNITY_SERVICE_SUPPLY
    69: INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE

    _intracommunity_clave (_source_resolver.py:455-483) maps both to "S" and "I",
    and consults operation_type at :456 before reading iva_category at :464.

The capability-parity proof landed in the preceding Step independently declares an intra-community service acquisition under clave I, so the correction is exercised by a second, unrelated test as well.

## Notes

This is the third instance in this campaign of prose that was accurate when written and silently became false: the persistence guard justifying unattributed invoices, the English locale leaf documenting a removed default, and this one. All three were **load-bearing** — each was the stated reason for a behaviour, not a description of it — which is what makes the class dangerous. A stale description misleads a reader; a stale justification licenses them to act.

The countermeasure applied here and worth generalising: prefer a justification that rests on **control flow** over one that rests on the **contents of a set**. Control flow reddens a test when it changes; set membership grows silently.
