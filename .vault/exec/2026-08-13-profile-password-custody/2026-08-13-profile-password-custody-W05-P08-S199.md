---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:3e0ccb8dd4a569f501fcae7716a900452e658d92045e6f1a1c8397ef70cf0886'
step_id: 'S199'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium carry the newly distinguished locked-profile state into the diagnostics summary, where a locked profile keys off neither status set and falls through to a no-profile-configured sentence that is untrue of it, the surface still warning so nothing passes silently but telling the operator the wrong thing, and note the two authority gates first suspected of the same gap are in fact unreachable because both open the encrypted workflow state before consulting the verdict

## Scope

- `src/cadrumo/application/diagnostics.py and src/cadrumo/locales/`

## Description

- Add a dedicated `profile_locked` branch to both diagnostics readiness
  renderers (`_profile_unavailable_check` and `_profile_check`), ahead of the
  status sets that previously let it fall through.
- Add the operator-facing sentence as a new locale key,
  `cli.diagnostics.summary.profile_locked`, in all four catalogues through
  `python -m dev.locales set`, using the wording already shipped for the
  logged-out CLI refusal.
- Add two real-behaviour tests proving both directions: a cold environment
  with no profile still reports "no profile configured", and a genuinely
  locked (published, session-suspended) profile now reports the locked
  sentence and routes to `operator.profile.login`.
- Verify the two authority gates named in the row (the operator's configure
  path and the certificate-source gate) are unreachable for this state, as
  the originating `S173` audit claimed, rather than inheriting the claim.

## Outcome

**The fall-through is closed at both renderers, with its own sentence rather
than borrowed wording.** `_profile_unavailable_check` (used when the
diagnostics secure-state probe itself fails to open, which is exactly what
happens for a locked profile — the workflow-state read needs the same absent
session) and `_profile_check` (used when that probe succeeds) each gained a
`health.status == "profile_locked"` branch checked before their existing
status-set branches. Neither reuses `cli.diagnostics.summary.profile_unreadable`
(implies damage) or `cli.diagnostics.summary.profile_none` (implies nothing was
ever set up) — both are false of a locked profile, which is exactly the S173
finding this row closes.

**The precondition verdict needed no change.** `ActiveProfileHealth` already
carries the correct `operator.profile.login` verdict for `profile_locked`,
computed by `_health_precondition_verdict` in `_profile_health.py` (landed by
`S173`) and threaded through unchanged by `_required_profile_health_verdict`.
Only the `summary` string was wrong; the recovery action an operator would
actually run was already right.

**The locale key reuses shipped wording rather than inventing new prose.**
`cli.diagnostics.summary.profile_locked` carries, in all four catalogues, the
exact sentence already shipped as `cli.config.errors.profile_session_absent`
(re-verified against the live catalogues before use, since they moved same-day
— all four still matched byte-for-byte). Landed through
`python -m dev.locales set <locale> ...`, never by hand-editing a `.yml`.

**Both authority gates named in the row are confirmed unreachable, not
inherited as a claim.** Read `operator.configure` (auth path) and the
certificate-source gate: both open the encrypted workflow state before
consulting any health verdict, so a locked profile is refused by that load
(a `CadrumoError`/`OSError` from the absent session) before either branch on
the record-failure status set is ever reached. Their behaviour is genuinely
unchanged by this row.

**Two-way proof, both real.** `test_profile_readiness_reports_the_lock_rather_than_no_profile_configured`
publishes a real capsule via `isolated_runtime_profile`, suspends the real
active session with `suspend_active_session()` (no subprocess needed — the
lock probe is in-process structural, not dependent on process boundary), and
asserts the rendered `profile.readiness` summary equals the new translated
sentence and differs from the old one, with the verdict's action resolving to
`operator.profile.login`.
`test_profile_readiness_reports_no_profile_configured_when_genuinely_absent`
is the control: a cold environment with no registered profile still renders
the untouched "no profile configured" sentence, proving the new branch did
not swallow the genuine-absence case.

**The gate was proven to bite by a runtime patch from outside the repository.**
A pytest plugin loaded via `PYTHONPATH`/`-p`, touching no tracked file,
replaced `_profile_unavailable_check` with its pre-fix body (no
`profile_locked` branch). Under that patch the locked-profile test reds with
exactly the pre-fix defect — `'No hay perfil configurado'` where
`'No has iniciado sesión...'` was expected — while the absence-control test
stays green, confirming the new test exercises the fix and not something else.

## Notes

**No regression in the wider diagnostics suite.** The full
`application/tests/test_diagnostics.py` file (37 tests, run sequentially,
`-m "unit or integration"`) passes 35/37; the two failures
(`test_config_repair_report_contains_registry_and_setup_checks`,
`test_repair_auth_session_predicate_agrees_with_wizard_status`) both assert
`report.registry.available is True` and fail on a `RegistryValidationError`
from the concurrent registry authority-grade sweep — the known ambient
"registry authority failing to load tree-wide" defect, unrelated to
`profile.readiness` rendering and untouched by this row. The sibling `S173`
suite (`test_locked_profile_is_not_a_missing_record.py`) stays green
unchanged, 5/5.

**Row complete.** Both diagnostics renderers, the locale key (all four
catalogues), and the two-way proof are landed; the plan Step is left
unchecked per instruction for the dispatching session to close.
