---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:0cd5c34d6e576d68d87621f35d17dff78b07c1c488da6660e7765dec66ff046d'
step_id: 'S459'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop deciding row-table candidacy by cell type and hold the translation-key kwarg set to the TranslationKey annotation, since a choice table pairs its key with the enum member it sets and four parameters the type already declares as keys were absent from a list grown one orphan at a time

## Scope

- `dev/locales/_ast_scanner.py`
- `dev/locales/tests/test_dynamic_prefix_registry_coverage.py`

## Changes

Parity extras: 176 -> 171. Full-literal residue 18 -> 13.

TWO FIXES, both of which replace a judgement with the declaration.

FIRST -- row-table candidacy stops depending on cell type. S457 allowed a
non-string cell so a column table could carry its width; the same rule still
demanded every cell be a literal CONSTANT, which rejected the choice table:

    (BusinessClassification.BUSINESS, "tui.ledger.classification.business")

Same shape, different sibling, and the enum member is no more a key than the
width was. Anything that is not a string literal is now carried as a position
that can never BE a key column. What keeps this from over-firing was never the
cell types: the table must still be iterated into a translator with the bound
name at a key column, and the gate pins the prose-index negative that proves it.

SECOND -- `_TRANSLATION_KEY_KWARGS` is held to the type. Every entry in that set
arrived because somebody chased a key that had already gone missing, which is
discovery by casualty. The codebase states the answer in the annotation: a
parameter declared `TranslationKey` IS a translation key. Four were absent --
`reason_key`, `short_help_key`, `prompt_key`, `confirmation_prompt_key`.

The set stays hand-written rather than derived, deliberately. It is read at five
sites, and an explicit list is auditable where a set computed from a tree walk
hides the surface it admits. The new gate is what makes the list honest: it
walks every `TranslationKey` annotation in the tree and fails on any name the
set does not declare.

Teeth: three defects, each restored by copy -- re-require literal cells (the
enum table is rejected), drop `reason_key` (the annotation gate fails), and the
prose-index and attribute defects from S457 still bite.

## Notes

TARGET 2 REMAINS OPEN at 171 extras. The suite reports exactly the two failures
that preceded this step -- the parity gate itself and the shadow gate. No new
breakage.

The shadow failure is the BLOCKER from S455, sharpened in S457: the code
declares `tui.ledger.reconciliation.direction` as a leaf and
`direction.invoice_only` beneath it, which is self-inconsistent by the
project's own rule. Other writer's module, rename reverted five times, waiting
on an ownership decision.

Residue: 13 full-literal, 60 tail-only, 98 no-trace. What remains of the
full-literal group is a local assigned a conditional of two keys, two
`frozenset` guards of safe keys, and the AEAT Sync column tables -- the last
reaching the translator through a function PARAMETER and a second helper hop,
interprocedural in a way nothing closed so far has been.
