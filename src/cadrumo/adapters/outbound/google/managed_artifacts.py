"""Receipt-bound Google transport; every request rechecks current containment."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING
from uuid import UUID

from ....application.export.managed_artifact_ports import (
    AdmittedArtifact,
    ArtifactCreationReceipt,
    ManagedArtifactKind,
    ManagedArtifactPurpose,
)
from ....core.google_drive_query import escape_google_drive_query_literal
from ....core.hashing import sha256_hex
from ....core.hex import Hex64Str
from ..storage.drive_pagination import next_drive_page_token
from ..storage.errors import OutboundStorageConflictError, OutboundStorageIntegrityError
from .api import RequestRetryPolicy, execute_request
from .artifact_admission import (
    CREATION_MARKER,
    GoogleArtifactAdmission,
    artifact_mime_type,
    creation_properties,
    managed_artifact_refusal,
    validate_creation_metadata,
)
from .artifact_receipt_store import GoogleArtifactReceiptStore

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import File


_BINARY_KINDS = frozenset(
    {
        ManagedArtifactKind.CIPHERTEXT,
        ManagedArtifactKind.MIRROR_MANIFEST,
        ManagedArtifactKind.EVIDENCE_PACKAGE,
        ManagedArtifactKind.PROBE,
    }
)


class ManagedGoogleArtifacts:
    """Direct creation, scoped inventory and single-publication binary transport.

    Google cannot bind a content call atomically to its current Drive ancestry.
    The adapter checks immediately before each call and after publication; it
    does not claim to eliminate a user move between those requests.
    """

    def __init__(self, admission: GoogleArtifactAdmission, *, receipts: GoogleArtifactReceiptStore) -> None:
        """Bind the same exact-profile receipt custody used by admission."""
        if admission.receipts is not receipts:
            raise ValueError("admission and transport must share receipt custody")
        self.admission = admission
        self.receipts = receipts

    def admit(self, receipt: ArtifactCreationReceipt, *, purpose: ManagedArtifactPurpose) -> AdmittedArtifact:
        """Require fresh profile, identity, marker, kind, trash and ancestry evidence."""
        return self.admission.admit(receipt, purpose=purpose)

    def _handoff(self, artifact: AdmittedArtifact, action: str, *, writes: bool = False) -> None:
        self.admit(artifact.receipt, purpose=artifact.purpose)
        if self.admission.before_handoff is not None:
            self.admission.before_handoff(action, writes=writes)

    def _acknowledge(self, action: str, *, writes: bool = False) -> None:
        if self.admission.acknowledged is not None:
            self.admission.acknowledged(action, writes=writes)

    def create(
        self, parent: AdmittedArtifact, *, name: str, kind: ManagedArtifactKind, publication_id: UUID
    ) -> ArtifactCreationReceipt:
        """Create once with the parent and all ownership evidence in the initial body."""
        if (
            parent.receipt.kind not in {ManagedArtifactKind.ROOT, ManagedArtifactKind.FOLDER}
            or parent.purpose is not ManagedArtifactPurpose.PUBLICATION
            or kind is ManagedArtifactKind.ROOT
            or not name.strip()
        ):
            raise OutboundStorageConflictError("invalid managed artifact creation capability")
        self.admit(parent.receipt, purpose=parent.purpose)
        attempt = self.receipts.begin_creation(
            parent=parent.receipt, name=name, kind=kind, publication_id=publication_id
        )
        body: File = {
            "name": name,
            "mimeType": artifact_mime_type(kind),
            "parents": [parent.receipt.artifact_id],
            "appProperties": creation_properties(
                profile_id=parent.receipt.profile_id,
                creation_id=attempt.creation_id,
                kind=kind,
                root_folder_id=parent.receipt.root_folder_id,
                publication_id=publication_id,
            ),
        }
        self._handoff(parent, "drive.files.create.managed", writes=True)
        created = execute_request(
            self.admission.drive.files().create(body=body, fields="id"),
            action="drive.files.create.managed",
            retry=RequestRetryPolicy.SINGLE_ATTEMPT,
        )
        identifier = created.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise OutboundStorageConflictError(
                "managed creation identity is unknown", context={"effect_uncertain": True}
            )
        receipt = ArtifactCreationReceipt(
            profile_id=parent.receipt.profile_id,
            root_folder_id=parent.receipt.root_folder_id,
            artifact_id=identifier,
            parent_id=parent.receipt.artifact_id,
            creation_id=attempt.creation_id,
            kind=kind,
            publication_id=publication_id,
        )
        self.receipts.complete_creation(attempt, receipt)
        self._acknowledge("drive.files.create.managed", writes=True)
        self.admit(receipt, purpose=ManagedArtifactPurpose.PUBLICATION)
        return receipt

    def list_children(self, parent: AdmittedArtifact) -> tuple[ArtifactCreationReceipt, ...]:
        """Fully paginate inside an admitted folder and refuse unknown copied identities."""
        if parent.receipt.kind not in {ManagedArtifactKind.ROOT, ManagedArtifactKind.FOLDER}:
            raise OutboundStorageConflictError("inventory requires an admitted folder")
        parent_id = escape_google_drive_query_literal(parent.receipt.artifact_id)
        page_token = None
        seen_tokens: set[str] = set()
        found: dict[str, ArtifactCreationReceipt] = {}
        while True:
            self._handoff(parent, "drive.files.list.managed")
            page = execute_request(
                self.admission.drive.files().list(
                    q=f"'{parent_id}' in parents and trashed = false",
                    fields="files(id),nextPageToken",
                    pageSize=100,
                    pageToken=page_token,
                ),
                action="drive.files.list.managed",
                retry=RequestRetryPolicy.SINGLE_ATTEMPT,
            )
            self._acknowledge("drive.files.list.managed")
            for entry in page.get("files", []):
                identifier = entry.get("id", "")
                receipt = self.admission.require(identifier)
                if receipt.parent_id != parent.receipt.artifact_id or identifier in found:
                    raise OutboundStorageConflictError("ambiguous managed child inventory")
                found[identifier] = receipt
            page_token = next_drive_page_token(
                page.get("nextPageToken"), seen_tokens=seen_tokens, action="drive.files.list.managed"
            )
            if page_token is None:
                return tuple(found.values())

    def reconcile_creation(
        self, parent: AdmittedArtifact, *, name: str, kind: ManagedArtifactKind, publication_id: UUID
    ) -> ArtifactCreationReceipt:
        """Recover one unknown child-create response within its recorded parent.

        This establishes identity only. It never retries creation or population,
        promotes publication, reads content, or searches outside the managed root.
        Missing or duplicate candidates remain uncertain.
        """
        if parent.purpose is not ManagedArtifactPurpose.RECONCILIATION:
            raise managed_artifact_refusal("reconciliation_purpose_required")
        self.admit(parent.receipt, purpose=parent.purpose)
        attempt = self.receipts.creation_attempt(
            parent=parent.receipt, name=name, kind=kind, publication_id=publication_id
        )
        if attempt is None or attempt.parent != parent.receipt:
            raise managed_artifact_refusal("reconciliation_intent_missing")
        if attempt.receipt is not None:
            self.admit(attempt.receipt, purpose=parent.purpose)
            return attempt.receipt
        parent_id = escape_google_drive_query_literal(parent.receipt.artifact_id)
        query = (
            f"'{parent_id}' in parents and trashed = false and "
            f"appProperties has {{ key='{CREATION_MARKER}' and value='{attempt.creation_id}' }}"
        )
        page_token = None
        seen_tokens: set[str] = set()
        candidates: list[ArtifactCreationReceipt] = []
        while True:
            self._handoff(parent, "drive.files.list.reconcile_creation")
            page = execute_request(
                self.admission.drive.files().list(
                    q=query,
                    fields="files(id,mimeType,trashed,parents,appProperties),nextPageToken",
                    pageSize=100,
                    pageToken=page_token,
                ),
                action="drive.files.list.reconcile_creation",
                retry=RequestRetryPolicy.SINGLE_ATTEMPT,
            )
            self._acknowledge("drive.files.list.reconcile_creation")
            for entry in page.get("files", []):
                identifier = entry.get("id")
                if not isinstance(identifier, str) or not identifier.strip():
                    raise managed_artifact_refusal("reconciliation_identity_missing", uncertain=True)
                receipt = ArtifactCreationReceipt(
                    profile_id=parent.receipt.profile_id,
                    root_folder_id=parent.receipt.root_folder_id,
                    artifact_id=identifier,
                    parent_id=parent.receipt.artifact_id,
                    creation_id=attempt.creation_id,
                    kind=kind,
                    publication_id=publication_id,
                )
                validate_creation_metadata(receipt, entry)
                candidates.append(receipt)
            page_token = next_drive_page_token(
                page.get("nextPageToken"), seen_tokens=seen_tokens, action="drive.files.list.reconcile_creation"
            )
            if page_token is None:
                break
        if len(candidates) != 1:
            raise managed_artifact_refusal("reconciliation_requires_one_candidate", uncertain=True)
        self.admit(parent.receipt, purpose=parent.purpose)
        self.receipts.complete_creation(attempt, candidates[0])
        self.admit(candidates[0], purpose=parent.purpose)
        return candidates[0]

    def read_bytes(self, artifact: AdmittedArtifact, *, expected_digest: Hex64Str) -> bytes:
        """Read a recorded binary artifact only for a closed integrity purpose."""
        from .api import execute_media_request

        if artifact.receipt.kind not in _BINARY_KINDS or artifact.purpose not in {
            ManagedArtifactPurpose.BACKUP_INTEGRITY,
            ManagedArtifactPurpose.BASELINE_VERIFICATION,
            ManagedArtifactPurpose.RECONCILIATION,
        }:
            raise OutboundStorageConflictError("binary read purpose is not admitted")
        self._handoff(artifact, "drive.files.get_media.managed")
        payload = execute_media_request(
            self.admission.drive.files().get_media(fileId=artifact.receipt.artifact_id),
            action="drive.files.get_media.managed",
        )
        self._acknowledge("drive.files.get_media.managed")
        _verify_digest(payload, expected_digest)
        self.admit(artifact.receipt, purpose=artifact.purpose)
        return payload

    def write_bytes(self, artifact: AdmittedArtifact, payload: bytes, *, expected_digest: Hex64Str) -> None:
        """Populate a new binary artifact once, preserving earlier or uncertain writes."""
        from googleapiclient.http import MediaIoBaseUpload

        if artifact.receipt.kind not in _BINARY_KINDS or artifact.purpose is not ManagedArtifactPurpose.PUBLICATION:
            raise OutboundStorageConflictError("binary publication purpose is not admitted")
        _verify_digest(payload, expected_digest)
        self.admit(artifact.receipt, purpose=artifact.purpose)
        self.receipts.reserve_content_write(artifact.receipt, digest=expected_digest)
        self._handoff(artifact, "drive.files.update.managed", writes=True)
        execute_request(
            self.admission.drive.files().update(
                body={},
                fileId=artifact.receipt.artifact_id,
                media_body=MediaIoBaseUpload(BytesIO(payload), mimetype="application/octet-stream", resumable=False),
                fields="id",
            ),
            action="drive.files.update.managed",
            retry=RequestRetryPolicy.SINGLE_ATTEMPT,
        )
        self._acknowledge("drive.files.update.managed", writes=True)
        self.admit(artifact.receipt, purpose=artifact.purpose)


def _verify_digest(payload: bytes, expected_digest: str) -> None:
    if sha256_hex(payload) != expected_digest:
        raise OutboundStorageIntegrityError("managed artifact bytes do not match the expected digest")
