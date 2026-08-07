---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:82efe8edaca4a0e1fcc39d1762f6744f6961d165e1ff3b7243a005cae81b82aa'
step_id: 'S132'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Derive each party territorial residency from the transcribed postal code, since the contract now carries a supplier and a customer postal code and the domain resolver can turn a Spanish code into its territory, but nothing joins them so neither residency resolves for a Spanish party on the real path and the classification assembly still refuses an ordinary domestic invoice. This is the last producer between the read path and the assembly answering, so the held minting convergence stays blocked until it lands. Hold the safety asymmetry through the join: an absent or unreadable code resolves to nothing rather than to the mainland, and a party whose residency cannot be established must refuse rather than be assumed domestic

## Scope

- `src/cadrumo/application/ledger`

## Description

- Join the printed postal code into each party's territorial scope resolution, gated on the country evidence positively naming Spain.
- Refuse rather than resolve to the mainland when a Spanish party's postal code is absent or unreadable.
- Refuse rather than assume Spain when no country evidence was established, so a bare postal code never reaches the Spanish province lookup.
- Split the collapsed refusal into three, so an absent, a malformed and a Spanish country code no longer share one message.
- Record in the module docstring why an ordinary domestic invoice still refuses.

## Outcome

The postal code is now the sub-national half of establishment: its first two
digits are the province, so it separates the three Spanish IVA territories a
country code cannot tell apart. An issuer in Las Palmas invoicing a customer in
Madrid resolves to Canarias and mainland respectively, and the assembly reaches
the rule table. Before this the resolver existed and nothing consulted it.

Two limits are deliberate and are the substance of the row. The postal half is
gated on the country evidence POSITIVELY naming Spain, never on the country
resolver merely returning nothing, because five-digit postal codes are not
unique to Spain and the Spanish province lookup would otherwise read a French or
German code as a Spanish province. And an absent or unreadable postal code
refuses rather than resolving to the peninsula: the peninsula is the majority
population, so that default would be invisible in testing while placing
Canarian and Ceutan parties inside a territory their operations are not subject
to. The resolver already refuses it; the refusal is asserted again at the join,
because a caller is free to substitute its own default for the resolver's
nothing, and this is the caller.

The collapsed-outcome defect is fixed in the same change, because it became
load-bearing the moment anything gated on whether the country evidence named
Spain. The country resolver returns nothing for an absent code, a malformed one
and a Spanish one alike; the refusal previously branched on the code merely
being present, so a malformed code was reported as naming Spain. Those are now
three distinct refusals, each naming what would settle it.

**An ordinary domestic Spanish invoice still does not resolve, and this Step
does not close that.** Establishment evidence reaches the assembly as a printed
country code, and a domestic Spanish invoice frequently prints no country at all
while its bare tax identifier carries no country prefix. The available shortcut
is to treat a checksum-valid Spanish tax identifier as establishing a Spanish
party, and it is false: the non-resident company leader, the K/L/M identifiers
issued to Spaniards abroad and to non-residents, and the whole NIE series belong
to parties who are not established in Spain. Establishment for IVA is the sede
de actividad or establecimiento permanente, not tax registration, so even an
ordinary company identifier is registration evidence rather than establishment
evidence. That inference would have tested green, because most Spanish tax
identifiers do belong to resident parties. It was refused and the underlying
evidence question was escalated to the decision record rather than settled here.

## Verification

Tests were written and run BEFORE the behaviour, and failed for the intended
reason rather than incidentally:

    uv run --no-sync pytest .../test_classification_assembly.py -n0 -q
    5 failed, 23 passed in 4.73s
    TypeError: assemble_classification_criteria() got an unexpected keyword argument 'issuer_postal_code'

After the implementation, and re-run against HEAD content after the sweep:

    uv run --no-sync pytest .../test_classification_assembly.py -n0 -q
    28 passed in 3.73s

Wider unit lane across both packages the change reaches:

    uv run --no-sync pytest .../ledger/tests .../iva/tests -n0 -q -m "not integration"
    1 failed, 1332 passed, 21 deselected, 15 warnings in 182.02s (0:03:02)

The single failure is `test_ambiguity_refusal_is_scoped_to_the_window_and_the_moved_tiers`
in the IVA saturation suite, which is peer work in flight and not this Step's:
that test file is modified in the working tree by another lane, carries a new
untracked companion test for the 2022 food-rate window, and holds no reference
to the module this Step changed. Named rather than absorbed.

    uv run --no-sync ruff check <both changed files>
    All checks passed!

Mutation proofs for the join, applied at plugin module scope from outside the
repository, each confirmed by its banner before the result was read:

    an unreadable Spanish postal code resolving to the peninsula -> 3 failed, 25 passed
    the postal half consulted without Spain having been named    -> 3 failed, 25 passed
    the pre-fix collapsed refusal restored                       -> 2 failed, 26 passed

The four mutations covering the customer-status work in the preceding Step were
re-run against this change and still bite, so the two sets of gates do not mask
each other.

An independent review supplied the input that turns the country gate from
prudent into necessary, and it is now carried as a gate. The five-digit shape
discriminates nothing, because Spain, France, Germany and Italy all use
five-digit postal codes, and the Spanish resolver is named for its precondition
rather than checking it. Measured directly against the resolver:

    75001 (Paris)             -> es_mainland
    10115 (Berlin)            -> es_mainland
    00170 (Rome)              -> es_mainland
    51001 (Ceuta / Reims)     -> es_ceuta_melilla
    35001 (Las Palmas/Rennes) -> es_canarias

So the earlier gate proved the guard using codes that happen to read as Spanish,
which demonstrated less than it appeared to. A parametrised case now drives the
join with an unambiguously foreign code and asserts the refusal, and the ungated
mutation was confirmed to produce the exact hazard rather than merely a failure:

    uv run --no-sync pytest .../test_classification_assembly.py -n0 -q
    32 passed in 4.60s

    with the country gate removed  -> 7 failed, 25 passed
    AssertionError: a Paris postal code was accepted as Spanish establishment evidence
    UNGATED: Paris issuer resolved to -> es_mainland

The composition is what makes the unsafe shape the natural one. The country half
returns nothing for a Spanish code BY DESIGN and also for an absent or malformed
one, so a consumer written the obvious way -- country first, else postal --
treats a French party whose country was unreadable exactly like a Spanish one.
Each half is fail-closed and the pair composes fail-open, which is why the gate
is on the country evidence POSITIVELY naming Spain and why telling the three
outcomes apart is load-bearing rather than cosmetic.

## Notes

**The gap this Step leaves open should be legible from here and not only from
the campaign's messages.** The postal join is live, but the establishment
evidence that would let an ordinary domestic Spanish invoice use it does not
exist on the read path. That population refuses, correctly, and the held minting
convergence therefore stays blocked. This Step is not the last producer before
the assembly answers, and describing it as one would misread the state.

A claim made while investigating was wrong and is corrected here so a later
reader does not inherit it. The collapsed-refusal defect was first reported with
`XX` as the example of a code misreported as naming Spain. Measured against the
live resolver, `XX` is a well-formed alpha-2 token and resolves to
THIRD_COUNTRY, so it never reaches that branch; the jurisdiction normaliser
checks the SHAPE of a code and not its membership of any real country list. The
defect is real but its example is a code malformed in shape, such as `ESP` or
`E1`. The gate uses `ESP` and says why, so the wrong example cannot be
reintroduced from the test.

The changed files were again taken into HEAD by the repository's in-flight
sweeper lane before this Step committed, this time carrying the whole test file
and most of the module. The remainder was committed with an explicit pathspec
and the landed state re-verified: the working tree is byte-identical to HEAD for
both files, and the baseline plus all three join mutations were re-run against
HEAD content with the results quoted above.

No production caller consumes the assembly yet, so the postal parameters are
supplied by tests only, symmetric with the country parameters that already had
no producer. Wiring them from the read draft belongs to the held convergence.
