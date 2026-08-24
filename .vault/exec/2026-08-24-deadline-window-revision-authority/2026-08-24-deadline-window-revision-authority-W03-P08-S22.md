---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:21696ad7f5bd790e47a514202fb2137abd8d77eeb028c0135ec8975e3f4158cc'
step_id: 'S22'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

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
