---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S267'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S267 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Verify each open W05 Step against its named surface before checking it, never inferring satisfaction from the live command tree alone and ## Scope

- `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Verify each open W05 Step against its named surface before checking it, never inferring satisfaction from the live command tree alone

## Scope

- `.vault/plan/2026-07-15-cli-authority-verb-conformance-plan.md`

## Description

- Apply the per-surface verification discipline to every W05 Step closed in
  this handover, rather than inferring satisfaction from the live tree.
- Record the cases where the discipline changed the outcome, since those are
  the evidence that it was actually applied.

## Outcome

SATISFIED. Every W05 Step closed in this handover was checked against its NAMED
surface, and the discipline changed the outcome in five of them - which is what
distinguishes having applied it from having claimed it.

The rule exists because the close review found the one W05 Step it actually
checked was the one genuinely undone, and it was concealing a fail-open. So the
test of this row is not that W05 closed; it is whether checking found anything
that inference would have missed.

It did, in both directions.

INFERENCE WOULD HAVE CLOSED THESE WRONGLY. The how-to index carried two retired
verbs, `lock` and `switch`, as bare words in running prose - invisible to a
search for `config lock` or `config switch`, which returns nothing across the
whole documentation tree. The evidence guide headed an `attach` procedure with
the word `Link`, the name of a different verb that requires `--invoice-id` and
carries no evidence role. The data-access guide told a reader whose data would
not open that reset was "the only way forward", directly above an irreversible
delete, when quarantine is non-destructive and previewable. The profile guide
never stated that login accepts only a UUID or the exact label. Each is a live
operator-facing defect that a tree-level check would have passed over.

INFERENCE WOULD ALSO HAVE OPENED WORK THAT DID NOT EXIST. I measured that four
custody surfaces appeared in no documentation and concluded four whole surfaces
were undocumented. They were fully documented; the pages cite commands through
sequence directives BY NAME rather than as literal text, so the search was
looking for a shape the data does not use. Separately, a count of accepted
grammar on the commands reference read as a large gap when that page is a
delegating map that scores zero by construction. Both would have produced
rewrites duplicating correct content.

The sharpest case was neither. I pushed a dispatched agent to treat the curated
help row as real work on the strength of a correct measurement - three surfaces
appearing zero times in the module - and the agent pushed back with evidence
that the row's verb is "replace stale" and that nothing there was stale. It was
right: a content search over that module's whole history shows it NEVER carried
those surfaces, and never carried the retired spellings either, so no stale
record ever existed there to replace. Verifying against the named surface
includes verifying what the row actually asks.

Gates at HEAD `9511ddc2421c3b5c3f07ed3291b217b01e4edb8e`. Each W05 closure carries its own command, collected
count, exit line and HEAD in its record; the shared documentation gate across
the phase was `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m ""
-n0`, collecting 362 cases and exiting `362 passed`.

## Notes

The generalisable form, since this row is a discipline rather than a change: a
clean negative is not evidence unless the tool ran, the path exists, AND the
pattern fits the shape the data actually uses. Three of the five findings above
came from a search returning nothing over the wrong shape, and two came from a
search returning something the reader misread. None came from the live command
tree, which was correct throughout - which is precisely why inferring from it
would have closed the phase with the defects intact.
