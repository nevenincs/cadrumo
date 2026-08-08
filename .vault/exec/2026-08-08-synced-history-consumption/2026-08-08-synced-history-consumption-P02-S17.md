---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:b3d520121ca361676f29cb00a724beab2ce69ba87a4e6e0dc90eddb3aa22388e'
step_id: 'S17'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
---
# Make the declared factual_evidence treatment actually gate consumption, since the registry draws the line and the resolver does not stand on it. classification.treatment is read at exactly one production site on the resolution path and folded into a requirement grouping key, so it discriminates bucketing and gates nothing, and a factual_evidence Modelo 193 retencion the taxpayer SUFFERED reaches the annual return by the identical path a direct_annual_settlement Modelo 130 pago fraccionado does. Per the ruling a factual_evidence carry is a reconciliation target and must not silently settle a casilla. The remedy must NOT be to blank the value, because a taxpayer is entitled to the retencion and a silent drop is the over-declaration direction this campaign already found unwatched. Surface it as a prefilled reconciliation value carrying its provenance and its treatment, distinguishable by a consumer from a settled figure. Gate: a factual_evidence carry and a direct_annual_settlement carry are distinguishable at the point a casilla value is produced, no value a taxpayer is entitled to is removed by the change, and a test drives one of each through the live calculate and asserts they are not interchangeable

## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/domain/calculations/registry`

## Description

- Relocated the defect before implementing it: the registry layer does not lose the treatment, the resolvers drop it at the requirement-to-value join.
- Took the narrow route, adding the treatment to the record each resolver emits, rather than widening the mesh's binding-values contract.
- Carried the value through unchanged, gating nothing, per the ruling's constraint.
- Pinned the undeclared case by test rather than by comment.
- Attributed 28 pre-existing failures in the owning directory against clean HEAD before claiming anything.

## Outcome

THE DEFECT WAS ONE LAYER LOWER THAN THE ROW SAID, AND SMALLER. The row and the ruling both stated that treatment is read at one production site and folded into a grouping key, so it gates nothing. That understates what the registry does. `dependency_treatment` is a declared field on the fold requirement, populated from the classification, carried out of `relation_source_requirements`, and typed as a three-value Literal at the handoff surface. The registry layer preserves it intact.

Where it was lost is the requirement-to-value join inside the two resolvers. By the time values reach the aggregation mesh, the contract is a bare mapping of binding id to Decimal with no provenance and no treatment, so both classes arrive indistinguishable. That relocation matters for whoever reads this next: the framing in the row would have sent someone looking in the registry layer, where nothing is wrong.

WHAT CHANGED. The relation value record and the prefilled binding record each gained a `dependency_treatment` field. The relation join now carries it off the requirement it already holds. The binding emit site reads it from the revision's own dependency classifications, keyed by source modelo, which is the same key the relation resolver reads it under.

CARRIED, NOT GATED, WHICH IS THE RULING'S CONSTRAINT AND NOT AN OMISSION. No value is withheld. A taxpayer is entitled to a suffered retencion and dropping it silently is an over-declaration, which is the direction this apparatus does not otherwise watch. What changes is that a consumer can tell a figure that settles the return from a fact to reconcile against. Choosing to gate would have been the harmful implementation of a correct reclassification.

THE SEVENTEEN UNDECLARED CARRIES ARE UNTOUCHED, AND THAT IS PINNED BY A TEST. The field defaults to the empty string, so a gate written as equality with a declared value is safe while one written as inequality with the settlement value would sweep every one of the seventeen into the reclassified set, which is ratifying by implementation what the ruling explicitly refused to rule. A comment would not survive a later simplification reaching for symmetry, so the default and its distinctness from both declared values are asserted.

THE NARROW ROUTE WORKED, so the wide one was not attempted. Widening the mesh's binding-values contract would have touched every enrolled resolver and is far larger than this row describes.

## Verification

    uv run --no-sync pytest -n0 -q <the new treatment-join test>
    4 passed in 16.56s

The carrying test asserts that two DISTINCT declared values survive the join rather than asserting against a named relation id, so a registry rename cannot make it pass vacuously while the distinction is lost. It runs the real join over the real Modelo 100 2024 revision and its real fold requirements.

MUTATION PROOF, out-of-repo plugin, holder asserted twice: that the join helper exists and that it actually carries a dependency_treatment key before rebinding. The join was rebound to drop the treatment, which is the state the tree was in before this change.

    1 failed, 3 passed in 0.65s
    FAILED ...::test_the_join_carries_both_declared_treatments_and_they_differ

Exactly the carrying assertion reddens. The three controls stay green, and that is the correct blast radius rather than a weakness: the undeclared pin stays green because an empty treatment is still empty under the mutation, and the value-preservation assertions stay green because dropping the treatment does not withhold a figure. A mutation that reddened all four would have meant the tests were asserting the helper rather than the property.

ATTRIBUTION OF 28 FAILURES IN THE OWNING DIRECTORY, none of them this change. The directory reported 28 failed and 601 passed in the working tree. Clean HEAD with only this change's three production files overlaid reported the same 28 and 601. Clean HEAD alone reported the same 28 and 601. Identical counts across all three trees, and three sampled failures reproduce on clean HEAD, so every one is pre-existing and none is caused here. They concern Modelo 303 intracom routing and a prorrata regularizacion oracle, consistent with the concurrent legal-catalogue and rates churn reported in the tree.

Type and lint gates on all three production files: ty check all checks passed, ruff format left them unchanged after formatting, ruff check clean.

## Notes

WHAT THIS DOES NOT DO. It does not change any consumer's behaviour. The distinction is now available at the point a value is produced, and nothing yet acts on it. That is deliberate and is the row's scope: the ruling reclassified twelve carries and required that the reclassification be visible without the value disappearing. Deciding what a consumer should DO with a factual_evidence carry, on a surface an operator sees, is not settled here and needs its own row.

A tenth peer sweep took all three production files into HEAD before they could be committed here. All three were verified present in HEAD afterwards by content rather than by status.

The registry directory-fingerprint race fired twice during this work, presenting as a pytest collection error rather than as a data problem. Both times the same file set passed on retry. It is worth naming because it looks like a real break and is not.
