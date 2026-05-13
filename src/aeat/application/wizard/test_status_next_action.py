"""Focused unit tests for wizard._status._next_wizard_action.

`_next_wizard_action` is a five-branch dispatcher that maps wizard-
state into the next operator-facing CLI command suggestion. The
function is exercised only indirectly through the public
``build_wizard_status`` orchestrator's tests; a regression in branch
ordering (for example, swapping the missing_required and
missing_enrolment branches) would silently change the operator-facing
next-command suggestion across every wizard-status call.

Tests here are mapper-contract assertions on the dispatcher's
declared precedence rules, not calculation tautologies.
"""

from __future__ import annotations

import pytest

from ._status import _next_wizard_action

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_next_wizard_action_returns_setup_command_when_no_profile() -> None:
    """`has_profile=False` is the highest-precedence branch; every other
    argument is ignored when the operator has no profile yet."""
    assert (
        _next_wizard_action(
            has_profile=False,
            missing_required=("nif", "iae"),
            missing_enrolment=("iva",),
            auth_provider="certificate",
            login_ready=True,
        )
        == "aeat config init --profile NAME"
    )


def test_next_wizard_action_returns_set_required_command_when_missing_required() -> None:
    """When the profile exists but a required field is missing, the
    operator is pointed at the matching ``aeat config set <field> VALUE``."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=("nif",),
            missing_enrolment=("iva",),
            auth_provider="certificate",
            login_ready=True,
        )
        == "aeat config set nif VALUE"
    )


def test_next_wizard_action_names_first_missing_required_field_only() -> None:
    """The dispatcher picks ``missing_required[0]`` even when several
    fields are absent — operators address one at a time."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=("nif", "iae", "tax_residence_ccaa"),
            missing_enrolment=(),
            auth_provider="certificate",
            login_ready=True,
        )
        == "aeat config set nif VALUE"
    )


def test_next_wizard_action_returns_set_enrolment_command_when_missing_enrolment() -> None:
    """`missing_required=()` is the gate for the enrolment branch; once
    every required field is set, the dispatcher moves to the
    ``aeat config set <enrolment> GENERAL`` suggestion."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=(),
            missing_enrolment=("iva",),
            auth_provider="certificate",
            login_ready=True,
        )
        == "aeat config set iva GENERAL"
    )


def test_next_wizard_action_returns_auth_setup_command_when_no_auth_provider() -> None:
    """When the profile is complete but no auth provider is configured,
    the operator is pointed at the auth-provider setup flow."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=(),
            missing_enrolment=(),
            auth_provider="",
            login_ready=False,
        )
        == "aeat config auth --provider certificate --file PATH"
    )


def test_next_wizard_action_returns_auth_login_command_when_not_login_ready() -> None:
    """Auth provider is configured but login is not yet ready (e.g.,
    cert needs unlocking or session is stale) — operator is pointed at
    the auth login flow."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=(),
            missing_enrolment=(),
            auth_provider="certificate",
            login_ready=False,
        )
        == "aeat config auth --provider certificate"
    )


def test_next_wizard_action_returns_app_overview_status_in_happy_path() -> None:
    """Every state ready — the operator's next move is to use the app."""
    assert (
        _next_wizard_action(
            has_profile=True,
            missing_required=(),
            missing_enrolment=(),
            auth_provider="certificate",
            login_ready=True,
        )
        == "aeat app overview status"
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

    assert "nif" in suggestion
    assert "iva" not in suggestion


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

    assert "iva" in suggestion
    assert "auth" not in suggestion
