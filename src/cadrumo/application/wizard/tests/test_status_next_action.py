"""Focused contracts for the typed wizard-status forward action."""

from __future__ import annotations

import pytest

from .._status import _next_wizard_action

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_next_wizard_action_returns_setup_command_when_no_profile() -> None:
    """No profile label is known and custody no longer permits wizard create."""
    assert (
        _next_wizard_action(
            has_profile=False,
            missing_required=("nif", "iae"),
            missing_enrolment=("iva",),
            auth_provider="certificate",
            login_ready=True,
        )
        is None
    )


def test_next_wizard_action_returns_profile_edit_command_when_missing_required() -> None:
    """A status report cannot materialise an edit without its target label."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=("nif",),
            missing_enrolment=("iva",),
            auth_provider="certificate",
            login_ready=True,
        )
        is None
    )


def test_next_wizard_action_collapses_multiple_missing_required_fields_to_profile_edit() -> None:
    """Multiple missing fields still leave the edit target unresolved."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=("nif", "iae", "tax_residence_ccaa"),
            missing_enrolment=(),
            auth_provider="certificate",
            login_ready=True,
        )
        is None
    )


def test_next_wizard_action_returns_profile_edit_command_when_missing_enrolment() -> None:
    """Enrolment repair likewise has no resolved profile label here."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=(),
            missing_enrolment=("iva",),
            auth_provider="certificate",
            login_ready=True,
        )
        is None
    )


def test_next_wizard_action_returns_auth_setup_command_when_no_auth_provider() -> None:
    """Configuration needs a certificate file the status projection lacks."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=(),
            missing_enrolment=(),
            auth_provider="",
            login_ready=False,
        )
        is None
    )


def test_next_wizard_action_returns_auth_login_command_when_not_login_ready() -> None:
    """The configured provider fully materialises the registered login action."""
    action = _next_wizard_action(
        has_profile=True,
        missing_required=(),
        missing_enrolment=(),
        auth_provider="certificate",
        login_ready=False,
    )
    assert action is not None
    assert action.action.action_id == "operator.auth.login"
    assert {binding.argument_name: binding.value for binding in action.argument_bindings} == {"provider": "certificate"}


def test_next_wizard_action_uses_configured_auth_provider() -> None:
    action = _next_wizard_action(
        has_profile=True,
        missing_required=(),
        missing_enrolment=(),
        auth_provider="clave_movil",
        login_ready=False,
    )
    assert action is not None
    assert action.action.action_id == "operator.auth.login"
    assert {binding.argument_name: binding.value for binding in action.argument_bindings} == {"provider": "clave_movil"}


def test_next_wizard_action_returns_app_overview_status_in_happy_path() -> None:
    """No registered, fully-addressable overview action exists on this surface."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=(),
            missing_enrolment=(),
            auth_provider="certificate",
            login_ready=True,
        )
        is None
    )


def test_next_wizard_action_missing_required_wins_precedence_over_missing_enrolment() -> None:
    """The dispatcher's precedence chain places missing_required
    strictly above missing_enrolment. A regression that swapped these
    branches would surface a wrong-namespace suggestion to the operator."""
    suggestion = _next_wizard_action(
        has_profile=True,
        missing_required=("nif",),
        missing_enrolment=("iva",),
        auth_provider="certificate",
        login_ready=True,
    )

    assert suggestion is None


def test_next_wizard_action_missing_enrolment_wins_precedence_over_auth() -> None:
    """Once missing_required is empty, missing_enrolment takes
    precedence over an unconfigured auth provider — the wizard
    completes profile enrolment before configuring authentication."""
    suggestion = _next_wizard_action(
        has_profile=True,
        missing_required=(),
        missing_enrolment=("iva",),
        auth_provider="",
        login_ready=False,
    )

    assert suggestion is None
