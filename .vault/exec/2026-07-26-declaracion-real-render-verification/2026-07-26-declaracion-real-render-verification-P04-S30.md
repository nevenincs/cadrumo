---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S30'
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
     The S30 and 2026-07-26-declaracion-real-render-verification-plan placeholders are machine-filled by
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
     The Declare verify_declaracion's reference-implementation role in its own docstring so it is not deleted as dead code, since three production modules cite it as the canonical scoping policy and ## Scope

- `src/cadrumo/application/verification` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare verify_declaracion's reference-implementation role in its own docstring so it is not deleted as dead code, since three production modules cite it as the canonical scoping policy

## Scope

- `src/cadrumo/application/verification`

## Description

- Confirm by search which modules cite verify_declaracion, and for what.
- Declare the reference-implementation role in the function's own docstring.
- Record what deleting it would cost and what wiring it would still require.

## Outcome

The role is now declared in the function's own docstring, where a dead-code sweep will meet it.

The disposition this implements was already taken: neither wired nor deleted, but declared. What was missing was the declaration itself, and its absence was the hazard. The function has no production caller and no entrypoint surface, so every reachability pass reads it as an abandoned build, and the likely outcome of leaving it undeclared was deletion.

The docstring states that it is the canonical statement of the registry-declared reconciliation scope, that being unwired is deliberate, and that the enrolled reconcile path is not a replacement because it compares against a persisted revision where this one computes fresh and needs no revision to exist.

The dependants are named from a search rather than carried over, and the search corrected the earlier count. Two production modules depend on it for the scoping policy: the reconcile path and the casilla comparison, which describe their own behaviour as the same policy and as mirroring this treatment. A third module cites it for a different thing, since the verdict schema's discrepancy categories mirror this classifier rather than its scope. Seven Modelo 100 grounded-oracle tests describe the projection they assert against by reference to it.

## Notes

The inherited claim was that three production modules cite it as the canonical scoping policy. That is not quite what is in the tree. Three production modules do cite it, but only two cite it for the scoping policy; the third cites the classifier taxonomy. The docstring says which is which rather than repeating the aggregate, because the aggregate makes the citation look more uniform than it is.

The seven grounded-oracle tests were not in the earlier count at all, and they materially strengthen the case against deletion since they define the projection they assert against by pointing here.

Run through the nitpicky documentation build as well as the package tests, because the docstring adds cross-references and that gate imports every stubbed module.

Still open and deliberately not taken here: whether to wire it. That needs an operator verb designed under the current two-family command vocabulary, which is a CLI-surface decision rather than this campaign's. The docstring records that wiring stays available so this record is not read as closing it off.
