---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S295'
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
     The S295 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Closed as unnecessary, a peer fix bridged the payload-name filter by importing the wizard result classes into a walked module, so enrolment is filename-filtered still and the divergence ended when that bridge landed and ## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Closed as unnecessary, a peer fix bridged the payload-name filter by importing the wizard result classes into a walked module, so enrolment is filename-filtered still and the divergence ended when that bridge landed

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

Determine whether the wizard result schemas need enrolling in the manifest
population walk before the identity fix can land.

## Outcome

SATISFIED as unnecessary, after two wrong explanations were corrected.

The schemas are declared in a module the population walk never reaches: the
walk imports `*payload*`-named modules under two declared payload packages, and
that module is under neither. Enrolment is filename-filtered, and the finding
was correct when filed.

What made the step unnecessary is a peer fix at `92b0dfd10b`, landed thirteen
hours after the finding and a descendant of the HEAD it was measured at, which
bridges the filter by importing the two result classes into a module the walk
already visits. That fix's own comment states the mechanism and marks the
imports load-bearing.

Measured after it: a `git archive` tree with no untracked files reports 295
schemas, both profile schemas present, zero import failures, identical to the
working tree.

Two explanations were asserted here before that one and both were wrong - that
enrolment was never filename-filtered, and that the untracked-module commit was
the repair. Both were fabricated from present state without checking history,
which `git log -S` answers in one command. The verification phase caught it by
testing the claim rather than agreeing with it.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
