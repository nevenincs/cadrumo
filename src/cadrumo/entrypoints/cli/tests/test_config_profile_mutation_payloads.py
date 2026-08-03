"""Strict JSON payload checks for the config profile delete/duplicate/rename envelopes.

``ConfigProfileDeleteResult``, ``ConfigProfileDuplicateResult``, and
``ConfigProfileRenameResult`` used to redeclare identity, status, and label
fields as plain strings, so an empty identity or an unknown lifecycle status
crossed the envelope. They now project the same bounds
:class:`~cadrumo.application.user_profile.ProfileLifecycleResult` and
:class:`~cadrumo.application.bucket_maintenance.RenameBucketResult` enforce.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....domain.user_profile import UserProfileStatus
from .._config_payloads import (
    ConfigProfileDeleteResult,
    ConfigProfileDuplicateResult,
    ConfigProfileRenameResult,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _delete_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "profile_id": "profile-1",
        "display_name": "Operator",
        "status": UserProfileStatus.TOMBSTONED,
        "active_profile_cleared": True,
    }
    base.update(overrides)
    return base


def test_config_profile_delete_result_round_trips_valid_row() -> None:
    result = ConfigProfileDeleteResult.model_validate(_delete_kwargs())

    assert result.status is UserProfileStatus.TOMBSTONED


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("profile_id", ""),
        ("display_name", ""),
        ("status", "bogus"),
    ),
)
def test_config_profile_delete_result_refuses_malformed_field(field: str, bad_value: object) -> None:
    with pytest.raises(ValidationError):
        ConfigProfileDeleteResult.model_validate(_delete_kwargs(**{field: bad_value}))


def _duplicate_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "source_profile_id": "source-1",
        "target_profile_id": "target-1",
        "display_name": "Copy",
    }
    base.update(overrides)
    return base


def test_config_profile_duplicate_result_round_trips_valid_row() -> None:
    result = ConfigProfileDuplicateResult.model_validate(_duplicate_kwargs())

    assert result.display_name == "Copy"


@pytest.mark.parametrize("field", ("source_profile_id", "target_profile_id", "display_name"))
def test_config_profile_duplicate_result_refuses_blank_field(field: str) -> None:
    with pytest.raises(ValidationError):
        ConfigProfileDuplicateResult.model_validate(_duplicate_kwargs(**{field: ""}))


def _rename_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "profile_id": "profile-1",
        "previous_display_name": "old",
        "display_name": "new",
    }
    base.update(overrides)
    return base


def test_config_profile_rename_result_round_trips_valid_row() -> None:
    result = ConfigProfileRenameResult.model_validate(_rename_kwargs())

    assert result.display_name == "new"


@pytest.mark.parametrize("field", ("profile_id", "previous_display_name", "display_name"))
def test_config_profile_rename_result_refuses_blank_field(field: str) -> None:
    with pytest.raises(ValidationError):
        ConfigProfileRenameResult.model_validate(_rename_kwargs(**{field: ""}))
