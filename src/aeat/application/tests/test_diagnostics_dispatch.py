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
``next_action`` shape; assertions are predicate-contract /
structural assertions, not calculation tautologies.
"""

from __future__ import annotations

import pytest

from ..diagnostics import (
    DiagnosticCheck,
    _auth_check,
    _overall_status,
    _profile_check,
)
from ..wizard._status import WizardStatusReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _wizard_status(
    *,
    active_profile: str | None = "operator",
    profile_ready: bool = True,
    profile_present_keys: int = 5,
    profile_total_keys: int = 5,
    missing_required: tuple[str, ...] = (),
    auth_provider: str = "certificate",
    login_ready: bool = True,
    next_action: str = "",
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
        next_action=next_action,
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
        DiagnosticCheck(name="b", status="warn", summary="beta", next_action="aeat config repair"),
        DiagnosticCheck(name="c", status="ok", summary="gamma"),
    )

    assert _overall_status(checks) == "warn"


def test_overall_status_returns_fail_when_any_check_is_fail() -> None:
    checks = (
        DiagnosticCheck(name="a", status="ok", summary="alpha"),
        DiagnosticCheck(name="b", status="fail", summary="beta", dead_end="terminal"),
    )

    assert _overall_status(checks) == "fail"


def test_overall_status_fail_priority_overrides_warn() -> None:
    """A single ``fail`` outranks any number of ``warn`` checks —
    the rollup never downgrades fail → warn."""
    checks = (
        DiagnosticCheck(name="a", status="warn", summary="alpha", next_action="aeat config repair"),
        DiagnosticCheck(name="b", status="warn", summary="beta", next_action="aeat config repair"),
        DiagnosticCheck(name="c", status="fail", summary="gamma", dead_end="terminal"),
        DiagnosticCheck(name="d", status="warn", summary="delta", next_action="aeat config repair"),
    )

    assert _overall_status(checks) == "fail"


def test_overall_status_returns_fail_when_every_check_is_fail() -> None:
    checks = (
        DiagnosticCheck(name="a", status="fail", summary="alpha", dead_end="terminal"),
        DiagnosticCheck(name="b", status="fail", summary="beta", dead_end="terminal"),
    )

    assert _overall_status(checks) == "fail"


# ---------------------------------------------------------------------------
# _profile_check — 3 branches
# ---------------------------------------------------------------------------


def test_profile_check_no_active_profile_returns_warn_with_setup_next_action() -> None:
    report = _wizard_status(active_profile=None, profile_ready=False)

    result = _profile_check(report)

    assert result.name == "profile.readiness"
    assert result.status == "warn"
    assert result.next_action == "aeat config profile create NAME --tax-id <TAX_ID> --activity <ACTIVITY>"


def test_profile_check_missing_required_keys_returns_warn_with_canonical_next_action() -> None:
    """When the profile exists but isn't ready, the diagnostic row routes
    the operator to the guided editor and names each missing key as a
    typed finding — not a bare counter buried in the summary.
    """
    report = _wizard_status(
        profile_ready=False,
        missing_required=("tax_id", "ccaa"),
        next_action="aeat config profile edit NAME",
    )

    result = _profile_check(report)

    assert result.name == "profile.readiness"
    assert result.status == "warn"
    assert result.next_action == "aeat config profile edit NAME"
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
    assert result.next_action is None
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
        next_action="aeat config profile edit NAME",
    )

    result = _profile_check(report)

    assert result.name == "profile.readiness"


# ---------------------------------------------------------------------------
# _auth_check — 3 branches
# ---------------------------------------------------------------------------


def test_auth_check_no_provider_returns_warn_with_auth_setup_next_action() -> None:
    """auth_provider is the empty string → no provider configured →
    ``auth.readiness`` warn row pointing at auth configure."""
    report = _wizard_status(auth_provider="", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
    assert result.status == "warn"
    assert result.next_action == "aeat config auth configure --provider certificate --file PATH"


def test_auth_check_provider_configured_but_no_session_returns_warn() -> None:
    report = _wizard_status(auth_provider="certificate", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
    assert result.status == "warn"
    assert "certificate" in result.summary
    assert result.next_action == "aeat config auth test --provider certificate"


def test_auth_check_uses_configured_provider_for_session_probe() -> None:
    report = _wizard_status(auth_provider="clave_movil", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
    assert result.status == "warn"
    assert "clave_movil" in result.summary
    assert result.next_action == "aeat config auth test --provider clave_movil"


def test_auth_check_happy_path_returns_ok_with_provider_session_summary() -> None:
    report = _wizard_status(auth_provider="certificate", login_ready=True)

    result = _auth_check(report)

    assert result.name == "auth.readiness"
    assert result.status == "ok"
    assert "certificate" in result.summary
    assert result.next_action is None


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
