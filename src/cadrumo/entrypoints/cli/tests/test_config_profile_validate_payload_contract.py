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

from ....core import Period
from ....core.config import SecretStoreBackend
from ....domain.user_profile import UserProfileStatus
from .._config_payloads import ConfigLoginResult, ConfigProfilePreflightResult, ConfigProfileValidateResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_INSTANT = datetime(2026, 6, 1, 8, 0, tzinfo=UTC)


def _validate_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "profile_id": "11111111-1111-4111-8111-111111111111",
        "display_name": "MyCo",
        "status": UserProfileStatus.ACTIVE,
        "valid": True,
        "schema_version": 1,
        "issues": [],
    }
    base.update(overrides)
    return base


def test_validate_result_accepts_a_real_projection() -> None:
    """A genuine profile-validation projection validates cleanly."""
    result = ConfigProfileValidateResult.model_validate(_validate_kwargs())

    assert result.status is UserProfileStatus.ACTIVE


def test_validate_result_rejects_a_blank_profile_id() -> None:
    """A blank profile id is refused, matching the canonical ``ProfileId`` constraint."""
    with pytest.raises(ValidationError):
        ConfigProfileValidateResult.model_validate(_validate_kwargs(profile_id=""))


def test_validate_result_rejects_an_unknown_status() -> None:
    """A status outside the closed ``UserProfileStatus`` vocabulary is refused."""
    with pytest.raises(ValidationError):
        ConfigProfileValidateResult.model_validate({**_validate_kwargs(), "status": "bogus"})


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
        "backend_kind": SecretStoreBackend.KEYRING,
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

    assert result.backend_kind is SecretStoreBackend.KEYRING


def test_login_result_rejects_a_blank_active_profile() -> None:
    """A blank ``profile_id`` is refused."""
    with pytest.raises(ValidationError):
        ConfigLoginResult.model_validate(_login_kwargs(profile_id=""))


def test_login_result_rejects_an_unknown_backend_kind() -> None:
    """A backend outside the closed ``SecretStoreBackend`` vocabulary is refused."""
    with pytest.raises(ValidationError):
        ConfigLoginResult.model_validate({**_login_kwargs(), "backend_kind": "bogus"})


def test_login_result_rejects_a_malformed_deadline() -> None:
    """A non-ISO deadline string is refused."""
    with pytest.raises(ValidationError):
        ConfigLoginResult.model_validate({**_login_kwargs(), "idle_deadline": "not-a-time"})


def _preflight_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "profile_id": "11111111-1111-4111-8111-111111111111",
        "modelo": "303",
        "revision_id": "2023-y-siguientes",
        "filing_year": 2026,
        "period": Period.from_year_and_code(2026, "1T"),
        "ready": True,
        "missing": [],
    }
    base.update(overrides)
    return base


def test_preflight_result_accepts_a_real_projection() -> None:
    """A genuine preflight coordinate projects and validates cleanly."""
    result = ConfigProfilePreflightResult.model_validate(_preflight_kwargs())

    assert result.modelo == "303"


def test_preflight_result_rejects_a_blank_profile_id() -> None:
    """A blank profile id is refused."""
    with pytest.raises(ValidationError):
        ConfigProfilePreflightResult.model_validate(_preflight_kwargs(profile_id=""))


def test_preflight_result_rejects_blank_modelo_and_revision() -> None:
    """A blank modelo or revision id is refused."""
    with pytest.raises(ValidationError):
        ConfigProfilePreflightResult.model_validate(_preflight_kwargs(modelo=""))
    with pytest.raises(ValidationError):
        ConfigProfilePreflightResult.model_validate(_preflight_kwargs(revision_id=""))


def test_preflight_result_rejects_an_out_of_range_filing_year() -> None:
    """A filing year of 0 is refused, matching ``ProfilePreflightReport``."""
    with pytest.raises(ValidationError):
        ConfigProfilePreflightResult.model_validate(
            {**_preflight_kwargs(), "filing_year": 0, "period": {"filing_year": 0, "code": "1T"}},
        )


def test_preflight_result_rejects_a_filing_year_period_mismatch() -> None:
    """A filing_year that disagrees with period.filing_year is refused."""
    with pytest.raises(ValidationError):
        ConfigProfilePreflightResult.model_validate(
            _preflight_kwargs(filing_year=2025, period=Period.from_year_and_code(2026, "1T")),
        )
