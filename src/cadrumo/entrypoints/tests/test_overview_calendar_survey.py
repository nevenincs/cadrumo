"""Locked calendar rows retain other profiles without exposing the active row."""

from __future__ import annotations

from uuid import UUID

import pytest

from ...application.workflow.profile_bucket_models import ProfileBucketPointer
from ..overview_read_composition import _calendar_other_profiles

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("include_active", [False, True])
def test_calendar_locked_profiles_exclude_active_and_keep_label_order(include_active: bool) -> None:
    active = str(UUID(int=1))
    alpha = str(UUID(int=2))
    zulu = str(UUID(int=3))
    pointers = {
        zulu: ProfileBucketPointer(bucket_id=zulu, label="Zulu"),
        alpha: ProfileBucketPointer(bucket_id=alpha, label="Alpha"),
    }
    if include_active:
        pointers[active] = ProfileBucketPointer(bucket_id=active, label="Active")

    rows = _calendar_other_profiles(active, pointers)

    assert tuple((row.profile_id, row.label) for row in rows) == ((alpha, "Alpha"), (zulu, "Zulu"))


def test_calendar_locked_profiles_keep_source_order_for_equal_labels() -> None:
    active = str(UUID(int=1))
    first = str(UUID(int=3))
    second = str(UUID(int=2))
    pointers = {
        first: ProfileBucketPointer(bucket_id=first, label="Shared label"),
        active: ProfileBucketPointer(bucket_id=active, label="Shared label"),
        second: ProfileBucketPointer(bucket_id=second, label="Shared label"),
    }

    assert tuple(row.profile_id for row in _calendar_other_profiles(active, pointers)) == (first, second)


def test_calendar_locked_profiles_accept_no_other_profiles() -> None:
    active = str(UUID(int=1))
    assert _calendar_other_profiles(active, {}) == ()
    assert _calendar_other_profiles(active, {active: ProfileBucketPointer(bucket_id=active, label="Active")}) == ()
