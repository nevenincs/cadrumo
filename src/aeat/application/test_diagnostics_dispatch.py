"""Focused unit tests for diagnostics dispatch helpers.

Three private dispatch helpers back the config-doctor rendering:

- ``_overall_status(checks)`` — rolls up a tuple of
  :class:`DiagnosticCheck` into a single :class:`DiagnosticStatus`
  with priority ``fail`` > ``warn`` > ``ok``.
- ``_profile_check(report)`` — projects a
  :class:`WizardStatusReport` into the ``profile.*`` diagnostic
  row. Three branches: no active profile, missing required keys,
  happy path.
- ``_auth_check(report)`` — projects a
  :class:`WizardStatusReport` into the ``auth.*`` diagnostic row.
  Three branches: no provider, provider + no session, happy path.

Previously exercised only indirectly through
``test_config_doctor_report_contains_registry_and_setup_checks``,
which inspects the whole doctor report end-to-end and cannot pin
the branch semantics of each dispatch helper. A regression that
swapped the priority order in ``_overall_status`` (e.g. warn over
fail) would silently downgrade every doctor report's overall
status from fail → warn; the integration tests would still pass
if no individual check happened to be fail.

Tests pin each branch's :class:`DiagnosticStatus` and
``next_action`` shape; assertions are predicate-contract /
structural assertions, not calculation tautologies.
"""

from __future__ import annotations

import pytest

from .diagnostics import (
    DiagnosticCheck,
    _auth_check,
    _overall_status,
    _profile_check,
)
from .wizard._status import WizardStatusReport

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _wizard_status(
    *,
    active_profile: str | None = "kent",
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
        DiagnosticCheck(name="b", status="warn", summary="beta"),
        DiagnosticCheck(name="c", status="ok", summary="gamma"),
    )

    assert _overall_status(checks) == "warn"


def test_overall_status_returns_fail_when_any_check_is_fail() -> None:
    checks = (
        DiagnosticCheck(name="a", status="ok", summary="alpha"),
        DiagnosticCheck(name="b", status="fail", summary="beta"),
    )

    assert _overall_status(checks) == "fail"


def test_overall_status_fail_priority_overrides_warn() -> None:
    """A single ``fail`` outranks any number of ``warn`` checks —
    the rollup never downgrades fail → warn."""
    checks = (
        DiagnosticCheck(name="a", status="warn", summary="alpha"),
        DiagnosticCheck(name="b", status="warn", summary="beta"),
        DiagnosticCheck(name="c", status="fail", summary="gamma"),
        DiagnosticCheck(name="d", status="warn", summary="delta"),
    )

    assert _overall_status(checks) == "fail"


def test_overall_status_returns_fail_when_every_check_is_fail() -> None:
    checks = (
        DiagnosticCheck(name="a", status="fail", summary="alpha"),
        DiagnosticCheck(name="b", status="fail", summary="beta"),
    )

    assert _overall_status(checks) == "fail"


# ---------------------------------------------------------------------------
# _profile_check — 3 branches
# ---------------------------------------------------------------------------


def test_profile_check_no_active_profile_returns_warn_with_setup_next_action() -> None:
    report = _wizard_status(active_profile=None, profile_ready=False)

    result = _profile_check(report)

    assert result.name == "profile.active"
    assert result.status == "warn"
    assert result.next_action == "aeat config setup --profile-name NAME --tax-id NIF"


def test_profile_check_missing_required_keys_returns_warn_with_report_next_action() -> None:
    """When the profile exists but isn't ready, the renderer
    forwards the wizard status's own ``next_action`` so the
    doctor row points at the same remediation step the wizard
    reports."""
    report = _wizard_status(
        profile_ready=False,
        missing_required=("tax_id", "ccaa"),
        next_action="aeat config setup --tax-id NIF",
    )

    result = _profile_check(report)

    assert result.name == "profile.required_keys"
    assert result.status == "warn"
    assert result.next_action == "aeat config setup --tax-id NIF"
    assert "tax_id" in result.summary
    assert "ccaa" in result.summary


def test_profile_check_happy_path_returns_ok_with_present_total_summary() -> None:
    report = _wizard_status(
        profile_ready=True,
        profile_present_keys=4,
        profile_total_keys=4,
    )

    result = _profile_check(report)

    assert result.name == "profile.required_keys"
    assert result.status == "ok"
    assert result.next_action is None
    assert "4/4" in result.summary


def test_profile_check_active_profile_set_but_not_ready_does_not_short_circuit_to_active_branch() -> None:
    """The first branch keys on ``active_profile is None`` strictly.
    A non-None active_profile with profile_ready=False routes to
    the ``profile.required_keys`` branch, not ``profile.active``."""
    report = _wizard_status(
        active_profile="kent",
        profile_ready=False,
        missing_required=("tax_id",),
        next_action="aeat config setup --tax-id NIF",
    )

    result = _profile_check(report)

    assert result.name == "profile.required_keys"


# ---------------------------------------------------------------------------
# _auth_check — 3 branches
# ---------------------------------------------------------------------------


def test_auth_check_no_provider_returns_warn_with_auth_setup_next_action() -> None:
    """auth_provider is the empty string → no provider configured →
    ``auth.provider`` warn row pointing at ``aeat config auth``."""
    report = _wizard_status(auth_provider="", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.provider"
    assert result.status == "warn"
    assert result.next_action == "aeat config auth --provider certificate --file PATH"


def test_auth_check_provider_configured_but_no_session_returns_warn() -> None:
    report = _wizard_status(auth_provider="certificate", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.session"
    assert result.status == "warn"
    assert "certificate" in result.summary
    assert result.next_action == "aeat config auth --provider certificate"


def test_auth_check_happy_path_returns_ok_with_provider_session_summary() -> None:
    report = _wizard_status(auth_provider="certificate", login_ready=True)

    result = _auth_check(report)

    assert result.name == "auth.session"
    assert result.status == "ok"
    assert "certificate" in result.summary
    assert result.next_action is None


def test_auth_check_summary_carries_provider_name_under_session_warn() -> None:
    """A non-default provider (e.g. clave-movil) propagates into
    both the session-warn summary and the happy-path summary so
    operators can see which provider is configured."""
    report = _wizard_status(auth_provider="clave-movil", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.session"
    assert "clave-movil" in result.summary


def test_auth_check_no_provider_branch_wins_when_login_ready_is_also_false() -> None:
    """Branch ordering: the auth_provider falsy check fires first.
    A WizardStatusReport with both auth_provider='' and
    login_ready=False routes to ``auth.provider``, never
    ``auth.session``."""
    report = _wizard_status(auth_provider="", login_ready=False)

    result = _auth_check(report)

    assert result.name == "auth.provider"
