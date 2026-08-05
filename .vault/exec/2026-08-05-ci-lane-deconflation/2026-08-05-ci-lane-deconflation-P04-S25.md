---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:9b2103d961380a1aa20bf15d3bfdc46bcba8817cd7baf5fbadafdddcdb4bf17b'
step_id: 'S25'
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
     The S25 and 2026-08-05-ci-lane-deconflation-plan placeholders are machine-filled by
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
     The Sweep for tests relying on the English CLI env override for help text, it is inert against the cached Click tree so any such test asserts against whatever language the tree was built in and ## Scope

- `src/cadrumo/entrypoints/cli/tests` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Sweep for tests relying on the English CLI env override for help text, it is inert against the cached Click tree so any such test asserts against whatever language the tree was built in

## Scope

- `src/cadrumo/entrypoints/cli/tests`

## Description

- Sweep the CLI tests for reliance on the English environment override for help text.

## Outcome

Landed as `56ab637c42` ("docs(tests): record that a language env is inert for the in-process
CLI runner"), one file, 27 insertions and no deletions.

The sweep's finding is that the override is inert against the cached command tree: help
strings are rendered when the tree is built, so an environment variable set afterwards cannot
change them, and any test relying on it asserts against whatever language the tree was built
in. The landed change records that where the next author will meet it.

## Verification

    git log --format=%H --grep="a language env is inert for the in-process CLI runner" -1
    git show 56ab637c42 --numstat
    27      0       (one CLI test module)

Insertions only, no deletions: the commit adds an explanation and removes no assertion.

## Notes

**This row closes on a sweep whose result was "no test to repair", and that deserves stating
rather than leaving implied by a documentation-only commit.** The row asks for a sweep; the
sweep found the mechanism inert and documented it. Had a test been found relying on the
override, the row would have required a repair and the commit would not have been
documentation only.

A reader auditing this row later should read the absence of a code change as the sweep's
finding, not as the sweep having been skipped.
