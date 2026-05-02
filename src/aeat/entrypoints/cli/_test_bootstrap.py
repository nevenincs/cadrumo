"""Unit tests for the pure helpers in :mod:`aeat.entrypoints.cli.bootstrap`.

The Drive API interactions and the env-file write are exercised by the
live smoke tests in the ``_test_*_live`` modules. Here we cover only
the dedup decision logic, which is straightforward to test against a
synthetic listing.
"""

from __future__ import annotations

import pytest

from .bootstrap import (
    FOLDER_MIME,
    SHEET_MIME,
    ScratchResources,
    dedup_existing_resource,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


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


class TestScratchResources:
    """The ``ScratchResources`` dataclass is frozen and value-equal."""

    def test_equality(self) -> None:
        a = ScratchResources(folder_id="f", sheet_id="s", doc_id="d")
        b = ScratchResources(folder_id="f", sheet_id="s", doc_id="d")
        assert a == b
