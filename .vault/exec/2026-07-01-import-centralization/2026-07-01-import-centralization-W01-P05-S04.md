---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S04'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Promote `CensoSnapshot`, `CensoSnapshotService`, `PersistedExpedientesSnapshot`, `PersistedNotificationsSnapshot`, `VerifyObservation`, `censo_snapshot_object_key`, `expedientes_snapshot_object_key`, `notifications_snapshot_object_key`, `verify_observation_object_key` to `aeat.application.live.__all__` with eager re-exports so the 12 existing cross-package consumer site(s) can import from the facade

## Scope

- `src/aeat/application/live/__init__.py`

## Description

This record covers the full Wave W01 facade-promotion batch dispatched for three
owning packages: `aeat.application.live` (W01.P05.S04), `aeat.domain.iva_compensation`
(W01.P06.S05, W01.P06.S06), and `aeat.application.calculations` (W01.P11.S12,
W01.P11.S13, W01.P11.S14).

- Promote `CensoSnapshot`, `CensoSnapshotService`, and `censo_snapshot_object_key` as
  eager re-exports (the `_censo` submodule was already loaded eagerly for
  `CensoSnapshotNotFoundError`) in `aeat.application.live.__init__`.
- Extend the existing lazy `__getattr__` dispatch table in `aeat.application.live` to
  cover `PersistedExpedientesSnapshot`, `expedientes_snapshot_object_key`,
  `PersistedNotificationsSnapshot`, `notifications_snapshot_object_key`,
  `VerifyObservation`, and `verify_observation_object_key` — matching the package's
  established lazy-load convention for its heavier service submodules.
- Promote `DEFAULT_MAX_WALLET_AGE_DAYS`, `IvaCompensationAuthoritySource`,
  `IvaCompensationReconciliationDecision`, `IvaCompensationWalletObservationProtocol`,
  `local_recurrence_authority_source`, `reconcile_iva_compensation_wallet`, and
  `validate_wallet_matches_snapshot` to `aeat.domain.iva_compensation.__all__`.
- Underscore disposition (i): rename `_period_sort_key` to public
  `iva_compensation_period_sort_key` at its definition site in `_carry_forward.py`
  (two internal call sites updated) and promote it through the package facade; the
  sole external consumer (`aeat.application.calculations._iva_compensation_history`)
  now imports the symbol from the `aeat.domain.iva_compensation` facade instead of the
  private `_carry_forward` submodule.
- Promote `M111_NO_RETENCIONES_PROFILE_PATH`, `MaritimeExemptionResult`, and
  `m111_no_retenciones_periods_for_bucket` to `aeat.application.calculations.__all__`.
- Underscore disposition (ii): rename `_IvaWalletDecisionEnvelopePayload` to public
  `IvaWalletDecisionEnvelopePayload` at its definition site in
  `_observations_repository.py` (narrow purpose-built promotion — the sole external
  reach is the custody-carry generic natural-key resolver in
  `aeat.application.user_profile._custody_carry`, which is updated to the new name)
  and promote it through the facade.
- Underscore disposition (ii): rename `_MODELO_303_IVA_COMPENSATION_BINDING_ID` to
  public `MODELO_303_IVA_COMPENSATION_BINDING_ID` at its definition site in
  `_binding_prefill.py` and promote it through the facade; the sole external consumer
  (`aeat.application.modelo._calculation_actions`, three call sites) and its
  regression test (`test_local_cross_period_carry.py`) now import the constant from
  the `aeat.application.calculations` facade instead of the private
  `_binding_prefill` submodule.
- Ran `ruff check --fix` on every touched file (import-sort only; zero remaining
  findings) and confirmed no line exceeds the project's 120-column limit.
- Isolated two files that carried unrelated in-flight peer WIP
  (`_calculation_actions.py`: an M131 objective-estimation data-base projection;
  `_custody_carry.py`: a UTF-8 constant + type-ignore-rationale sweep) by building
  HEAD-anchored patches containing only this Step's renames and staging them via
  `git apply --cached`, per the worktree apply-cached-own-only discipline, rather
  than committing the peer's uncommitted lines.

## Outcome

All three facades resolve every promoted/renamed symbol
(`aeat.application.live`, `aeat.domain.iva_compensation`,
`aeat.application.calculations`) confirmed via a live import probe. `ruff check`
clean on all ten touched files. `pytest --collect-only -q src/aeat` exits 0 with
14517-14557 tests collected (no collection errors; the small count drift between runs
is unrelated deselection noise from peer test-marker churn, not a regression here).
Targeted test run (`test_local_cross_period_carry.py`,
`application/calculations/tests`, `domain/iva_compensation/tests`,
`application/live/tests`, `test_custody_roundtrip.py`, `test_custody_store_matrix.py`)
passed 651/651. No consumer files were mechanically rewritten beyond the specific
per-symbol underscore-disposition sites named in the Step rows above — the bulk
Wave W02 consumer sweep remains out of scope for this dispatch.

## Notes

Two touched files (`src/aeat/application/modelo/_calculation_actions.py`,
`src/aeat/application/user_profile/_custody_carry.py`) held substantial uncommitted
peer WIP at edit time that was not checked via `git diff` before the first edit (a
process gap against the worktree-safety discipline). No data was lost: the peer WIP
was verified untouched in the working tree and excluded from the staged commit via
the apply-cached patch technique described above. Future dispatches in this shared
worktree should run `git diff -- <file>` before the first edit to every file, not
only the package `__init__.py` facades.
