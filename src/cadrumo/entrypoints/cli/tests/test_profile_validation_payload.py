"""Strict CLI projection contracts for profile-validation issues."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....application.user_profile.commands import ProfileValidationIssue
from ....core.errors import BaseSeverity
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from .._config_payloads import ProfileIssuePayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_profile_validation_payload_preserves_the_source_severity_enum() -> None:
    source = ProfileValidationIssue(
        severity=BaseSeverity.WARNING,
        code="effective_window_end_not_enforced",
        path=PROFILE_OUTPUT_LANGUAGE_PATH,
        message="a later fact should supersede this value",
    )
    payload = ProfileIssuePayload(
        severity=source.severity,
        code=source.code,
        path=source.path,
        message=source.message,
    )

    assert payload.severity is BaseSeverity.WARNING
    assert payload.model_dump(mode="json")["severity"] == "warning"


@pytest.mark.parametrize("severity", ("bogus", ""))
def test_profile_validation_payload_rejects_arbitrary_severity_tokens(severity: str) -> None:
    with pytest.raises(ValidationError):
        ProfileIssuePayload.model_validate(
            {
                "severity": severity,
                "code": "effective_window_end_not_enforced",
                "path": PROFILE_OUTPUT_LANGUAGE_PATH,
                "message": "a later fact should supersede this value",
            },
        )
