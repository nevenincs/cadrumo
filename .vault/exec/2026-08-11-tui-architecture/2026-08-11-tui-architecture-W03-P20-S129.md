---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:c6aafab9a82238432dec44f811bd4d3e0bcdbe76ba4821d18d62fe1a99b034c0'
step_id: 'S129'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Run the final current-HEAD residual Workspace V1 census and cut over only remaining assembly, dispatch, frontend, and receipt consumers not already owned by S171 or S172 to their exact public defining modules, then prove application.modelo namespace inertness plus the defining-module and zero-remnant fixed point, without deleting package bindings or moving, redefining, or deleting any model, producer, or assembly surface owned by S171, S172, or S128

## Scope

- `src/cadrumo/application/modelo/workspace.py`
- `src/cadrumo/application/modelo/__init__.py inert-namespace verification`
- `remaining assembly/dispatch/frontend/receipt consumers`
- `Workspace receipt inventories`
- `dev/quality/import_hygiene_scan.py`
- `dev/tests/test_import_hygiene_gate.py`
- `and focused residual direct-import/defining-module/zero-remnant census tests`

## Changes

- `M` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `verify:` `uv run --no-sync python -m dev.quality.import_hygiene_scan` -> `pass` (zero hits in any family attributable to the Workspace assembly/model/producer/manifest family)
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py -m integration -q -n0 -k "workspace_assembly_has_one_public_module or workspace_assembly_forbidden_private_paths"` -> `pass` (2 passed)
- `verify:` `uv run --no-sync pytest dev/tests/test_import_hygiene_gate.py -q -n0` -> `fail` (6 pre-existing failures unrelated to this Step; none reference "workspace" anywhere in the output -- baseline-count/named-set drift from concurrent peer commits elsewhere in the tree, not touched)

## Notes

The residual census found NOTHING to cut over. The residual set is SMALLER
than the Step assumed, not larger: no assembly, dispatch, frontend, or
receipt consumer of `workspace.py` exists anywhere in the tracked tree
outside `workspace.py` itself and `tests/test_workspace.py`. Established
three ways, by calling/scanning rather than reading: a full
`dev.quality.import_hygiene_scan` run (zero Workspace-attributable hits
across every family -- private imports, shims, multi-sourced symbols,
orphaned modules); a `git grep` across the whole tracked tree for the actual
Workspace V1 symbols (`ModeloWorkspaceRequestV1`, `ModeloWorkspaceResultV1`,
`resolve_static_inspection_result`, `resolve_graded_snapshot_result`,
`resolve_modelo_workspace_target`), which returned only `workspace.py`, its
own test file, and `.vault/` documentation; and a manual read of the actual
TUI frontend package (`cadrumo.entrypoints.tui`), which has no Workspace V1
import at all. The one near-hit was a name collision: `tui/operations/controller.py`
and `tui/operations/modal.py` carry `OperationWorkspaceRefreshTargetRequestV1`/
`ResultV1` and a "Workspace-refresh" vocabulary that is an unrelated,
pre-existing TUI-operations concept (refreshing the current operator screen
after an action settles), never a consumer of the Modelo Workspace V1
registry-reading contract this feature builds. Treating that name collision
as a real consumer would have produced a phantom residual set; it is not
one. `application.modelo.__init__` was already fully inert before this Step
touched anything. No `_workspace_projection.py` or private `_workspace.py`
predecessor has ever existed under `application/modelo/` (confirmed via
`git log --all` against both paths).

Because the cutover was empty, this Step's remaining deliverable is the
proof S171 and S172 each built for their own family and the assembly family
never had: a focused namespace-inertness and zero-remnant fixed point.
Added two tests to `test_workspace.py`, mirroring
`test_workspace_models_have_one_public_module_and_no_private_or_package_binding_remnant`/
`test_workspace_model_docs_and_active_tree_reach_the_public_module_fixed_point`
(S171) and their producer-family siblings (S172):
`test_workspace_assembly_has_one_public_module_and_no_private_or_package_binding_remnant`
(direct-import identity plus `application.modelo` package-attribute absence)
and `test_workspace_assembly_forbidden_private_paths_have_not_reappeared_in_the_tracked_tree`
(a `git ls-files`-scoped scan for `_workspace.py`/`_workspace_projection.py`
under `application/modelo/`, never a filesystem walk, per the two live
lessons from today: a gitignored mirror or an in-flight peer deletion can
make a filesystem walk lie in either direction, while `git ls-files` answers
what the tree actually tracks and a path present in that list but absent
from disk is skipped as someone else's in-progress deletion rather than
failed on).

Two real false-positive traps surfaced building the second test and are
recorded here so the next remnant scan does not repeat them. First, a bare
`entry.endswith("/_workspace.py")` match caught two unrelated, legitimate
files sharing the filename by coincidence:
`src/cadrumo-harness/src/cadrumo_harness/_workspace.py` and
`src/cadrumo/core/telemetry/_workspace.py`, neither a Modelo Workspace V1
predecessor. Narrowed to an exact `application/modelo/` path match. Second,
a bare `"_workspace_projection"` substring match caught the real, sanctioned
`modelo_workspace_projection_schema_fingerprint` symbol (defined in
`workspace_producers.py`, exercised by `test_workspace_producers.py`) and
the real test name
`test_workspace_projection_preserves_canonical_readiness_closure_and_capability_coordinates`
in `test_workspace_models.py`. Narrowed the prose scan to the literal
`"_workspace_projection.py"` module filename (with extension), and
additionally excluded `workspace.py`'s own module docstring, which
deliberately documents `_workspace_projection.py` as the REJECTED
intermediate design S128 chose against -- an accurate historical record,
not a stale reference to something that still exists. A gate that reds on
legitimate code is worse than no gate at all; both traps would have done
exactly that.

`dev/tests/test_import_hygiene_gate.py` carries 6 pre-existing failures at
the HEAD this Step's verification ran against
(`test_production_family1_violations_do_not_exceed_baseline_count`,
`test_production_family1_violations_are_exactly_the_named_baseline_set`,
`test_test_only_underscore_reaches_do_not_exceed_test_debt_count`,
`test_test_only_underscore_reaches_are_exactly_the_named_test_debt_set`,
`test_every_test_debt_entry_answers_a_live_occurrence`,
`test_family2_delegate_wrapper_shims_are_exactly_the_documented_exemptions`).
None reference "workspace" anywhere in their failure output; all are
baseline-count/named-set drift from unrelated concurrent commits landing
elsewhere in this fast-moving shared tree. Reported, not fixed: out of this
Step's scope, and re-baselining a gate against a tree state this Step did
not cause would misattribute someone else's drift to this commit.

This commit (`3d42a90a15`) landed on the shared worktree's checked-out
branch, `docs/reconcile-bucket-claim`, not `main` -- a peer switched the
shared checkout away from `main` before this Step began and it was never
switched back, a divergence the team lead is routing to the operator for
reconciliation. Recorded here for provenance; not this Step's defect to fix
and not blocking this Step's closure.
