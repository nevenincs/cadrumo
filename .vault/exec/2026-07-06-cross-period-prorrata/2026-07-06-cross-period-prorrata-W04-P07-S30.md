---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S30'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# defer prorrata source-mesh promotion pending peer WIP

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Re-read the live plan status after S29 and confirmed `W04.P07.S30` was the
  next authoritative open step.
- Re-grounded the promotion semantics through semantic search, the
  cross-period prorrata ADR, the W04/P07 plan row, the existing
  `PRORRATA_REGULARIZACION` deferred-source registry entry, and the
  `iva_compensation_annual_partition` precedent.
- Ran the required pre-edit WIP check for `_source_mesh.py` and found existing
  non-authored uncommitted changes in that target file.
- Did not edit `_source_mesh.py`, did not promote `PRORRATA_REGULARIZACION`,
  and did not change resolver ownership or source-kind disposition.

## Outcome

- `W04.P07.S30` is formally deferred, not implemented as a live mesh promotion.
- Blocker: `_source_mesh.py` contains non-authored WIP adding structured
  out-of-window source-diagnostic fields/helpers. The shared-worktree safety rule
  requires aborting edits to a file with non-authored WIP.
- Follow-up: rerun S30 after the `_source_mesh.py` WIP owner lands or clears that
  change; then enroll the `PRORRATA_REGULARIZACION` resolver in
  `merge_source_resolutions` and remove it from `DEFERRED_SOURCE_KIND_TARGETS`
  in the same change, gated by the S29 AEAT manual oracle proof.

## Notes

- Verification evidence: `vault plan status` at HEAD reported S30 as the next
  open step and no missing exec ids before this deferral.
- Verification evidence: `git diff -- src\aeat\application\aggregation\_source_mesh.py`
  showed non-authored WIP in the S30 target file.
- No production code was edited for this step.
