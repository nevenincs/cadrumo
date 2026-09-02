"""Contract parity between profile validation/login application results and their CLI shells.

``ConfigProfileValidateResult`` and ``ConfigLoginResult`` must refuse the
malformed identity, status, backend, timestamp, and schema-version shapes
the canonical ``ProfileValidationReport`` / ``ProfileLoginOutcome`` models
already refuse. Distinct from the existing issue-severity finding, which
covers the nested ``ProfileIssuePayload`` row shape only.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....domain.user_profile.values import ProfileSetupState
from ..config_payloads import ConfigLoginResult, ConfigProfileValidateResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_INSTANT = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)


def _validate_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "profile_id": "11111111-1111-4111-8111-111111111111",
        "display_name": "MyCo",
        "setup_state": ProfileSetupState.COMPLETE,
        "valid": True,
        "schema_version": 1,
        "issues": [],
    }
    base.update(overrides)
    return base


def test_validate_result_accepts_a_real_projection() -> None:
    """A genuine profile-validation projection validates cleanly."""
    result = ConfigProfileValidateResult.model_validate(_validate_kwargs())

    assert result.setup_state is ProfileSetupState.COMPLETE


def test_validate_result_rejects_a_blank_profile_id() -> None:
    """A blank profile id is refused, matching the canonical ``ProfileId`` constraint."""
    with pytest.raises(ValidationError):
        ConfigProfileValidateResult.model_validate(_validate_kwargs(profile_id=""))


def test_validate_result_rejects_an_unknown_setup_state() -> None:
    """A setup state outside the closed vocabulary is refused."""
    with pytest.raises(ValidationError):
        ConfigProfileValidateResult.model_validate({**_validate_kwargs(), "setup_state": "bogus"})


def test_validate_result_rejects_a_non_positive_schema_version() -> None:
    """A schema version below 1 is refused, matching ``ProfileValidationReport``."""
    with pytest.raises(ValidationError):
        ConfigProfileValidateResult.model_validate(_validate_kwargs(schema_version=0))


def test_validate_result_rejects_a_blank_display_name() -> None:
    """A blank display name is refused."""
    with pytest.raises(ValidationError):
        ConfigProfileValidateResult.model_validate(_validate_kwargs(display_name=""))


def _login_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "profile_id": "bucket-1",
        "active_profile": "myco",
        "authenticated_at": _INSTANT,
        "idle_deadline": _INSTANT,
        "absolute_deadline": _INSTANT,
        "session_persisted": True,
        "already_authenticated": False,
    }
    base.update(overrides)
    return base


def test_login_result_accepts_a_real_projection() -> None:
    """A genuine login outcome projects and validates cleanly."""
    result = ConfigLoginResult.model_validate(_login_kwargs())

    assert result.session_persisted is True


def test_login_result_rejects_a_blank_active_profile() -> None:
    """A blank ``profile_id`` is refused."""
    with pytest.raises(ValidationError):
        ConfigLoginResult.model_validate(_login_kwargs(profile_id=""))


def test_login_result_refuses_retired_backend_metadata() -> None:
    """Normal password custody does not project a retired provider backend."""
    with pytest.raises(ValidationError):
        ConfigLoginResult.model_validate({**_login_kwargs(), "backend_kind": "bogus"})


def test_login_result_rejects_a_malformed_deadline() -> None:
    """A non-ISO deadline string is refused."""
    with pytest.raises(ValidationError):
        ConfigLoginResult.model_validate({**_login_kwargs(), "idle_deadline": "not-a-time"})
