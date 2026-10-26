"""The workstation check's CLI transport shape."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..check_payloads import CheckDependencyPayload, CheckPreflightPayload, ConfigCheckResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_GIB = 1024**3


def test_workstation_cli_result_keeps_the_closed_row_schemas() -> None:
    """The authenticated presenter retains the established JSON result rows."""
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
        CheckDependencyPayload(service="dependency", available=False, detail="legacy")
