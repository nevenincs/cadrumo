"""Strict JSON payload checks for the bare config-repair report."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ...config_payloads import ConfigRepairResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _repair_payload() -> dict[str, object]:
    return {
        "overall": "warn",
        "package_name": "cadrumo",
        "package_version": "1.0.0",
        "python_version": "3.13",
        "log_file": "cadrumo.log",
        "registry": {
            "available": True,
            "registry_root": "registry",
            "modelo_count": 1,
            "revision_count": 1,
            "casilla_count": 2,
            "formula_count": 2,
            "revision_ids": ["modelo-303-v1"],
        },
        "setup": None,
        "secure_objects": {
            "namespaces": [{"namespace": "workflow", "readable": 1, "unreadable": 0}],
            "readable_total": 1,
            "unreadable_total": 0,
        },
        "checks": [
            {
                "name": "registry.load",
                "status": "warn",
                "summary": "Registry needs attention",
                "audience": "operator",
                "findings": [{"summary": "One revision is pending", "requirement": "required"}],
            },
        ],
    }


def test_config_repair_payload_projects_all_nested_sections() -> None:
    """A report-shaped JSON projection preserves each typed nested section."""

    result = ConfigRepairResult.model_validate(_repair_payload())

    assert result.overall == "warn"
    assert result.registry.revision_ids == ["modelo-303-v1"]
    assert result.secure_objects.namespaces[0].namespace == "workflow"
    assert result.checks[0].findings[0].requirement == "required"
    check_payload = result.checks[0].model_dump(mode="json")
    assert "next_action" not in check_payload
    assert "dead_end" not in check_payload
    assert "next_action" not in check_payload["findings"][0]


@pytest.mark.parametrize("retired_field", ("next_action", "dead_end"))
def test_config_repair_payload_refuses_retired_recovery_transport(retired_field: str) -> None:
    """The wire contract rejects legacy prose channels instead of emitting nulls."""

    payload = _repair_payload()
    checks = payload["checks"]
    assert isinstance(checks, list)
    check = checks[0]
    assert isinstance(check, dict)
    check[retired_field] = "legacy transport"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ConfigRepairResult.model_validate(payload)


def test_config_repair_setup_payload_refuses_wizard_next_action_transport() -> None:
    """The diagnostics wire projection cannot inherit wizard command prose."""

    payload = _repair_payload()
    payload["setup"] = {
        "active_profile": "demo",
        "profile_ready": True,
        "identity_ready": True,
        "enrolment_ready": True,
        "missing_required": [],
        "missing_enrolment": [],
        "profile_present_keys": 10,
        "profile_total_keys": 10,
        "auth_provider": "certificate",
        "login_ready": False,
        "next_action": "aeat config auth login",
    }

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ConfigRepairResult.model_validate(payload)


@pytest.mark.parametrize("overall", ("unknown", "", 1))
def test_config_repair_payload_refuses_noncanonical_overall_status(overall: object) -> None:
    """The outer repair verdict accepts only the diagnostic status vocabulary."""

    payload = _repair_payload()
    payload["overall"] = overall

    with pytest.raises(ValidationError):
        ConfigRepairResult.model_validate(payload)


@pytest.mark.parametrize(
    "checks",
    (
        [{}],
        [{"name": "registry.load", "status": "unknown", "summary": "bad", "audience": "operator", "findings": []}],
    ),
)
def test_config_repair_payload_refuses_malformed_check_rows(checks: object) -> None:
    """Each check must retain its complete, closed-vocabulary transport shape."""

    payload = _repair_payload()
    payload["checks"] = checks

    with pytest.raises(ValidationError):
        ConfigRepairResult.model_validate(payload)
