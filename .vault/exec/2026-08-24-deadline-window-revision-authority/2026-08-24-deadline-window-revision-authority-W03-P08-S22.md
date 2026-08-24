---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d266e7c3bdb74724dddf72d4b7ea7d051cfea610e4adcfb8adbb99740b9b27c4'
step_id: 'S22'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S22 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Add a fleet authority test proving canonical ownership, exact multiplicity, qualifier distinction, and modelo-filter invariance and ## Scope

- `src/cadrumo/domain/calculations/registry/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a fleet authority test proving canonical ownership, exact multiplicity, qualifier distinction, and modelo-filter invariance

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Discover the canonical projection, selector, and semantic-coordinate surfaces with Vaultspec RAG.
- Confirm exact symbols and downstream consumers with targeted source sweeps.
- Add a real bundled-fleet test for 2022-2026 canonical ownership, exact row multiplicity, stable ordering, atomic coordinate uniqueness, modelo-filter invariance, and qualified M210 distinction.
- Run focused Ruff and the focused pytest target.
- Request an independent architecture and test-quality review.

## Outcome

The fleet regression is authored, Ruff passes, and the real bundled-fleet focused
pytest target passes 2/2 in 32.53 seconds. It derives expected ownership
through the existing `select_revision` function and expands qualifier identity through
the existing `deadline_window_semantic_coordinates` function. It introduces no
selector, resolver, period parser, cadence map, qualifier vocabulary, deadline
catalogue, deduplication, or sort implementation.

S22 is complete.

## Notes

The first focused pytest run failed before either test body could run because a
concurrent unrelated workspace change left the Modelo 390 revision-2022
`casilla_continuidad_evolutions` fragment directory empty. Registry loading correctly
raises `RegistryLoadError` for that malformed tree. This step did not touch Modelo 390,
did not weaken the real-fleet test, and did not add an xfail, skip, mock, or stub.

After that concurrent workspace condition cleared, the unchanged real-fleet test was
rerun successfully: 2 tests passed in 32.53 seconds.
