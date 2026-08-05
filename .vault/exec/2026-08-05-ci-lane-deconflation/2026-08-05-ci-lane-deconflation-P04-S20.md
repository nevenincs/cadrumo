---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:2eacb86f94ab20de3b30b3bce69305a2064ef26c33236c2c6d41a3c720f3f134'
step_id: 'S20'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ci-lane-deconflation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S20 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Resolve the import-hygiene test-debt failures from the maternidad private reaches, raising a baseline designed to only decrease would invert the ratchet so establish whether the debt is legitimate before admitting it and ## Scope

- `src/cadrumo/tests/test_import_hygiene_gate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Resolve the import-hygiene test-debt failures from the maternidad private reaches, raising a baseline designed to only decrease would invert the ratchet so establish whether the debt is legitimate before admitting it

## Scope

- `src/cadrumo/tests/test_import_hygiene_gate.py`

## Description

- Establish whether the import-hygiene test debt is legitimate before admitting it to the baseline.
- Route the offending reaches onto the facades that own them.

## Outcome

Landed as `dd9e6b3504` ("fix(imports): route two test reaches onto the facades that own them"),
three files, 4 insertions and 3 deletions.

**The row asks a judgement question before it asks for a fix**, and the landed change is that
judgement's answer: the debt was not legitimate. Raising a baseline designed only to decrease
would have inverted the ratchet, so the reaches were repointed at the owning facades and the
baseline was left untouched. A three-file, seven-line change is the right size for that answer;
the alternative would have been a one-line baseline bump.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_import_hygiene_gate.py -q
    19 passed in 90.07s (0:01:30)

Nineteen tests selected and executed. No marker expression was applied to that invocation, so
nothing was deselected and the count is the whole module.

    git log --format=%H --grep="route two test reaches onto the facades" -1
    git show dd9e6b3504 --numstat
    (3 files, +4/-3)

## Notes

The row's framing generalises past this instance: a baseline that only ever decreases is a
ratchet, and admitting new debt to it inverts the mechanism rather than accommodating it. The
question "is this debt legitimate" has to be answered before the baseline is touched, because
touching the baseline is what makes the question unanswerable afterwards.
