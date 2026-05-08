"""Unit tests for setup readiness and next-action projection."""

from __future__ import annotations

import pytest

from .setup_status import build_setup_status
from .user_cli import UserCliState, set_active_profile, set_profile_values, update_auth

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_setup_status_without_profile_points_to_profile_creation() -> None:
    report = build_setup_status(UserCliState())

    assert report.active_profile is None
    assert report.profile_ready is False
    assert report.missing_required == ()
    assert report.profile_present_keys == 0
    assert report.profile_total_keys > 0
    assert report.next_action == "aeat setup init --name NAME"


def test_setup_status_with_missing_required_profile_key_points_to_first_missing_key() -> None:
    state = set_active_profile(UserCliState(), "operator")

    report = build_setup_status(state)

    assert report.profile_ready is False
    assert report.missing_required[0] == "tax.id"
    assert report.next_action == "aeat setup profile set tax.id VALUE"


def test_setup_status_with_complete_profile_points_to_auth_configuration() -> None:
    state = set_profile_values(
        UserCliState(),
        "operator",
        {
            "tax.id": "12345678Z",
            "activity": "design",
            "iva.regime": "general",
        },
    )

    report = build_setup_status(state)

    assert report.profile_ready is True
    assert report.identity_ready is True
    assert report.enrolment_ready is True
    assert report.missing_required == ()
    assert report.missing_enrolment == ()
    assert report.profile_present_keys == 3
    assert report.profile_total_keys > report.profile_present_keys
    assert report.auth_provider == ""
    assert report.next_action == "aeat setup auth configure --provider certificate --file PATH"


def test_setup_status_with_identity_only_remains_not_ready_until_enrolment_declared() -> None:
    """A profile carrying just the required identity keys must NOT report ready.

    UX-006 root cause: ``profile_ready`` previously returned ``True`` as
    soon as ``tax.id`` and ``activity`` were set, even though the
    deadline engine could not compute IVA obligations without an IVA
    regime declaration. The new contract gates ``profile_ready`` on
    BOTH identity and enrolment readiness.
    """
    state = set_profile_values(
        UserCliState(),
        "operator",
        {
            "tax.id": "12345678Z",
            "activity": "design",
        },
    )

    report = build_setup_status(state)

    assert report.identity_ready is True
    assert report.enrolment_ready is False
    assert report.profile_ready is False
    assert report.missing_enrolment == ("iva.regime",)
    assert report.next_action == "aeat setup profile set iva.regime general"


def test_setup_status_with_provider_points_to_login_until_session_ready() -> None:
    state = set_profile_values(
        UserCliState(),
        "operator",
        {
            "tax.id": "12345678Z",
            "activity": "design",
            "iva.regime": "general",
        },
    )
    state = update_auth(state, provider="clave_movil")

    report = build_setup_status(state)

    assert report.auth_provider == "clave_movil"
    assert report.login_ready is False
    assert report.next_action == "aeat setup auth login"


def test_setup_status_with_verified_session_points_to_app_overview() -> None:
    state = set_profile_values(
        UserCliState(),
        "operator",
        {
            "tax.id": "12345678Z",
            "activity": "design",
            "iva.regime": "general",
        },
    )
    state = update_auth(state, provider="clave_movil")
    state = update_auth(state, authenticated=True, subject="12345678Z")

    report = build_setup_status(state)

    assert report.login_ready is True
    assert report.next_action == "aeat app overview status"
