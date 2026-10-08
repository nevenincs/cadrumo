"""Pure CLI contract checks for workstation preflight rows."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .....application.preflight import HealthSeverity
from ..check_payloads import CheckDependencyPayload, CheckPreflightPayload, ConfigCheckResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_config_check_payload_rows_refuse_empty_ids_and_unknown_severity() -> None:
    """The workstation result retains its typed dependency and preflight row schemas."""
    assert set(ConfigCheckResult.model_fields) == {
        "profile_id",
        "ok",
        "capabilities",
        "dependencies",
        "preflight",
        "issues",
    }
    assert set(CheckDependencyPayload.model_fields) == {"service", "available", "facts", "precondition_action"}
    assert set(CheckPreflightPayload.model_fields) == {
        "check",
        "healthy",
        "severity",
        "facts",
        "precondition_action",
    }
    with pytest.raises(ValidationError):
        CheckDependencyPayload(service="", available=True)
    with pytest.raises(ValidationError):
        CheckPreflightPayload(check="", healthy=True, severity=HealthSeverity.OK)
    with pytest.raises(ValidationError):
        CheckPreflightPayload(check="storage:local-root", healthy=True, severity="bogus")
