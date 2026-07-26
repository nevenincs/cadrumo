---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S25'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace censal-profile-autofill with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S25 and 2026-07-25-censal-profile-autofill-plan placeholders are machine-filled by
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
     The Bind the operator guide's account of what the censal pull fills to CENSAL_ADOPTABLE_PATHS with a both-directions parity gate, the page having promised the fiscal ID it never adopts while the ownership guard's deliberate first-read allowance kept the failure silent for a blank-identity operator and ## Scope

- `docs/how-to/censo-update.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Bind the operator guide's account of what the censal pull fills to CENSAL_ADOPTABLE_PATHS with a both-directions parity gate, the page having promised the fiscal ID it never adopts while the ownership guard's deliberate first-read allowance kept the failure silent for a blank-identity operator

## Scope

- `docs/how-to/censo-update.md`

## Description

- Correct the operator guide's account of the censal pull so it no longer
  promises to fill the fiscal identity, which the pull reads to confirm
  ownership and never adopts.
- Bind the guide's claim to the adoptable-path tuple with a parity gate in both
  directions, so the page and the code cannot drift apart silently again.

## Outcome

The guide states what the pull fills and what it does not, and the claim is
enforced against the tuple rather than maintained by hand.

Landed as commit `299e1e988e`.

## Notes

This record was written during a plan reconciliation, from the commit and the
step text, rather than by whoever executed the work. It reports what landed and
what was verified; it does not speak for the reasoning behind the choices, which
only the executor holds.

The step was already marked complete when this was written, with no record
linked - the state the plan-closure rule exists to prevent. The record was
absent rather than misfiled: no document under the feature carried this step's
identifier or referenced the guide, checked with a positive control confirming
the search ran. So the checkbox was set without a record rather than a record
existing under a name the index could not match, and the repair is this document
rather than a rename.
