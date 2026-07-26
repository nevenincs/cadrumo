---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S27'
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
     The S27 and 2026-07-25-censal-profile-autofill-plan placeholders are machine-filled by
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
     The Rewrite this campaign's censo pull door docstring to assert what the test pins in the present tense with no narration of the module's previous state, then re-run the marker-integrity gate and quote its exit line rather than re-reading the file and ## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/test_censo_pull_verb.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Rewrite this campaign's censo pull door docstring to assert what the test pins in the present tense with no narration of the module's previous state, then re-run the marker-integrity gate and quote its exit line rather than re-reading the file

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/test_censo_pull_verb.py`

## Description

- Rewrite the censo pull door's test docstring to assert what the test pins, in
  the present tense, without narrating what the module used to do.
- Re-run the marker-integrity gate and quote its exit line rather than inferring
  the result from re-reading the file.

## Outcome

The docstring states the rule the test enforces rather than the history of the
module, and the file is no longer among those the marker gate flags.

Landed as commit `f35765291c`. Re-verified at this reconciliation: the gate no
longer names this file, and its remaining failure is the pytestmark-placement
check against files owned by other campaigns.

## Notes

Scaffolded and first drafted during a plan reconciliation; the executor then
authored this account, so the reasoning below is first-hand.

The step's instruction to quote the gate's exit line rather than re-read the
file was the substance of it, not a formality. An earlier pass on this same
surface reported the tree broken on the strength of a compound shell expression
whose output was misread, and the retraction cost more than the check would
have. Quoting what the gate printed is the cheapest available guard against
reporting a state nobody measured.

The docstring rewrite itself is small: the banned tokens were campaign
vocabulary describing what the module used to do, and a test docstring that
narrates history goes stale the moment the history does. Stating the rule the
test pins keeps it true for as long as the assertion is.

One number attached to this step needs correcting rather than repeating, and it
belongs to the reconciler rather than the executor. The
gate was reported at one failure after this work, then read as two, and the
second reading was accurate - but not because this fix regressed. A different
campaign, working on required-field binding, added a fresh violation about an
hour later by using a banned token in its ordinary English sense. That was
corrected separately, and the gate now reads one failure again. The lesson is
that a shared ratchet's count is not attributable to the last person who touched
it; the file list is, and the count is not.
