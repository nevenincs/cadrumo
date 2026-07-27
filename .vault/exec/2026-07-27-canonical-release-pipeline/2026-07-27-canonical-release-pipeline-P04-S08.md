---
tags:
  - '#exec'
  - '#canonical-release-pipeline'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S08'
related:
  - "[[2026-07-27-canonical-release-pipeline-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-release-pipeline with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-27-canonical-release-pipeline-plan placeholders are machine-filled by
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
     The Declare the superseded-names axis in the generated cohort marketplace manifest, seeded with the retired aeat plugin identity, gate: uv run --no-sync pytest dev/packaging/tests -q -k marketplace passes with the generator test asserting the declaration is emitted in every generated manifest and ## Scope

- `dev/packaging/release_cohort.py`
- `dev/packaging/cohort_manifest.py`
- `dev/packaging/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Declare the superseded-names axis in the generated cohort marketplace manifest, seeded with the retired aeat plugin identity, gate: uv run --no-sync pytest dev/packaging/tests -q -k marketplace passes with the generator test asserting the declaration is emitted in every generated manifest

## Scope

- `dev/packaging/release_cohort.py`
- `dev/packaging/cohort_manifest.py`
- `dev/packaging/tests/`

## Description

- Add a superseded-names declaration to the cohort marketplace manifest.
- Seed the shipped cohort manifest with the retired product identity.
- Pin the shipped declaration with a test.

## Outcome

Landed under the commit subject `feat(packaging): retire a superseded plugin
identity by declaration, not delete authority`.

Supersession is declared by the cohort rather than held as a delete list in the
publishing tool, for two reasons. A standing delete authority decoupled from any
release is the shape of the incident that made the ownership rule necessary in
the first place. And a declaration ships in every later cohort, so retirement
becomes an enforced invariant rather than a one-time act.

A malformed declaration refuses rather than reading as retire-nothing, because
an unreadable declaration that parses to an empty set cannot be told apart from
a cohort that retires nothing at all.

Gate: the marketplace suite passes, including a test that the shipped cohort
manifest actually carries the declaration. A mechanism whose declaration does
not ship protects nothing.

## Notes

The retired identity is claimable by anyone today: its published entry records
no publisher, because it predates ownership tracking.

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
