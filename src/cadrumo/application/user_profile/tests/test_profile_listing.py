"""The join a profile listing makes between its summaries and the selected profile."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from cadrumo.application.user_profile.profile_summary import ProfileListing, ProfileSummary, ProfileSummaryInventory
from cadrumo.core.profile_publication import ProfilePublicationKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _profile(number: int) -> str:
    return f"0000000{number}-0000-4000-8000-00000000000{number}"


def _summary(number: int, label: str) -> ProfileSummary:
    return ProfileSummary(
        profile_id=_profile(number),
        label=label,
        label_revision=1,
        published_at=datetime(2026, 3, 4, tzinfo=UTC),
        publication_kind=ProfilePublicationKind.ENROLL,
    )


def test_rows_read_alphabetically_and_only_the_selected_profile_is_active() -> None:
    inventory = ProfileSummaryInventory(summaries=(_summary(3, "zeta"), _summary(2, "Alba"), _summary(1, "alba")))

    result = ProfileListing(inventory=inventory, active_profile_id=_profile(3)).result()

    assert [(row.name, row.bucket_id, row.active) for row in result.profiles] == [
        ("alba", _profile(1), False),
        ("Alba", _profile(2), False),
        ("zeta", _profile(3), True),
    ]
    assert result.active_profile == "zeta"


def test_a_selection_that_names_no_listed_profile_leaves_every_row_inactive() -> None:
    inventory = ProfileSummaryInventory(summaries=(_summary(1, "solo"),))

    for selected in (None, _profile(9)):
        result = ProfileListing(inventory=inventory, active_profile_id=selected).result()

        assert result.active_profile is None
        assert [row.active for row in result.profiles] == [False]
