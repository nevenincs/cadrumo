---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S18'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace declaracion-real-render-verification with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-07-26-declaracion-real-render-verification-plan placeholders are machine-filled by
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
     The Decide the disposition of verify_declaracion, a modelo-agnostic comparison mechanism with zero callers outside its own tests and ## Scope

- `src/cadrumo/application/verification` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Decide the disposition of verify_declaracion, a modelo-agnostic comparison mechanism with zero callers outside its own tests

## Scope

- `src/cadrumo/application/verification`

## Description

- Determine whether verify_declaracion is dead code, an unwired capability, or a deliberate seam.
- Establish it from the code and its history rather than from its docstring.
- Cross-check against the parallel audit already sitting in this feature.

## Outcome

An abandoned partial build. Not dead code, and not a deliberate seam.

The mechanism is real and modelo-agnostic, scoped by the same verification-policy fold the enrolled reconcile path uses, and it has no callers outside its own tests. The originating decision record planned it together with a CLI-wiring section naming two operator verbs. Neither verb was ever built, and the CLI root has since narrowed to two command families, so those names would not fit today even if someone wanted them.

The newer reconcile mechanism is not its replacement. It solves a different problem — comparing against a persisted revision, where this one computes fresh and needs no revision at all — and was enrolled months later. So the two are not duplicates and retiring one in favour of the other would lose a capability rather than remove a redundancy.

The practical consequence is that enrolling it today means designing a new operator verb under the current command vocabulary, not flipping a switch. That is a decision for whoever owns the CLI surface, and it is recorded here rather than taken.

## Notes

The finding was cross-checked against a parallel audit from another campaign that had reached the no-callers conclusion independently. Its claims reproduced, which is corroboration from a genuinely separate source rather than the citation loop this feature has had to break twice.

The disposition deliberately stops short of a recommendation to delete or to wire. Both are defensible and the choice depends on whether the fresh-compute capability is wanted, which is not this campaign's question.
