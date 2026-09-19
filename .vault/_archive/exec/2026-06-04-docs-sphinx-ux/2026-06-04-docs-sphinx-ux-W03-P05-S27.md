---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:11ca51c47ea5dfa575289c3cbcd44465712c890068e586a641c0f4a9ecfb9cbd'
step_id: 'S27'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---
# Reconcile post-close nitpicky documentation-build drift by refreshing the six non-machine-secret sequence sources whose directive frame counts exceed their goldens, restoring every generated or authored target currently missing from the all-pages build, resolving the current generated Modelo markup failure, and proving the complete Sphinx and documentation-conformance lanes green without suppressing warnings

## Scope

- `docs/how-to/filing-spine.md; docs/how-to/modelo-303.md; docs/how-to/verification-reports.md; docs/_sequences; docs/reference; docs/api; docs/cli; dev/docs; full docs gates`

## Description

- Reconcile each sequence source against its committed golden through the canonical sequence refresh and review path.
- Restore or correctly retire every target the full documentation tree currently references but cannot resolve.
- Correct the current generated Modelo markup failure at its generator or source authority, never in generated output.
- Run the full sequence, nitpicky Sphinx, and documentation-conformance lanes without warning suppression.

## Outcome

Open carry-forward. The 2026-08-23 machine-secret S17 review recorded that full strict Sphinx stopped on unrelated generated Modelo 200 markup, a missing API index, and stale filing, Modelo 303, and verification sequence goldens while the reviewed protect-data-access page itself parsed and rendered without a diagnostic.

Fresh POT extraction during S18 reproduced six exact non-machine-secret sequence source-to-golden frame mismatches: four on `how-to/filing-spine.md`, one on `how-to/modelo-303.md`, and one on `how-to/verification-reports.md`. The same build also named unresolved authored or generated targets for `reference/environment-overrides`, the CLI root and child pages, and the generated glossary. These pages and generators are outside the machine-secret target and predate its current help remediation.

This Step owns that complete finite Sphinx and sequence backlog. The open CI-lane observation remains separately owned by `ci-lane-deconflation` P01.S01 after this local build criterion becomes green.

## Notes

Closure requires `uv run --no-sync python -m dev.docs.sequences check --timeout 300` and `just docs-check` to complete green on one coherent HEAD, with all sequence cases collected, the nitpicky full-site build successful, no warning suppression or page exclusion, and no hand edit of generated reference output. The subsequent push-triggered runner observation remains the unchanged `ci-lane-deconflation` P01.S01 criterion.
