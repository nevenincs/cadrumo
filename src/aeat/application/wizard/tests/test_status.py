"""Structural / wiring assertions on the wizard status surface.

The tests pin the report shape and the projection from
``WorkflowState`` into :class:`WizardStatusReport`. No arithmetic is
exercised: the report is the structural contract that doctor and
``aeat config status`` both read from.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile._orchestration import profile_create_storage_span, profile_storage_session
from ...user_profile._testing import register_minimal_profile
from ...workflow._models import WorkflowState
from .._status import (
    WizardStatusError,
    WizardStatusReport,
    build_wizard_status,
    load_active_taxpayer_profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _file_backed_profile_store(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _register_profile_state(
    state: WorkflowState,
    *,
    profile_id: str,
    overrides: Mapping[str, str] | None = None,
) -> WorkflowState:
    with profile_create_storage_span(profile_id):
        return register_minimal_profile(
            state,
            profile_id=profile_id,
            overrides=overrides,
        )


def test_empty_state_yields_no_active_profile_report() -> None:
    state = WorkflowState()
    report = build_wizard_status(state)
    assert isinstance(report, WizardStatusReport)
    assert report.active_profile is None
    assert report.identity_ready is False
    assert report.enrolment_ready is False
    assert report.profile_ready is False


def test_active_profile_with_identity_and_iva_regime_is_profile_ready() -> None:
    state = _register_profile_state(
        WorkflowState(),
        profile_id="operator",
        overrides={"activities.description": "design"},
    )
    with profile_storage_session("operator"):
        report = build_wizard_status(state)
    assert report.active_profile == "operator"
    assert report.identity_ready is True
    assert report.enrolment_ready is True
    assert report.profile_ready is True
    assert report.missing_enrolment == ()


def test_next_action_for_empty_state_directs_to_profile_create() -> None:
    state = WorkflowState()
    report = build_wizard_status(state)
    assert report.next_action == "aeat config profile create NAME"


def test_report_is_strict_frozen_pydantic_v2() -> None:
    model_config = WizardStatusReport.model_config
    assert model_config.get("strict") is True
    assert model_config.get("frozen") is True
    assert model_config.get("extra") == "forbid"
    # The report rejects unknown fields per extra="forbid"
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        WizardStatusReport.model_validate(
            {
                "profile_ready": False,
                "profile_present_keys": 0,
                "profile_total_keys": 0,
                "auth_provider": "",
                "login_ready": False,
                "next_action": "x",
                "unknown_field": "rejected",
            },
        )


def test_load_active_taxpayer_profile_raises_wizard_status_error_when_no_profile() -> None:
    state = WorkflowState()
    with pytest.raises(WizardStatusError) as exc_info:
        load_active_taxpayer_profile(state)
    context = exc_info.value.context
    assert context is not None
    assert context["workflow_state"] == "no_active_profile"


def test_load_active_taxpayer_profile_returns_taxpayer_record_for_minimal_profile() -> None:
    state = _register_profile_state(
        WorkflowState(),
        profile_id="operator",
        overrides={"activities.description": "design", "identity.tax_id": "00000000T"},
    )
    with profile_storage_session("operator"):
        profile = load_active_taxpayer_profile(state)
    assert profile.tax_id == "00000000T"
