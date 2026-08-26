---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:82df7eab0e201c07a7d781e485553160bb28f4cf97c63ea2ec832daac94cdf28'
step_id: 'S287'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Decide which producer field carries the separately stamped capability verdict the governing record requires before a graded-snapshot capability may read available, since that record states twice that a readiness flag or an assessment count is insufficient without naming the stamp for filing-draft readiness, verification readiness or filing-export readiness: rule for each capability whether such a verdict exists on its canonical producer, whether one must be added there, or whether the capability is permanently unmeasured until its producer stamps one, and amend the governing registry-api-gate decision record in the same change so the requirement names a field rather than a property

## Scope

- `the amended 2026-08-24-tui-registry-api-gate-adr`
- `src/cadrumo/application/state_projection.py`
- `src/cadrumo/application/modelo/work_review.py`
- `src/cadrumo/application/registry/closure.py`
- `and focused per-capability verdict-stamp tests`

## Changes

- `M` `src/cadrumo/application/modelo/workspace.py` (`graded_snapshot_modelo_workspace_capabilities`)
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py` (`test_graded_snapshot_capabilities_reads_producer_stamps_not_derivations`)
- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md` (S287 amendment, all five dispositions ruled)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/tests/test_workspace.py` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_manifest.py src/cadrumo/application/modelo/tests/test_workspace_producers.py -m integration -q` -> `pass` (112 passed, 1 pre-existing unrelated failure)

## Notes

Scope diverged from the plan Step's guessed file list (`state_projection.py`,
`work_review.py`, `registry/closure.py`): none of the three real stamps
identified live on those files. `CALCULATION_MATERIALIZATION` and
`VERIFICATION_READINESS` both read `CalculationRevision` (existence, and
`state == VERIFICADO_COMPLETO` with required `verified_at`/`verified_by`) --
neither of those fields lives on `ProjectionModeloReadiness`, `ModeloWorkReview`,
or `RegistryClosureLimb`. The guessed scope assumed the stamp would live on
one of the three existing capability-adjacent projections; the actual
answer is that two capabilities' stamps already live on the domain revision
object itself, one capability's approved stamp (a `MODELO_EXPORTED` bucket
event) has no existing S126 contributor port to read it through yet, and one
capability has no stamp anywhere. Recorded plainly here rather than forcing
a false fit to the guessed scope.

Built `graded_snapshot_modelo_workspace_capabilities`, mirroring
`static_inspection_modelo_workspace_capabilities`'s shape: takes an already
-captured `CalculationRevision | None` (never performs its own I/O, matching
the pattern of `graded_snapshot_readiness`/`graded_snapshot_materialization_facet`)
and the resolved target, and computes all five dispositions. Verified the
exact-coordinate requirement explicitly: a revision belonging to a
DIFFERENT work unit must never count toward either calculation-derived
capability, proven by a real test case using a mismatched `work_unit_id`.

`FILING_EXPORT_READINESS` and `FILING_DRAFT_READINESS` both land as
`UNMEASURED` in the built table -- the former pending a ninth contributor
port (bucket event history) that does not exist yet and is explicitly out of
this change's scope; the latter permanently, per the ADR amendment's
finding. Neither is guessed around with a shortcut (e.g. substituting the
registry closure `filing_export` limb, which answers a structurally
different question -- "can this modelo/revision be filed at all" versus
"has THIS revision actually been exported").

S128 is answerable now that S287, S290 and S291 are all decided; checking
S128 itself is the next action.
