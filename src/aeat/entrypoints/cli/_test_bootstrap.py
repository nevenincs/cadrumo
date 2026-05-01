"""Unit tests for the pure helpers in :mod:`aeat.cli.bootstrap`.

The Drive API interactions and the env-file write are exercised by the
live smoke tests in . Here we cover only the dedup decision
logic, which is straightforward to test against a synthetic listing.
"""

from __future__ import annotations

import pytest

from .bootstrap import (
    DOC_MIME,
    FOLDER_MIME,
    SCRATCH_DOC_NAME,
    SCRATCH_FOLDER_NAME,
    SCRATCH_SHEET_NAME,
    SHEET_MIME,
    ScratchResources,
    dedup_existing_resource,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


class TestDedupExistingResource:
    """Behaviour of ``dedup_existing_resource``."""

    def test_returns_id_for_first_match(self) -> None:
        listing = [
            {"id": "abc", "name": "aeat-scratch", "mimeType": FOLDER_MIME},
        ]
        assert dedup_existing_resource("aeat-scratch", FOLDER_MIME, listing) == "abc"

    def test_returns_none_for_no_match(self) -> None:
        listing = [
            {"id": "xyz", "name": "other", "mimeType": FOLDER_MIME},
        ]
        assert dedup_existing_resource("aeat-scratch", FOLDER_MIME, listing) is None

    def test_mime_type_must_match(self) -> None:
        listing = [
            {"id": "xyz", "name": "aeat-scratch", "mimeType": SHEET_MIME},
        ]
        assert dedup_existing_resource("aeat-scratch", FOLDER_MIME, listing) is None

    def test_picks_first_when_multiple(self) -> None:
        listing = [
            {"id": "first", "name": "aeat-scratch", "mimeType": FOLDER_MIME},
            {"id": "second", "name": "aeat-scratch", "mimeType": FOLDER_MIME},
        ]
        assert dedup_existing_resource("aeat-scratch", FOLDER_MIME, listing) == "first"

    def test_handles_empty_listing(self) -> None:
        assert dedup_existing_resource("aeat-scratch", FOLDER_MIME, []) is None

    def test_skips_entries_without_id_and_continues(self) -> None:
        listing = [
            {"name": "aeat-scratch", "mimeType": FOLDER_MIME},
            {"id": "good", "name": "aeat-scratch", "mimeType": FOLDER_MIME},
        ]
        assert dedup_existing_resource("aeat-scratch", FOLDER_MIME, listing) == "good"


class TestScratchConstants:
    """The scratch resource names and MIME types must match the documented contract."""

    def test_folder_mime(self) -> None:
        assert FOLDER_MIME == "application/vnd.google-apps.folder"

    def test_sheet_mime(self) -> None:
        assert SHEET_MIME == "application/vnd.google-apps.spreadsheet"

    def test_doc_mime(self) -> None:
        assert DOC_MIME == "application/vnd.google-apps.document"

    def test_resource_names(self) -> None:
        assert SCRATCH_FOLDER_NAME == "aeat-scratch"
        assert SCRATCH_SHEET_NAME == "aeat-scratch-sheet"
        assert SCRATCH_DOC_NAME == "aeat-scratch-doc"


class TestScratchResources:
    """The ``ScratchResources`` dataclass is frozen and value-equal."""

    def test_equality(self) -> None:
        a = ScratchResources(folder_id="f", sheet_id="s", doc_id="d")
        b = ScratchResources(folder_id="f", sheet_id="s", doc_id="d")
        assert a == b
