"""Strict JSON payload checks for ``aeat config profile view``.

``ConfigProfileViewResult`` used to declare ``profile_id``, ``display_name``,
``status``, and ``schema_version`` as permissive optionals, so a malformed
lifecycle status or a non-positive schema version could be reported as a
valid profile row. It now bounds them at the same widths
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord` enforces, while
keeping the explicit missing/unreadable failure branches (including the
``profile_record_unreadable`` readiness sentinel, which is separate from the
record's ``setup_state``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....domain.user_profile.values import ProfileSetupState
from ..config_payloads import ConfigProfileViewResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = "2af4a976-6a8b-46d0-89e4-c1a6c8462ea2"


def _success_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "profile_id": _PROFILE_ID,
        "display_name": "Operator",
        "setup_state": ProfileSetupState.COMPLETE,
        "valid": True,
        "schema_version": 3,
        "issues": [],
        "facts": [],
    }
    base.update(overrides)
    return base


def test_config_profile_view_result_round_trips_valid_success_row() -> None:
    result = ConfigProfileViewResult.model_validate(_success_kwargs())

    assert result.setup_state is ProfileSetupState.COMPLETE
    assert result.schema_version == 3


def test_config_profile_view_result_round_trips_unreadable_sentinel() -> None:
    """The readiness-branch sentinel is not a lifecycle status, but is accepted."""
    result = ConfigProfileViewResult(
        profile_id=_PROFILE_ID,
        display_name="Operator",
        status="profile_record_unreadable",
        registered_bucket=True,
        profile_record_present=False,
    )

    assert result.status == "profile_record_unreadable"


def test_config_profile_view_result_round_trips_missing_record_branch() -> None:
    """The missing-record branch carries no status at all."""
    result = ConfigProfileViewResult(
        profile_id=_PROFILE_ID,
        display_name="Operator",
        registered_bucket=True,
        profile_record_present=False,
        readiness="missing_profile_record",
    )

    assert result.status is None
    assert result.readiness == "missing_profile_record"


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("profile_id", ""),
        ("display_name", ""),
        ("setup_state", "bogus"),
        ("schema_version", 0),
    ),
)
def test_config_profile_view_result_refuses_malformed_field(field: str, bad_value: object) -> None:
    """A blank identity, unknown status, or non-positive schema version is refused."""
    with pytest.raises(ValidationError):
        ConfigProfileViewResult.model_validate(_success_kwargs(**{field: bad_value}))
