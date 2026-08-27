"""Strict JSON payload checks for the config profile list/sandbox pointer rows.

``ProfilePointerPayload`` and ``ConfigListResult`` used to accept plain,
unbounded ``str`` for identity/status/active-label fields. They now project
:class:`~cadrumo.application.workflow.ProfileBucketPointer`'s bounds directly
(a bounded non-blank label, a bounded non-blank bucket id, and the real
profile pointer identity and label), so a malformed row is refused rather than
listed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .._profile_list_payloads import ConfigListResult, ProfilePointerPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _pointer_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "name": "alice",
        "bucket_id": "b" * 32,
        "active": True,
    }
    base.update(overrides)
    return base


def test_profile_pointer_payload_round_trips_valid_row() -> None:
    """A valid pointer row carries bounded identity and label fields."""
    row = ProfilePointerPayload.model_validate(_pointer_kwargs())

    assert row.bucket_id == "b" * 32


def test_profile_pointer_payload_refuses_blank_name() -> None:
    with pytest.raises(ValidationError):
        ProfilePointerPayload.model_validate(_pointer_kwargs(name=""))


def test_profile_pointer_payload_refuses_blank_bucket_id() -> None:
    with pytest.raises(ValidationError):
        ProfilePointerPayload.model_validate(_pointer_kwargs(bucket_id=""))


def test_profile_pointer_payload_refuses_legacy_status_field() -> None:
    """The unauthenticated pointer projection has no lifecycle field."""
    with pytest.raises(ValidationError):
        ProfilePointerPayload.model_validate(_pointer_kwargs(status="active"))


def test_config_list_result_accepts_no_active_profile() -> None:
    result = ConfigListResult(active_profile=None, profiles=[])

    assert result.active_profile is None
    assert result.profiles == []


def test_config_list_result_refuses_empty_active_profile_label() -> None:
    """An empty-but-present active-profile label is refused, not listed as active."""
    with pytest.raises(ValidationError):
        ConfigListResult(active_profile="", profiles=[])


def test_config_list_result_round_trips_valid_row() -> None:
    result = ConfigListResult(
        active_profile="alice",
        profiles=[ProfilePointerPayload.model_validate(_pointer_kwargs())],
    )

    assert result.active_profile == "alice"
    assert result.profiles[0].name == "alice"
