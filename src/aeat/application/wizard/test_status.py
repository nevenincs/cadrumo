"""Structural / wiring assertions on the wizard status surface.

The tests pin the report shape and the projection from
``WorkflowState`` into :class:`WizardStatusReport`. No arithmetic is
exercised: the report is the structural contract that doctor and
``aeat config status`` both read from.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aeat.application.profile._actions import set_active_profile, set_profile_values
from aeat.application.wizard._status import (
    WizardStatusError,
    WizardStatusReport,
    build_wizard_status,
    load_active_autonomo_profile,
)
from aeat.application.workflow._models import WorkflowState

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_empty_state_yields_no_active_profile_report() -> None:
    state = WorkflowState()
    report = build_wizard_status(state)
    assert isinstance(report, WizardStatusReport)
    assert report.active_profile is None
    assert report.identity_ready is False
    assert report.enrolment_ready is False
    assert report.profile_ready is False


def test_active_profile_without_iva_regime_is_identity_ready_only() -> None:
    state = set_active_profile(
        set_profile_values(WorkflowState(), "operator", {"tax.id": "12345678Z", "activity": "design"}),
        "operator",
    )
    report = build_wizard_status(state)
    assert report.active_profile == "operator"
    assert report.identity_ready is True
    assert report.enrolment_ready is False
    assert report.profile_ready is False
    assert "iva.regime" in report.missing_enrolment


def test_active_profile_with_identity_and_iva_regime_is_profile_ready() -> None:
    state = set_active_profile(
        set_profile_values(
            WorkflowState(),
            "operator",
            {"tax.id": "12345678Z", "activity": "design", "iva.regime": "GENERAL"},
        ),
        "operator",
    )
    report = build_wizard_status(state)
    assert report.identity_ready is True
    assert report.enrolment_ready is True
    assert report.profile_ready is True
    assert report.missing_enrolment == ()


def test_next_action_for_empty_state_directs_to_aeat_config_init() -> None:
    state = WorkflowState()
    report = build_wizard_status(state)
    assert report.next_action.startswith("aeat config init")


def test_report_is_strict_frozen_pydantic_v2() -> None:
    model_config = WizardStatusReport.model_config
    assert model_config.get("strict") is True
    assert model_config.get("frozen") is True
    assert model_config.get("extra") == "forbid"
    # The report rejects unknown fields per extra="forbid"
    with pytest.raises(ValidationError):
        WizardStatusReport.model_validate(
            {
                "active_profile": None,
                "profile_ready": False,
                "profile_present_keys": 0,
                "profile_total_keys": 0,
                "auth_provider": "",
                "login_ready": False,
                "next_action": "x",
                "unknown_field": "rejected",
            }
        )


def test_load_active_autonomo_profile_raises_wizard_status_error_when_no_profile() -> None:
    state = WorkflowState()
    with pytest.raises(WizardStatusError):
        load_active_autonomo_profile(state)


def test_load_active_autonomo_profile_raises_wizard_status_error_when_tax_id_missing() -> None:
    state = set_active_profile(
        set_profile_values(WorkflowState(), "operator", {"activity": "design"}),
        "operator",
    )
    with pytest.raises(WizardStatusError):
        load_active_autonomo_profile(state)
