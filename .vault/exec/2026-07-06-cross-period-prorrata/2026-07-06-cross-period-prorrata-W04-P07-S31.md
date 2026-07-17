---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S31'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# defer bienes-inversion unblock record pending source promotion

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Re-read the live W04/P07 plan row and confirmed S31 is the same source-mesh
  ownership surface as S30.
- Confirmed the existing `BIENES_INVERSION_REGULARIZACION` deferred target still
  declares `promotion_depends_on=BindingSourceKind.PRORRATA_REGULARIZACION`.
- Did not edit `_source_mesh.py` because the same non-authored WIP that blocks
  S30 also blocks S31.

## Outcome

- `W04.P07.S31` is formally deferred.
- Blocker: the S31 target file `_source_mesh.py` contains non-authored WIP and
  the prerequisite live `PRORRATA_REGULARIZACION` promotion was formally deferred
  in S30, so the definitive-percentage source is not yet live.
- Follow-up: after S30 lands the live prorrata regularizacion source, record the
  bienes-inversion casilla-43 automatic feed unblock in the source-mesh
  disposition surface, preserving the existing `promotion_depends_on` link to
  `PRORRATA_REGULARIZACION`.

## Notes

- Verification evidence: semantic search and grep found the current
  `BIENES_INVERSION_REGULARIZACION` deferred entry and its
  `promotion_depends_on=BindingSourceKind.PRORRATA_REGULARIZACION` relation.
- No production code was edited for this step.
