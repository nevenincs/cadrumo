"""The Drive folder Cadrumo creates for a profile and keeps everything under.

Cadrumo never works inside a folder the user points it at. Signing in creates
one folder in the user's My Drive, stamped with the application's ownership
marker in the creating call, and its ID is stored for the profile. Every
workbook and every mirrored object lives beneath it.

A stored ID is not trusted on its own. Before it is used as a parent it is read
back from Drive and must still be a live folder carrying the marker, so an ID
that reached the profile store any other way is refused rather than written
under.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from ....core.external_constants import GOOGLE_DRIVE_FOLDER_MIME_TYPE
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.product_identity import PRODUCT_IDENTITY
from ....core.type_guards import is_str_keyed_dict
from ..storage.errors import OutboundStorageConflictError
from ._preconditions import google_terminal_refusal
from .api import RequestRetryPolicy, drive_v3_service, execute_request
from .drive_entries import is_app_owned

if TYPE_CHECKING:
    from google.auth.credentials import Credentials
    from googleapiclient._apis.drive.v3.resources import DriveResource

MY_DRIVE: Final[str] = "root"
"""Drive's own alias for the top of the signed-in user's My Drive."""

_PROFILE_DISCRIMINATOR_LENGTH: Final[int] = 8


class RootFolderPreconditionCondition(StrEnum):
    """Closed terminal conditions owned by the profile root folder."""

    API_CLIENT_AVAILABLE = "google.root_folder.api_client_available"
    OWNED_BY_APPLICATION = "google.root_folder.owned_by_application"


def profile_root_folder_name(profile: str) -> str:
    """Return the name of the folder created for ``profile``.

    The start of the profile ID keeps two profiles signed in to one Google
    account apart without putting the profile's label in the user's Drive.
    """
    return f"{PRODUCT_IDENTITY.prose_name} {profile[:_PROFILE_DISCRIMINATOR_LENGTH]}"


def ensure_profile_root_folder(credentials: Credentials, *, profile: str) -> str:
    """Return the ID of the profile's root folder, creating it when absent.

    The folder is looked up by name among the entries this application can
    see in My Drive, so signing in again finds the folder an earlier sign-in
    created instead of making a second one. A same-named entry without the
    ownership marker is refused, never adopted.

    Args:
        credentials: Credentials of the account that just signed in.
        profile: Profile the folder belongs to.

    Returns:
        The Drive ID of the marker-stamped root folder.
    """
    drive = drive_v3_service(
        credentials, unavailable_condition_id=RootFolderPreconditionCondition.API_CLIENT_AVAILABLE.value
    )
    return ensure_root_folder(drive, profile=profile)


def ensure_root_folder(drive: DriveResource, *, profile: str) -> str:
    """Find or create the profile's root folder through an already built Drive service."""
    from .calc_sheets_apply import _ensure_folder

    return _ensure_folder(drive, parent_id=MY_DRIVE, name=profile_root_folder_name(profile))


def require_owned_root_folder(credentials: Credentials, *, root_folder_id: str) -> None:
    """Refuse a stored root folder ID that is not a live folder this application created.

    Args:
        credentials: Credentials of the signed-in account.
        root_folder_id: The ID stored for the profile.

    Raises:
        :exc:`~adapters.outbound.storage.errors.OutboundStorageNotFoundError`:
            When Drive does not show the folder to this application.
        :exc:`~adapters.outbound.storage.errors.OutboundStorageConflictError`:
            When the entry is trashed, is not a folder, or lacks the marker.
    """
    drive = drive_v3_service(
        credentials, unavailable_condition_id=RootFolderPreconditionCondition.API_CLIENT_AVAILABLE.value
    )
    require_owned_folder(drive, root_folder_id=root_folder_id)


def require_owned_folder(drive: DriveResource, *, root_folder_id: str) -> None:
    """Apply :func:`require_owned_root_folder` through an already built Drive service."""
    entry = execute_request(
        drive.files().get(fileId=root_folder_id, fields="id,mimeType,trashed,appProperties"),
        action="drive.files.get.root_folder",
        retry=RequestRetryPolicy.REPLAY_SAFE,
    )
    raw_properties = entry.get("appProperties")
    properties: Mapping[str, object] = raw_properties if is_str_keyed_dict(raw_properties) else {}
    is_folder = entry.get("mimeType") == GOOGLE_DRIVE_FOLDER_MIME_TYPE
    is_live = entry.get("trashed") is not True
    owned = is_app_owned(properties)
    if is_folder and is_live and owned:
        return
    raise google_terminal_refusal(
        OutboundStorageConflictError(
            "the stored Drive root is not a live folder created by this application",
            context={"root_folder_id": root_folder_id},
            translated_message="adapters.google.root_folder.errors.root_folder_not_owned",
        ),
        condition_id=RootFolderPreconditionCondition.OWNED_BY_APPLICATION.value,
        facts={"is_folder": is_folder, "is_live": is_live, "ownership_marker_present": owned},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


__all__ = [
    "MY_DRIVE",
    "RootFolderPreconditionCondition",
    "ensure_profile_root_folder",
    "ensure_root_folder",
    "profile_root_folder_name",
    "require_owned_folder",
    "require_owned_root_folder",
]
