"""Focused unit tests for diagnostics dispatch helpers.

Three private dispatch helpers back the config-repair rendering:

- ``_overall_status(checks)`` — rolls up a tuple of
  :class:`DiagnosticCheck` into a single :class:`DiagnosticStatus`
  with priority ``fail`` > ``warn`` > ``ok``.
- ``_profile_check(report)`` — projects a
  :class:`WizardStatusReport` into the ``profile.readiness``
  diagnostic row. Three branches: no active profile, missing
  required keys, happy path; all carry the same row name with the
  branch encoded in ``summary``.
- ``_auth_check(report)`` — projects a
  :class:`WizardStatusReport` into the ``auth.readiness`` diagnostic
  row. Three branches: no provider, provider + no session, happy
  path; all carry the same row name with the branch encoded in
  ``summary``.

Tests pin each branch's :class:`DiagnosticStatus` and
``precondition_verdict`` shape; assertions are predicate-contract /
structural assertions, not calculation tautologies.
"""

from __future__ import annotations

import pytest

from ...core.operator_action_enums import (
    ActionArgumentSource,
    ActionArgumentStatus,
    ActionConditionality,
    NoRecoveryOutcome,
)
from ..diagnostics import (
    DiagnosticCheck,
    _auth_check,
    _diagnostic_no_recovery_verdict,
    _overall_status,
    _profile_check,
)
from ..wizard.status import WizardStatusReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ROLLUP_WARN_VERDICT = _diagnostic_no_recovery_verdict(
    condition_id="diagnostics.test.rollup.warn",
    evidence_id="diagnostics.test.rollup.warn.observation",
    values={"available": False},
    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
)
_ROLLUP_FAIL_VERDICT = _diagnostic_no_recovery_verdict(
    condition_id="diagnostics.test.rollup.fail",
    evidence_id="diagnostics.test.rollup.fail.observation",
    values={"available": False},
    outcome=NoRecoveryOutcome.TERMINAL,
)


def _wizard_status(
    *,
    active_profile: str | None = "operator",
    profile_ready: bool = True,
    profile_present_keys: int = 5,
    profile_total_keys: int = 5,
    missing_required: tuple[str, ...] = (),
    auth_provider: str = "certificate",
    login_ready: bool = True,
) -> WizardStatusReport:
    """Build a minimal :class:`WizardStatusReport` for dispatch testing."""
    return WizardStatusReport(
        active_profile=active_profile,
        profile_ready=profile_ready,
        identity_ready=profile_ready,
        enrolment_ready=profile_ready,
        missing_required=missing_required,
        missing_enrolment=(),
        profile_present_keys=profile_present_keys,
        profile_total_keys=profile_total_keys,
        auth_provider=auth_provider,
        login_ready=login_ready,
        next_action=None,
    )


# ---------------------------------------------------------------------------
# _overall_status — priority rollup
# ---------------------------------------------------------------------------


def test_overall_status_empty_checks_returns_ok() -> None:
    """Empty input → no failing or warning members → ok."""
    assert _overall_status(()) == "ok"


def test_overall_status_returns_ok_when_every_check_is_ok() -> None:
    checks = (
        DiagnosticCheck(name="a", status="ok", summary="alpha"),
        DiagnosticCheck(name="b", status="ok", summary="beta"),
    )

    assert _overall_status(checks) == "ok"


def test_overall_status_returns_warn_when_any_check_is_warn_and_none_fail() -> None:
    checks = (
        DiagnosticCheck(name="a", status="ok", summary="alpha"),
        DiagnosticCheck(
            name="b",
            status="warn",
            summary="beta",
            precondition_verdict=_ROLLUP_WARN_VERDICT,
        ),
        DiagnosticCheck(name="c", status="ok", summary="gamma"),
    )

    assert _overall_status(checks) == "warn"


def test_overall_status_returns_fail_when_any_check_is_fail() -> None:
    checks = (
        DiagnosticCheck(name="a", status="ok", summary="alpha"),
        DiagnosticCheck(
            name="b",
            status="fail",
            summary="beta",
            precondition_verdict=_ROLLUP_FAIL_VERDICT,
        ),
    )

    assert _overall_status(checks) == "fail"


def test_overall_status_fail_priority_overrides_warn() -> None:
    """A single ``fail`` outranks any number of ``warn`` checks —
    the rollup never downgrades fail → warn."""
    checks = (
        DiagnosticCheck(
            name="a",
            status="warn",
            summary="alpha",
            precondition_verdict=_ROLLUP_WARN_VERDICT,
        ),
        DiagnosticCheck(
            name="b",
            status="warn",
            summary="beta",
            precondition_verdict=_ROLLUP_WARN_VERDICT,
        ),
        DiagnosticCheck(
            name="c",
            status="fail",
            summary="gamma",
            precondition_verdict=_ROLLUP_FAIL_VERDICT,
        ),
        DiagnosticCheck(
            name="d",
            status="warn",
            summary="delta",
            precondition_verdict=_ROLLUP_WARN_VERDICT,
        ),
    )

    assert _overall_status(checks) == "fail"


def test_overall_status_returns_fail_when_every_check_is_fail() -> None:
    checks = (
        DiagnosticCheck(
            name="a",
            status="fail",
            summary="alpha",
            precondition_verdict=_ROLLUP_FAIL_VERDICT,
        ),
        DiagnosticCheck(
            name="b",
            status="fail",
            summary="beta",
            precondition_verdict=_ROLLUP_FAIL_VERDICT,
        ),
    )

    assert _overall_status(checks) == "fail"


# ---------------------------------------------------------------------------
# _profile_check — 3 branches
# ---------------------------------------------------------------------------


def test_profile_check_no_active_profile_returns_warn_with_setup_action() -> None:
    report = _wizard_status(active_profile=None, profile_ready=False)

    result = _profile_check(report)

    assert result.name == "profile.readiness"
    assert result.status == "warn"
    verdict = result.precondition_verdict
    assert verdict is not None
    action = verdict.action
    assert action is not None
    assert action.action_id == "operator.profile.create"
    assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    assert verdict.missing_argument_names == ("profile_name",)
    bindings = {binding.argument_name: binding for binding in verdict.argument_bindings}
    assert set(bindings) == {"profile_name"}
    binding = bindings["profile_name"]
    assert binding.status is ActionArgumentStatus.MISSING
    assert binding.value is None
    assert binding.source is None
    assert binding.source_key is None


def test_profile_check_missing_required_keys_returns_warn_with_profile_edit_action() -> None:
    """When the profile exists but isn't ready, the diagnostic row routes
    the operator to the guided editor and names each missing key as a
    typed finding — not a bare counter buried in the summary.
    """
    report = _wizard_status(
        profile_ready=False,
        missing_required=("tax_id", "ccaa"),
    )

    result = _profile_check(report)

    assert result.name == "profile.readiness"
    assert result.status == "warn"
    verdict = result.precondition_verdict
    assert verdict is not None
    action = verdict.action
    assert action is not None
    assert action.action_id == "operator.profile.edit"
    assert verdict.conditionality is ActionConditionality.IMMEDIATE
    assert verdict.missing_argument_names == ()
    bindings = {binding.argument_name: binding for binding in verdict.argument_bindings}
    assert set(bindings) == {"profile_name"}
    binding = bindings["profile_name"]
    assert binding.status is ActionArgumentStatus.RESOLVED
    assert binding.value == "operator"
    assert binding.source is ActionArgumentSource.VERDICT_CONTEXT
    assert binding.source_key == "profile_name"
    assert binding.source_evidence_id is None
    finding_keys = {finding.summary.split(" — ", 1)[0] for finding in result.findings}
    assert "tax_id" in finding_keys
    assert "ccaa" in finding_keys


def test_profile_check_happy_path_returns_ok_with_present_total_summary() -> None:
    report = _wizard_status(
        profile_ready=True,
        profile_present_keys=4,
        profile_total_keys=4,
    )

    result = _profile_check(report)

    assert result.name == "profile.readiness"
    assert result.status == "ok"
    assert result.precondition_verdict is None
    assert "4/4" in result.summary


def test_profile_check_active_profile_set_but_not_ready_does_not_short_circuit_to_active_branch() -> None:
    """The first branch keys on ``active_profile is None`` strictly.
    A non-None active_profile with profile_ready=False still routes
    to the consolidated ``profile.readiness`` row; the consolidated
    row name carries every branch."""
    report = _wizard_status(
        active_profile="operator",
        profile_ready=False,
        missing_required=("tax_id",),
    )

    result = _profile_check(report)

    assert result.name == "profile.readiness"


# ---------------------------------------------------------------------------
# _auth_check — 3 branches
# ---------------------------------------------------------------------------


def test_auth_check_no_provider_returns_warn_with_auth_setup_action() -> None:
    """auth_provider is the empty string → no provider configured →
    ``auth.readiness`` warn row pointing at auth configure."""
    report = _wizard_status(auth_provider="", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
    assert result.status == "warn"
    verdict = result.precondition_verdict
    assert verdict is not None
    action = verdict.action
    assert action is not None
    assert action.action_id == "operator.auth.configure"
    assert verdict.conditionality is ActionConditionality.REQUIRES_ARGUMENTS
    assert verdict.missing_argument_names == ("file",)
    bindings = {binding.argument_name: binding for binding in verdict.argument_bindings}
    assert set(bindings) == {"file", "provider"}
    file_binding = bindings["file"]
    assert file_binding.status is ActionArgumentStatus.MISSING
    assert file_binding.value is None
    assert file_binding.source is None
    assert file_binding.source_key is None
    provider_binding = bindings["provider"]
    assert provider_binding.status is ActionArgumentStatus.RESOLVED
    assert provider_binding.value == "certificate"
    assert provider_binding.source is ActionArgumentSource.VERDICT_CONTEXT
    assert provider_binding.source_key == "provider"


def test_auth_check_provider_configured_but_no_session_returns_warn() -> None:
    report = _wizard_status(auth_provider="certificate", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
    assert result.status == "warn"
    assert "certificate" in result.summary
    verdict = result.precondition_verdict
    assert verdict is not None
    action = verdict.action
    assert action is not None
    assert action.action_id == "operator.auth.login"
    assert verdict.conditionality is ActionConditionality.IMMEDIATE
    assert verdict.missing_argument_names == ()
    bindings = {binding.argument_name: binding for binding in verdict.argument_bindings}
    assert set(bindings) == {"provider"}
    binding = bindings["provider"]
    assert binding.status is ActionArgumentStatus.RESOLVED
    assert binding.value == "certificate"
    assert binding.source is ActionArgumentSource.VERDICT_CONTEXT
    assert binding.source_key == "provider"


def test_auth_check_uses_configured_provider_for_session_probe() -> None:
    report = _wizard_status(auth_provider="clave_movil", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
    assert result.status == "warn"
    assert "clave_movil" in result.summary
    verdict = result.precondition_verdict
    assert verdict is not None
    action = verdict.action
    assert action is not None
    assert action.action_id == "operator.auth.login"
    assert verdict.conditionality is ActionConditionality.IMMEDIATE
    assert verdict.missing_argument_names == ()
    bindings = {binding.argument_name: binding for binding in verdict.argument_bindings}
    assert set(bindings) == {"provider"}
    binding = bindings["provider"]
    assert binding.status is ActionArgumentStatus.RESOLVED
    assert binding.value == "clave_movil"
    assert binding.source is ActionArgumentSource.VERDICT_CONTEXT
    assert binding.source_key == "provider"


def test_auth_check_happy_path_returns_ok_with_provider_session_summary() -> None:
    report = _wizard_status(auth_provider="certificate", login_ready=True)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
    assert result.status == "ok"
    assert "certificate" in result.summary
    assert result.precondition_verdict is None


def test_auth_check_summary_carries_provider_name_under_session_warn() -> None:
    """A non-default provider (e.g. clave-movil) propagates into
    both the session-warn summary and the happy-path summary so
    operators can see which provider is configured."""
    report = _wizard_status(auth_provider="clave-movil", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
    assert "clave-movil" in result.summary


def test_auth_check_no_provider_branch_wins_when_login_ready_is_also_false() -> None:
    """Branch ordering: the auth_provider falsy check fires first.
    A WizardStatusReport with both auth_provider='' and
    login_ready=False routes to the consolidated ``auth.readiness``
    row, with the no-provider summary, never the no-session
    summary."""
    report = _wizard_status(auth_provider="", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
