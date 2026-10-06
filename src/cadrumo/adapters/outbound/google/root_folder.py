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

from enum import StrEnum
from typing import TYPE_CHECKING, Final
from uuid import UUID

from ....application.export.managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ....application.user_profile.google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationCommit,
    GoogleConfigurationHandoff,
)
from ....core.external_constants import GOOGLE_DRIVE_FOLDER_MIME_TYPE
from ....core.product_identity import PRODUCT_IDENTITY
from ...persistence.storage.runtime_repository import secure_object_repository_for_active_bucket
from ..storage.errors import OutboundStorageConflictError, OutboundStorageValidationError
from .api import RequestRetryPolicy, drive_v3_service, execute_request
from .artifact_admission import GoogleArtifactAdmission, creation_properties
from .artifact_receipt_store import GoogleArtifactReceiptStore

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


def ensure_profile_root_folder(
    credentials: Credentials,
    *,
    profile: str,
    commit: GoogleConfigurationCommit,
    before_handoff: GoogleConfigurationHandoff,
    acknowledged: GoogleConfigurationAcknowledgement,
) -> str:
    """Reuse an exact retained creation receipt or create without listing My Drive."""
    drive = drive_v3_service(
        credentials, unavailable_condition_id=RootFolderPreconditionCondition.API_CLIENT_AVAILABLE.value
    )
    receipts = GoogleArtifactReceiptStore(
        secure_object_repository_for_active_bucket(), profile_id=UUID(profile), commit=commit
    )
    return ensure_root_folder(
        drive, profile=profile, receipts=receipts, before_handoff=before_handoff, acknowledged=acknowledged
    )


def ensure_root_folder(
    drive: DriveResource,
    *,
    profile: str,
    receipts: GoogleArtifactReceiptStore,
    before_handoff: GoogleConfigurationHandoff | None = None,
    acknowledged: GoogleConfigurationAcknowledgement | None = None,
) -> str:
    """Create a marked root once; ambiguous attempts require explicit reconciliation."""
    profile_id = UUID(profile)
    prior = receipts.root_attempt()
    if prior is not None:
        if prior.receipt is None:
            raise OutboundStorageConflictError(
                "a prior root creation has an unknown outcome; automatic retry is refused",
                context={"effect_uncertain": True},
            )
        GoogleArtifactAdmission(
            drive,
            profile_id=profile_id,
            root=prior.receipt,
            receipts=receipts,
            before_handoff=before_handoff,
            acknowledged=acknowledged,
        ).require(prior.receipt.artifact_id, kind=ManagedArtifactKind.ROOT)
        return prior.receipt.artifact_id
    attempt = receipts.begin_root_creation()
    if before_handoff is not None:
        before_handoff("drive.files.create.root", writes=True)
    created = execute_request(
        drive.files().create(
            body={
                "name": profile_root_folder_name(profile),
                "mimeType": GOOGLE_DRIVE_FOLDER_MIME_TYPE,
                "parents": [MY_DRIVE],
                "appProperties": creation_properties(
                    profile_id=profile_id, creation_id=attempt.creation_id, kind=ManagedArtifactKind.ROOT
                ),
            },
            fields="id",
        ),
        action="drive.files.create.root",
        retry=RequestRetryPolicy.SINGLE_ATTEMPT,
    )
    identifier = created.get("id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise OutboundStorageValidationError(
            "root creation returned no usable identity", context={"effect_uncertain": True}
        )
    receipt = ArtifactCreationReceipt(
        profile_id=profile_id,
        root_folder_id=identifier,
        artifact_id=identifier,
        creation_id=attempt.creation_id,
        kind=ManagedArtifactKind.ROOT,
    )
    receipts.complete_root_creation(receipt)
    if acknowledged is not None:
        acknowledged("drive.files.create.root", writes=True)
    GoogleArtifactAdmission(
        drive,
        profile_id=profile_id,
        root=receipt,
        receipts=receipts,
        before_handoff=before_handoff,
        acknowledged=acknowledged,
    ).require(identifier, kind=ManagedArtifactKind.ROOT)
    return identifier


def require_owned_root_folder(credentials: Credentials, *, root_folder_id: str, profile: str) -> None:
    """Refuse a stored root folder ID that is not a live folder this application created.

    Args:
        credentials: Credentials of the signed-in account.
        root_folder_id: The ID stored for the profile.
        profile: Exact active profile whose creation receipt is required.

    Raises:
        :exc:`~adapters.outbound.storage.errors.OutboundStorageConflictError`:
            When Drive does not show the folder to this application, or the
            entry is trashed, is not a folder, or lacks the marker. A folder
            created under another client is invisible here, and the remedy
            is the same in every case: sign in again.
    """
    drive = drive_v3_service(
        credentials, unavailable_condition_id=RootFolderPreconditionCondition.API_CLIENT_AVAILABLE.value
    )
    receipts = GoogleArtifactReceiptStore(secure_object_repository_for_active_bucket(), profile_id=UUID(profile))
    require_owned_folder(drive, root_folder_id=root_folder_id, profile=profile, receipts=receipts)


def require_owned_folder(
    drive: DriveResource, *, root_folder_id: str, profile: str, receipts: GoogleArtifactReceiptStore
) -> None:
    """Admit the exact locally retained profile root before any descendant access."""
    root = receipts.load(root_folder_id)
    if root is None:
        raise OutboundStorageConflictError("stored root lacks local creation evidence; sign in to create a fresh root")
    GoogleArtifactAdmission(drive, profile_id=UUID(profile), root=root, receipts=receipts).require(
        root_folder_id, kind=ManagedArtifactKind.ROOT
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
