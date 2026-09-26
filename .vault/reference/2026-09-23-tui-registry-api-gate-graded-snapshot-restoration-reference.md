---
tags:
  - '#reference'
  - '#tui-registry-api-gate'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:eb75e9e288af04bf47c37ab4327789d7101899c7766f6060785e43dfa8684a5a'
related:
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-09-04-reachability-burndown-adr]]"
---

# `tui-registry-api-gate` reference: `graded snapshot restoration inventory`

What the graded-snapshot workspace admission was, why it was removed, what
changed in the contracts it depended on, and where it would plug into the TUI.
Read at the tree before the removal (`a23276d2d0~1`) and at `ab9ae2d093` on
`tui/modelo`.

## Summary

### Why it was removed

The graded path never had a production caller. At `a23276d2d0~1` the only
non-test mention of `resolve_graded_snapshot_result` is a docstring in
`src/cadrumo/entrypoints/tui/modelo/view/results.py:23`. The symbol-usage gate
(`dev/quality/unused_symbol_coverage.py`, `just check-symbol-usage`, test
references do not count, `dev/audit/unreachable_code.py:1`) therefore flagged
it, and `a23276d2d0` removed it. Restoring the code without a production call
site in the TUI launcher would repeat that.

### What the removal deleted

- `src/cadrumo/application/modelo/workspace.py` at `a23276d2d0~1`:
  - `resolve_graded_snapshot_result` (:1743)
  - `graded_snapshot_modelo_workspace_capabilities` (:558)
  - `resolve_graded_snapshot_schema_identity` (:871)
  - `graded_snapshot_evidence_horizon` (:895)
  - `graded_snapshot_contributors` (:910), eight contributors
  - `resolve_graded_snapshot_baseline` (:998)
  - `graded_snapshot_casilla_schema_records` (:1167) and `graded_snapshot_schema_records` (:1247)
  - `graded_snapshot_family_dispositions` (:1612)
  - `graded_snapshot_materialization_facet` (:2048)
  - `graded_snapshot_provenance_facet` (:2095)
  - `graded_snapshot_closure_limbs` (:2144) and `graded_snapshot_readiness` (:2167)
  - `resolve_modelo_workspace_target` (:367) and `capture_modelo_workspace_target_axes` (:343)
- `workspace_producers.py`: the atomic projection, bounded-review, calculation,
  readiness and closure ports (:228, :530, :597, :641, :679).
- The owners' capture functions: `calculation.py:177`, `work_review.py:387`,
  `state_projection.py:1440`, and the whole of `application/registry/closure_capture.py`.
- Three `*_capture_not_current` keys in every `errors.yml`.
- TUI: `admit_workspace_session` (`view/controller.py:199`), `refusal_view`,
  `constraint_disclosure`, `disposition_glyph` and `ModeloWorkspaceRefusalViewV1`
  (`view/models.py:234`, `:258`).
- The graded tests in `test_workspace.py`, and all of
  `test_workspace_projection.py` and `test_workspace_dependency_receipt.py`.

These survived: the graded result and scope models
(`workspace_models.py:1104`, `:979`, `:949`), the readiness family
(`:862`-`:946`), the materialization and provenance records (`:613`-`:666`),
the refusal models (`:1121`, `:1151`), and the graded validators
(`_workspace_model_validation.py:156`-`:200`).

### Current admission

- Only static inspection is admitted: `resolve_static_inspection_result`
  (`workspace.py:1084`) captures four contributors (`:663`). Its capability
  table is at `:448`-`:472`, and it always sets `STATIC_INSPECTION_WORK_REVIEW_FACET` (`:132`).
- The registry half of graded admission is still wired.
  `capture_modelo_workspace_target_captures(..., grade=None)` (`workspace.py:260`)
  passes a grade through `ModeloWorkspaceRegistryPortV1`
  (`workspace_producers.py:405`) to `capture_law_selected_projection(grade=...)`
  (`src/cadrumo/domain/calculations/registry/authority.py:811`).
- The module docstring (`workspace.py:13`-`:19`) still calls graded admission
  "not yet built" and cites a vault record from source.

### Contract changes since the graded code was written

1. The closure contributor is gone. `ModeloWorkspaceContributorKindV1` has
   seven members (`workspace_producers.py:68`-`:77`), and closure limbs are no
   longer in the projection (`38b2a9b1f5`). The API-gate decision still lists eight.
2. `FILING_EXPORT_READINESS` is gone: `ModeloWorkspaceCapabilityName` has four
   members (`workspace_models.py:111`-`:117`), and `ProjectionV1` checks the
   exact count (`:1014`-`:1017`). Static admission attributes
   `VERIFICATION_READINESS` to bounded review (`workspace.py:463`).
3. The second-pass currentness read (`read_current_stamp_and_epoch`, the
   atomic port protocol) was removed in `109234fcb0`. The API-gate decision
   still requires it.
4. The owners' capture and current-coordinate pairs have to be re-authored:
   calculation, work review and readiness.
5. `build_modelo_work_review` now takes a `PinnedAuthorityOperation` (`work_review.py:210`).
6. Readiness has no public per-request producer. `_build_modelo_readiness` is
   private (`state_projection.py:917`).
7. Relations were absorbed into bindings: `BindingDefinition`, endpoint helpers
   at `workspace.py:593`-`:622`, and no `relations` on `ModeloRevision`
   (`src/cadrumo/domain/calculations/registry/schema.py:693`).
8. Work selection moved to `work_selection.py`.
9. Casilla labels arrive through the batched locale port (`0901ef1134`).
10. The authority parameter is the `RegistryAuthorityCapturePort` protocol (`workspace_producers.py:46`).
11. Workspace errors now derive from `CadrumoError`.

### The TUI today

- Production reads go through one path:
  - `launcher.py:362` `_modelo_projection_reader` calls
    `resolve_modelo_workspace_static_inspection` (`launcher.py:1165`).
  - `workbench_generation.py:540` and `:775` call it for each unit.
  - `tui/modelo/installed_workspace.py:120` opens the session.
- The reader type has no refusal arm.
- Results (`view/results.py:58`-`:73`) needs an available work-review facet.
- Inputs (`view/inputs.py:162`) shows `values_unmeasured`.
- Verification (`view/verification.py:151`) shows findings and readiness as unmeasured.
- So no destination renders a value today, although each renderer already
  handles the graded facets.
- The repositories graded admission needs are already composed at `launcher.py:145`-`:154`.

### Reachability instruments

- `dev/quality/unused_symbol_coverage.py`: symbol-level, and not in the aggregate CI checks.
- `dev/quality/unreachable_module_coverage.py`: module-level only.
- `dev/tests/test_workspace_field_population_gate.py` over
  `dev/quality/workspace_field_population_scan.py`. Measured read-only on
  2026-09-24: 33 unfilled fields against an 11-entry register, so it is red.
  Most of the 22 unregistered fields are ones a production graded path fills.
- `2026-09-04-reachability-burndown-adr` forbids name allowlists in a gate. A
  "stays reached" guard has to be behavioural: drive the real launcher reader
  over a calculated unit and see a value on Results.

### Implementation history

The graded implementation is recorded in the `2026-08-11-tui-architecture` plan,
Steps S128, S287, S290, S296, S300 and S356; S353, the unfilled-field
burndown, is still open. No record cites the removal commit.
