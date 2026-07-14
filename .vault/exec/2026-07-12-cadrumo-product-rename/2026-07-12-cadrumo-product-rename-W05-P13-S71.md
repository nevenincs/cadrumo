---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S71'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
  - "[[2026-07-14-cadrumo-product-rename-audit]]"
---




# Rewrite active explanation and reference pages with the product-authority boundary

## Scope

- `docs/explanation and docs/reference`

## Description

- Confirm the current `docs/explanation` and `docs/reference` directories carry no stale product-branding form (a token sweep for legacy `aeat`-as-product phrasing found none); no change to those two directories was required.
- Rewrite `docs/architecture/index.md` — the codebase-facing explanation page occupying the same product-authority-boundary role — landed in `ba5bc9e033`, replacing "`aeat` is a local-first command-line application..." with "Cadrumo is a local-first application... through the `aeat` command-line interface", correcting the `src/aeat/` path reference to `src/cadrumo/`, and noting the documented application-composition exception to the inward-dependency rule.
- Verify the rewritten page against the mandatory nitpicky Sphinx build (recorded under `S75`).

## Outcome

`docs/explanation` and `docs/reference` already observed the product-authority boundary and needed no edits. `docs/architecture/index.md`, the explanation-class page that previously conflated the `aeat` command with the product, now names Cadrumo as the product and `aeat` as its CLI, and its source-tree references match the current `src/cadrumo/` layout. Audit `2026-07-14-cadrumo-product-rename-audit` grants this Step's Phase 3/Phase 8 approval on the basis of the principal-documentation-writer session's direct review, which found no naming-law defect across the swept surfaces.

## Notes

This record documents work already committed in `ba5bc9e033` under the combined subject `W05.P13.S68-S71, S73`. The plan Step names `docs/explanation and docs/reference` as its scope; the only content requiring rewrite for this concept class lived in `docs/architecture/index.md`, which this record also covers.
