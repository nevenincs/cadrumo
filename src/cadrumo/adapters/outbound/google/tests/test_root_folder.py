"""Cadrumo creates its own Drive root folder and trusts a stored one only when it carries the marker."""

from __future__ import annotations

import pytest

from .....core.config import Settings
from ...storage.errors import OutboundStorageConflictError
from ..drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE
from ..root_folder import MY_DRIVE, ensure_root_folder, profile_root_folder_name, require_owned_folder
from .drive_files_server import drive_files_endpoint

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PROFILE = "3d2a9c41-7f5e-4b0a-9c1d-5e8f7a6b4c32"
_FOLDER = "application/vnd.google-apps.folder"
_MARKER = {OWNERSHIP_KEY: OWNERSHIP_VALUE}


def _folder(file_id: str, **fields: object) -> dict[str, object]:
    return {
        "id": file_id,
        "name": profile_root_folder_name(_PROFILE),
        "mimeType": _FOLDER,
        "parents": [MY_DRIVE],
        "trashed": False,
        **fields,
    }


def test_the_folder_name_separates_profiles_without_naming_them() -> None:
    assert profile_root_folder_name(_PROFILE) == "Cadrumo 3d2a9c41"
    assert profile_root_folder_name("ffffffff-0000-4000-8000-000000000000") != profile_root_folder_name(_PROFILE)


def test_the_first_sign_in_creates_one_marked_folder_in_my_drive() -> None:
    """The marker is in the creating call, so the folder never exists without it."""
    with drive_files_endpoint() as drive:
        root_folder_id = ensure_root_folder(drive.service, profile=_PROFILE)

        assert drive.calls == ["files.list", "files.create"]
        assert drive.created_bodies == [
            {"name": "Cadrumo 3d2a9c41", "mimeType": _FOLDER, "parents": [MY_DRIVE], "appProperties": _MARKER}
        ]
        assert root_folder_id == "created-1"


def test_signing_in_again_finds_the_folder_instead_of_creating_a_second_one() -> None:
    with drive_files_endpoint(entries=(_folder("existing-root", appProperties=_MARKER),)) as drive:
        assert ensure_root_folder(drive.service, profile=_PROFILE) == "existing-root"
        assert ensure_root_folder(drive.service, profile=_PROFILE) == "existing-root"

        assert drive.calls == ["files.list", "files.list"]
        assert drive.created_bodies == []


def test_another_profiles_folder_is_not_reused() -> None:
    other = _folder("other-root", name="Cadrumo ffffffff", appProperties=_MARKER)
    with drive_files_endpoint(entries=(other,)) as drive:
        assert ensure_root_folder(drive.service, profile=_PROFILE) == "created-1"


@pytest.mark.parametrize(
    "fields",
    ({}, {"appProperties": {}}, {"appProperties": {OWNERSHIP_KEY: "someone-else"}}),
    ids=("no-properties", "empty-properties", "foreign-marker"),
)
def test_a_same_named_folder_without_the_marker_is_refused_and_nothing_is_created(fields: dict[str, object]) -> None:
    with drive_files_endpoint(entries=(_folder("unmarked", **fields),)) as drive:
        with pytest.raises(OutboundStorageConflictError) as refused:
            ensure_root_folder(drive.service, profile=_PROFILE)

        assert drive.created_bodies == []
    verdict = refused.value.terminal_precondition_verdict
    assert verdict is not None and verdict.failed_condition_id == "google.drive_entry.ownership_aligned"


def test_a_stored_root_that_is_a_live_marked_folder_is_accepted() -> None:
    with drive_files_endpoint(entries=(_folder("stored-root", appProperties=_MARKER),)) as drive:
        require_owned_folder(drive.service, root_folder_id="stored-root")

        assert drive.calls == ["files.get"]


@pytest.mark.parametrize(
    ("entry", "facts"),
    (
        pytest.param(
            _folder("stored-root"),
            {"visible_to_application": True, "is_folder": True, "is_live": True, "ownership_marker_present": False},
            id="unmarked",
        ),
        pytest.param(
            _folder("stored-root", appProperties={OWNERSHIP_KEY: "someone-else"}),
            {"visible_to_application": True, "is_folder": True, "is_live": True, "ownership_marker_present": False},
            id="foreign-marker",
        ),
        pytest.param(
            _folder("stored-root", appProperties=_MARKER, trashed=True),
            {"visible_to_application": True, "is_folder": True, "is_live": False, "ownership_marker_present": True},
            id="trashed",
        ),
        pytest.param(
            _folder("stored-root", appProperties=_MARKER, mimeType="application/vnd.google-apps.spreadsheet"),
            {"visible_to_application": True, "is_folder": False, "is_live": True, "ownership_marker_present": True},
            id="not-a-folder",
        ),
    ),
)
def test_a_stored_root_that_is_not_a_live_folder_of_ours_is_refused(
    entry: dict[str, object], facts: dict[str, bool]
) -> None:
    with (
        drive_files_endpoint(entries=(entry,)) as drive,
        pytest.raises(OutboundStorageConflictError) as refused,
    ):
        require_owned_folder(drive.service, root_folder_id="stored-root")

    error = refused.value
    assert error.code.code == "REFUSED_OUTBOUND_STORAGE_CONFLICT"
    assert error.translated_message == "adapters.google.root_folder.errors.root_folder_not_owned"
    assert error.context == {"root_folder_id": "stored-root"}
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "google.root_folder.owned_by_application"
    assert dict(verdict.evidence[0].values) == facts


def test_a_stored_root_drive_does_not_show_is_refused_as_not_ours() -> None:
    """A folder created under another client, or pasted by hand, is invisible under the granted scope.

    It is refused, not reported as an error, so every operation settles it
    as a refusal whose remedy is signing in again.
    """
    with drive_files_endpoint() as drive, pytest.raises(OutboundStorageConflictError) as refused:
        require_owned_folder(drive.service, root_folder_id="a-folder-from-another-client")

    error = refused.value
    assert error.code.code == "REFUSED_OUTBOUND_STORAGE_CONFLICT"
    assert error.code.category.value == "REFUSED"
    assert error.translated_message == "adapters.google.root_folder.errors.root_folder_not_owned"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert dict(verdict.evidence[0].values) == {"visible_to_application": False}


def test_no_setting_supplies_a_drive_folder() -> None:
    assert sorted(name for name in Settings.model_fields if "drive" in name and "root" in name) == []
