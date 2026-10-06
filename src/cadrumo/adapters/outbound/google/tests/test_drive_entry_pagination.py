"""Scoped identity lookup must exhaust pages before accepting a unique entry."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs

import pytest

from ...storage.errors import OutboundStorageConflictError, OutboundStorageNetworkError
from ..drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE, find_owned_drive_entry
from .drive_list_server import drive_files_list_endpoint

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource
    from googleapiclient._apis.drive.v3.schemas import File

pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter]


def _owned(identifier: str) -> dict[str, object]:
    return {"id": identifier, "name": "target", "appProperties": {OWNERSHIP_KEY: OWNERSHIP_VALUE}}


def _lookup(service: object) -> File | None:
    return find_owned_drive_entry(
        cast("DriveResource", service),
        parent_id="managed-parent",
        name="target",
        mime_type="application/vnd.google-apps.folder",
        list_action="drive.files.list.folder",
        conflict_message="folder identity is ambiguous or foreign",
    )


def test_scoped_lookup_follows_empty_page_before_accepting_identity() -> None:
    with drive_files_list_endpoint(
        pages=[{"files": [], "nextPageToken": "second"}, {"files": [_owned("one")]}]
    ) as endpoint:
        found = _lookup(endpoint.service)
        assert found is not None
        assert found["id"] == "one"
        assert len(endpoint.requested_queries) == 2
        assert parse_qs(endpoint.requested_queries[1])["pageToken"] == ["second"]
        for query in endpoint.requested_queries:
            assert "'managed-parent' in parents" in parse_qs(query)["q"][0]
            assert "nextPageToken" in parse_qs(query)["fields"][0]


@pytest.mark.parametrize("later", [_owned("two"), {"id": "foreign", "name": "target"}])
def test_scoped_lookup_refuses_later_page_ambiguity(later: dict[str, object]) -> None:
    with (
        drive_files_list_endpoint(
            pages=[{"files": [_owned("one")], "nextPageToken": "second"}, {"files": [later]}],
        ) as endpoint,
        pytest.raises(OutboundStorageConflictError),
    ):
        _lookup(endpoint.service)


def test_scoped_lookup_refuses_duplicate_identities_in_one_page() -> None:
    with (
        drive_files_list_endpoint(pages=[{"files": [_owned("one"), _owned("two")]}]) as endpoint,
        pytest.raises(OutboundStorageConflictError),
    ):
        _lookup(endpoint.service)


def test_scoped_lookup_refuses_pagination_cycle() -> None:
    with drive_files_list_endpoint(
        pages=[{"files": [], "nextPageToken": "same"}, {"files": [], "nextPageToken": "same"}],
    ) as endpoint:
        with pytest.raises(OutboundStorageNetworkError):
            _lookup(endpoint.service)
        assert len(endpoint.requested_queries) == 2
