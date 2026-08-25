---
tags:
  - '#plan'
  - '#docs-sphinx-ux'
date: '2026-06-04'
tier: L3
related:
  - '[[2026-06-04-docs-sphinx-ux-adr]]'
  - '[[2026-06-04-docs-sphinx-ux-research]]'
  - '[[2026-06-01-docs-cli-buildtime-research]]'
  - '[[2026-06-01-docs-educational-surface-adr]]'
modified: '2026-08-25'
body_hash: 'sha256:f9ae3354868c08403e7e93db1097d674b524f645b167436d3cbf23cc03a1694e'
---

<!-- RETIRED: S27 -->

# `docs-sphinx-ux` implementation plan

Implement the accepted Furo-first generated Sphinx UX design system.

## Description

This plan turns the generated Sphinx UX ADR into executable work: dependency
wiring, theme ownership, brand assets, metadata, visible task routing,
generated-reference wrappers, and verification against the real built docs.
It preserves generated-output discipline by changing configuration,
generators, and curated entry pages rather than hand-editing generated stubs.

## Steps

## Wave `W01` - foundation and design approval

Establish the docs UX substrate and stop at a human approval gate before broad navigation and reference changes build on the visual direction.

### Phase `W01.P01` - wire docs dependencies and metadata

Establish the extension and metadata substrate before visual or navigation surfaces depend on it.

- [x] `W01.P01.S01` - add the approved Sphinx UX extensions; `pyproject.toml`.
- [x] `W01.P01.S02` - wire extension loading and project metadata; `docs/conf.py`.
- [x] `W01.P01.S03` - declare canonical published-site metadata placeholders; `docs/conf.py`.

### Phase `W01.P02` - build the Furo visual system

Create the trust-first brand assets and CSS layer that make the Sphinx site visibly project-owned.

- [x] `W01.P02.S04` - create light and dark documentation logo assets; `docs/_static`.
- [x] `W01.P02.S05` - create the Furo theme variable stylesheet; `docs/_static/aeat-docs.css`.
- [x] `W01.P02.S06` - connect logos CSS and Furo theme options; `docs/conf.py`.

### Phase `W01.P06` - approve brand direction

Pause implementation until a human reviewer accepts or redirects the logo, palette, typography, and trust posture.

- [x] `W01.P06.S17` - prepare the brand review packet; `docs/_build/html`.
- [x] `W01.P06.S18` - obtain explicit human approval for brand direction; `human brand review gate`.
- [x] `W01.P06.S19` - incorporate approved brand feedback; `docs/_static`.

## Wave `W02` - navigation and reference approval

Implement the visible route and generated-reference wrappers after the visual direction is approved, then stop for human review of cognitive load and readability.

### Phase `W02.P03` - make entry routes scannable

Turn the first documentation viewport into a compact task router while preserving Sphinx toctree structure.

- [x] `W02.P03.S07` - replace the first-page route list with a scannable task grid; `docs/index.md`.
- [x] `W02.P03.S08` - make safety and responsibility routes visually persistent; `docs/index.md`.
- [x] `W02.P03.S09` - preserve hidden toctrees while exposing visible route labels; `docs/index.md`.

### Phase `W02.P04` - wrap generated references

Reduce generated API and CLI mental load through curated wrappers and generator changes instead of manual output edits.

- [x] `W02.P04.S10` - add a curated API boundary overview; `docs/api/index.md`.
- [x] `W02.P04.S11` - retarget the API toctree entry to the curated overview; `docs/index.md`.
- [x] `W02.P04.S12` - separate operator CLI routes from schema registry detail; `src/aeat/entrypoints/cli/_doc_reference.py`.
- [x] `W02.P04.S13` - update CLI reference conformance expectations; `src/aeat/entrypoints/cli/test_doc_reference_conformance.py`.

### Phase `W02.P07` - approve navigation readability

Pause after route and reference wrapper changes until a human reviewer accepts the cognitive-load and readability tradeoffs.

- [x] `W02.P07.S20` - prepare the route and reference review packet from a fresh local site build (docs/_build/html is a gitignored, re-derivable artifact, not a persisted deliverable); `docs/_build/html`.
- [x] `W02.P07.S21` - obtain explicit human approval for navigation readability; `human navigation review gate`.
- [x] `W02.P07.S22` - incorporate approved route feedback; `docs/index.md`.
- [x] `W02.P07.S23` - incorporate approved reference feedback; `dev/docs/cli_reference.py`.

## Wave `W03` - rendered-site approval

Build the real HTML documentation and require explicit human approval of visual design, readability, accessibility, and cognitive load before the UX pass is considered complete.

### Phase `W03.P05` - verify rendered docs UX

Build and inspect the real HTML output so the decision is validated against the generated documentation tree.

- [x] `W03.P05.S14` - run docs dependency and stub drift gates; `docs conformance lane`.
- [x] `W03.P05.S15` - build the rendered HTML documentation; `docs/_build/html`.
- [x] `W03.P05.S16` - inspect desktop and mobile rendered UX; `docs/_build/html`.

### Phase `W03.P08` - approve rendered experience

Close the UX pass only after a human reviewer accepts the actual desktop and mobile rendered documentation.

- [x] `W03.P08.S24` - prepare the final rendered approval packet; `docs/_build/html`.
- [x] `W03.P08.S25` - obtain explicit human approval for rendered experience; `human final review gate`.
- [x] `W03.P08.S26` - record approved follow-up UX issues; `.vault/exec/2026-06-04-docs-sphinx-ux`.

## Parallelization

Dependency and theme configuration must land before route and reference
surface edits. Static assets and CSS can be developed in parallel inside
`W01`, but `W02` must not start until `W01.P06.S18` records explicit human
approval or `W01.P06.S19` applies requested brand revisions. The route and
reference wrapper work in `W02` can run in parallel after brand approval, but
`W03` must not start until `W02.P07.S21` records explicit human approval or
`W02.P07.S22` and `W02.P07.S23` apply requested readability revisions.

## Verification

The plan is complete when every Step is closed, the docs dependencies resolve,
the Sphinx build succeeds, the docs conformance lane passes, the generated
API and CLI surfaces are not hand-edited, and the built HTML has been visually
checked for navigation, branding, dark-mode contrast, metadata, and copy-button
behavior. Machine checks are necessary but insufficient: `W01.P06.S18`,
`W02.P07.S21`, and `W03.P08.S25` require explicit human approval before their
downstream waves or final completion can be marked closed.
