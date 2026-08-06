"""Strict JSON payload checks for ``aeat config profile show``.

``ConfigProfileShowResult`` used to declare ``profile_id``, ``display_name``,
``status``, and ``schema_version`` as permissive optionals, so a malformed
lifecycle status or a non-positive schema version could be reported as a
valid profile row. It now bounds them at the same widths
:class:`~cadrumo.domain.user_profile.UserProfileRecord` enforces, while
keeping the explicit missing/unreadable failure branches (including the
``profile_record_unreadable`` readiness sentinel, which is not itself a
:class:`~cadrumo.domain.user_profile.UserProfileStatus` lifecycle state).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....domain.user_profile import UserProfileStatus
from .._config_payloads import ConfigProfileShowResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _success_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "profile_id": "operator",
        "display_name": "Operator",
        "status": UserProfileStatus.ACTIVE,
        "valid": True,
        "schema_version": 3,
        "issues": [],
        "facts": [],
    }
    base.update(overrides)
    return base


def test_config_profile_show_result_round_trips_valid_success_row() -> None:
    result = ConfigProfileShowResult.model_validate(_success_kwargs())

    assert result.status is UserProfileStatus.ACTIVE
    assert result.schema_version == 3


def test_config_profile_show_result_round_trips_unreadable_sentinel() -> None:
    """The readiness-branch sentinel is not a lifecycle status, but is accepted."""
    result = ConfigProfileShowResult(
        profile_id="operator",
        display_name="Operator",
        status="profile_record_unreadable",
        registered_bucket=True,
        profile_record_present=False,
    )

    assert result.status == "profile_record_unreadable"


def test_config_profile_show_result_round_trips_missing_record_branch() -> None:
    """The missing-record branch carries no status at all."""
    result = ConfigProfileShowResult(
        profile_id="operator",
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
        ("status", "bogus"),
        ("schema_version", 0),
    ),
)
def test_config_profile_show_result_refuses_malformed_field(field: str, bad_value: object) -> None:
    """A blank identity, unknown status, or non-positive schema version is refused."""
    with pytest.raises(ValidationError):
        ConfigProfileShowResult.model_validate(_success_kwargs(**{field: bad_value}))
