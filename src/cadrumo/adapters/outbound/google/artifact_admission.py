"""Fresh admission of known Google creations inside a profile's managed subtree."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Final
from uuid import UUID

from ....application.export.managed_artifact_ports import (
    AdmittedArtifact,
    ArtifactCreationReceipt,
    ArtifactReceiptStore,
    ManagedArtifactKind,
    ManagedArtifactPurpose,
)
from ....application.user_profile.google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationHandoff,
)
from ....core.external_constants import GOOGLE_DRIVE_FOLDER_MIME_TYPE
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.type_guards import is_str_keyed_dict
from ..storage.errors import OutboundStorageConflictError, OutboundStorageNotFoundError
from ._preconditions import google_terminal_refusal
from .api import RequestRetryPolicy, execute_request
from .drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource

PROFILE_MARKER: Final = "cadrumo_profile"
CREATION_MARKER: Final = "cadrumo_creation"
KIND_MARKER: Final = "cadrumo_kind"
ROOT_MARKER: Final = "cadrumo_root"
PUBLICATION_MARKER: Final = "cadrumo_publication"
_MAX_ANCESTORS: Final = 16
_IDENTITY_FIELDS: Final = "id,mimeType,trashed,parents,appProperties"


def creation_properties(
    *,
    profile_id: UUID,
    creation_id: UUID,
    kind: ManagedArtifactKind,
    root_folder_id: str | None = None,
    publication_id: UUID | None = None,
) -> dict[str, str]:
    """Build ownership evidence included in the initial create request."""
    properties = {
        OWNERSHIP_KEY: OWNERSHIP_VALUE,
        PROFILE_MARKER: str(profile_id),
        CREATION_MARKER: str(creation_id),
        KIND_MARKER: kind.value,
    }
    if root_folder_id is not None:
        properties[ROOT_MARKER] = root_folder_id
    if publication_id is not None:
        properties[PUBLICATION_MARKER] = str(publication_id)
    return properties


def artifact_mime_type(kind: ManagedArtifactKind) -> str:
    """Map the closed admitted kind to its provider MIME boundary."""
    if kind in {ManagedArtifactKind.ROOT, ManagedArtifactKind.FOLDER}:
        return GOOGLE_DRIVE_FOLDER_MIME_TYPE
    if kind is ManagedArtifactKind.REVIEW_SHEET:
        return "application/vnd.google-apps.spreadsheet"
    return "application/octet-stream"


class GoogleArtifactAdmission:
    """Check a recorded identity and its bounded, locally known ancestry before use.

    Drive membership is not atomic with a later Sheets request. Every content
    call and retry must invoke admission again, then postcheck publication.
    Root movement does not authorize probing any ancestor outside the root.
    """

    def __init__(
        self,
        drive: DriveResource,
        *,
        profile_id: UUID,
        root: ArtifactCreationReceipt,
        receipts: ArtifactReceiptStore,
        before_handoff: GoogleConfigurationHandoff | None = None,
        acknowledged: GoogleConfigurationAcknowledgement | None = None,
    ) -> None:
        """Bind the active profile, recorded root and exact local receipt custody."""
        self.drive = drive
        self.profile_id = profile_id
        self.root = root
        self.receipts = receipts
        self.before_handoff = before_handoff
        self.acknowledged = acknowledged

    def require(self, artifact_id: str, *, kind: ManagedArtifactKind | None = None) -> ArtifactCreationReceipt:
        """Resolve only local creation evidence; unknown IDs cause no provider call."""
        receipt = self.receipts.load(artifact_id)
        if receipt is None or (kind is not None and receipt.kind is not kind):
            raise _refused("unknown_creation")
        self.admit(receipt, purpose=ManagedArtifactPurpose.ADMISSION)
        return receipt

    def admit(self, receipt: ArtifactCreationReceipt, *, purpose: ManagedArtifactPurpose) -> AdmittedArtifact:
        """Revalidate profile, exact identity, markers, kind, trash and ancestry."""
        if self.root.kind is not ManagedArtifactKind.ROOT or self.root.profile_id != self.profile_id:
            raise _refused("root_profile_mismatch")
        if self.receipts.load(self.root.artifact_id) != self.root:
            raise _refused("root_creation_missing")
        current = receipt
        seen: set[str] = set()
        for _ in range(_MAX_ANCESTORS):
            if (
                current.profile_id != self.profile_id
                or current.root_folder_id != self.root.artifact_id
                or current.artifact_id in seen
                or self.receipts.load(current.artifact_id) != current
            ):
                raise _refused("creation_identity_mismatch")
            seen.add(current.artifact_id)
            self._check_metadata(current)
            if current == self.root:
                return AdmittedArtifact(receipt=receipt, purpose=purpose)
            if current.parent_id is None:
                raise _refused("outside_managed_root")
            parent = self.receipts.load(current.parent_id)
            if parent is None or parent.kind not in {ManagedArtifactKind.ROOT, ManagedArtifactKind.FOLDER}:
                raise _refused("unknown_parent")
            current = parent
        raise _refused("ancestry_bound_exceeded")

    def _check_metadata(self, receipt: ArtifactCreationReceipt) -> None:
        try:
            if self.before_handoff is not None:
                self.before_handoff("drive.files.get.admission")
            entry = execute_request(
                self.drive.files().get(fileId=receipt.artifact_id, fields=_IDENTITY_FIELDS),
                action="drive.files.get.admission",
                retry=RequestRetryPolicy.SINGLE_ATTEMPT,
            )
            if self.acknowledged is not None:
                self.acknowledged("drive.files.get.admission")
        except OutboundStorageNotFoundError:
            raise _refused("identity_unavailable") from None
        validate_creation_metadata(receipt, entry)
        if receipt.kind is ManagedArtifactKind.ROOT:
            placement = self.receipts.root_placement(receipt.artifact_id)
            if placement is not None:
                parent_id, creation_id, my_drive = placement
                if entry.get("parents") != [parent_id]:
                    raise _refused("root_outside_application_parent")
                if self.before_handoff is not None:
                    self.before_handoff("drive.files.get.layout-parent")
                parent = execute_request(
                    self.drive.files().get(fileId=parent_id, fields=_IDENTITY_FIELDS + ",ownedByMe"),
                    action="drive.files.get.layout-parent",
                    retry=RequestRetryPolicy.SINGLE_ATTEMPT,
                )
                if self.acknowledged is not None:
                    self.acknowledged("drive.files.get.layout-parent")
                props = parent.get("appProperties")
                if (
                    parent.get("id") != parent_id
                    or parent.get("ownedByMe") is not True
                    or parent.get("parents") != [my_drive]
                    or parent.get("mimeType") != GOOGLE_DRIVE_FOLDER_MIME_TYPE
                    or parent.get("trashed") is not False
                    or not is_str_keyed_dict(props)
                    or props.get(OWNERSHIP_KEY) != OWNERSHIP_VALUE
                    or props.get(KIND_MARKER) != "application_root"
                    or props.get(CREATION_MARKER) != creation_id
                    or props.get("cadrumo_application_root_id") != parent_id
                ):
                    raise _refused("application_parent_identity_mismatch")


def validate_creation_metadata(receipt: ArtifactCreationReceipt, entry: Mapping[str, object]) -> None:
    """Validate metadata against a locally retained creation intent or receipt."""
    if (
        entry.get("id") != receipt.artifact_id
        or entry.get("mimeType") != artifact_mime_type(receipt.kind)
        or entry.get("trashed") is not False
    ):
        raise _refused("kind_identity_or_trash")
    expected = creation_properties(
        profile_id=receipt.profile_id,
        creation_id=receipt.creation_id,
        kind=receipt.kind,
        root_folder_id=None if receipt.kind is ManagedArtifactKind.ROOT else receipt.root_folder_id,
        publication_id=receipt.publication_id,
    )
    properties = entry.get("appProperties")
    if not is_str_keyed_dict(properties) or any(properties.get(key) != value for key, value in expected.items()):
        raise _refused("ownership_identity_mismatch")
    if receipt.kind is not ManagedArtifactKind.ROOT and entry.get("parents") != [receipt.parent_id]:
        raise _refused("outside_recorded_parent")


def _refused(reason: str) -> OutboundStorageConflictError:
    return managed_artifact_refusal(reason)


def managed_artifact_refusal(reason: str, *, uncertain: bool = False) -> OutboundStorageConflictError:
    """Return bounded provider-identity evidence without remote payload or arbitrary text."""
    error = OutboundStorageConflictError(
        "managed Drive artifact admission refused",
        context={"reason": reason, "effect_uncertain": uncertain},
    )
    return google_terminal_refusal(
        error,
        condition_id="google.managed_artifact.admitted",
        facts={"admitted": False, "reason": reason, "effect_uncertain": uncertain},
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.SAFETY,
    )
