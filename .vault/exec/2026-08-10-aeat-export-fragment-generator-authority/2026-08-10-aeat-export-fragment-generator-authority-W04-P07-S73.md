---
tags:
  - '#exec'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:95154b614e069b08ca1533e752901d7982c2798270976912ddece84d93792608'
step_id: 'S73'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# Extend the single annual Orden registry authority to the regulatory axes the official simplified-regime calculation requires but the compiled authority does not carry, being the ANEXO I agricultural cohort índices, the per-IAE porcentaje de ingreso a cuenta table, the índices correctores de temporada day bands, and the cuotas soportadas de difícil justificación rate, across every pinned Orden source, with census invariants and manifest regeneration. Remove the hardcoded non-agricultural kind, the single applicable fact identity, and the ANEXO II-only structural refusal that together cap the authority at one cohort and three axes. Ground the agricultural porcentaje and the two-digit agricultural código taxonomy in located official sources or refuse the axis explicitly rather than defaulting it

## Scope

- `src/cadrumo/domain/calculations/registry/`
- `src/cadrumo/core/`
- `src/cadrumo/_data/registry/aeat/m303_orden_anual/`
- `src/cadrumo/_data/corpus/`

## Description

- Extend the single annual Orden parser and registry authority with every source-pinned agricultural index, agricultural and IAE ingreso-a-cuenta, seasonal-band, and difficult-justification axis.
- Preserve each axis's source/legal coordinate, enforce per-year census invariants, regenerate the four bundled extraction sidecars and manifest, and retain the established non-agricultural projection path.
- Represent the agricultural source material as an explicit unresolved authority because the published Orden does not supply a DP30302 two-digit agricultural-code crosswalk; reject agricultural filing rows at validation and projection with the declared refusal token.
- Split the annual Orden compiler into bounded source, raw, key, legal, manifest, projection, and resolution modules without a second parser or parallel authority.

## Outcome

All four annual sources now carry the regulatory axes in one typed annual-Orden authority: 16 agricultural index and ingreso rows for 2023/2024, 17 for 2025/2026, 47 non-agricultural ingreso rows, season bands for days 1-180, and the source-agreeing one-percent difficult-justification rate. The bundled authority has no official agricultural DP30302 crosswalk, so it refuses agricultural activity selection deterministically rather than inferring a map. `pytest -n 0 --noconftest` on the annual authority, parser, and simplified-regime projection surfaces passed 39 tests; the annual manifest check, Ruff, and BasedPyright passed.

## Notes

The S73 review initially found that the typed agricultural refusal was retained in the snapshot but did not reach filing validation. This was resolved before closure by making agricultural authority an explicit required validation/projection input and adding a real resolved-authority refusal test. S74/S75-owned calculation and identity migrations remain deliberately intact: this step neither deletes their runtime paths nor infers the absent crosswalk.
