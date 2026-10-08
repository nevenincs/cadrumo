"""Journaled placement of known profile roots beneath the application folder.

:class:`SecureObjectRepository` stores the encrypted profile records.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel

from ....application.export.managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ....application.user_profile.google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationCommit,
    GoogleConfigurationHandoff,
)
from ....core.external_constants import GOOGLE_DRIVE_FOLDER_MIME_TYPE
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....core.time.clock import now
from ....core.type_guards import is_str_keyed_dict
from ...persistence.storage.secure_object_namespaces import GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
from ...persistence.storage.sql.secure_objects import SecureObjectRepository
from .api import RequestRetryPolicy, execute_request
from .artifact_admission import CREATION_MARKER, KIND_MARKER, managed_artifact_refusal, validate_creation_metadata
from .drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE

if TYPE_CHECKING:
    from googleapiclient._apis.drive.v3.resources import DriveResource

_FIELDS = "id,name,mimeType,trashed,parents,appProperties,ownedByMe"
_APP_KIND = "application_root"
APPLICATION_ROOT_ID_MARKER = "cadrumo_application_root_id"


class RootLayoutState(BaseModel):
    """Placement history is separate from immutable artifact creation receipts."""

    model_config = STRICT_FROZEN_CONFIG
    profile_id: UUID
    root_id: str
    parent_creation_id: UUID
    parent_id: str | None = None
    phase: Literal["parent_pending", "ready", "moving", "complete"] = "parent_pending"
    source_parent: str | None = None


def load_root_layout(repository: SecureObjectRepository, profile_id: UUID) -> RootLayoutState | None:
    """Read only this profile's encrypted placement journal.

    The ``repository`` parameter uses :class:`SecureObjectRepository`, which stores the encrypted profile records.
    """
    definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
    record = repository.load(
        definition.namespace,
        f"{profile_id}:root-layout:root",
        expected_class=definition.sensitivity,
        max_supported_version=definition.schema_version,
    )
    if record is None:
        return None
    state = RootLayoutState.model_validate_json(record.payload)
    if state.profile_id != profile_id:
        raise managed_artifact_refusal("layout_profile_mismatch")
    return state


class GoogleRootLayout:
    """One explicit layout operation; ordinary reads never arrange folders."""

    def __init__(
        self,
        drive: DriveResource,
        repository: SecureObjectRepository,
        *,
        root: ArtifactCreationReceipt,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
    ) -> None:
        """Bind exact creation evidence and the supervisor's effect/custody callbacks."""
        if root.kind is not ManagedArtifactKind.ROOT:
            raise managed_artifact_refusal("layout_requires_profile_root")
        self.drive, self.repository, self.root = drive, repository, root
        self.commit, self.before, self.ack = commit, before_handoff, acknowledged

    def _call(self, request, action: str, *, writes: bool = False):
        self.before(action, writes=writes)
        result = execute_request(request, action=action, retry=RequestRetryPolicy.SINGLE_ATTEMPT)
        self.ack(action, writes=writes)
        return result

    def _get(self, identifier: str):
        return self._call(self.drive.files().get(fileId=identifier, fields=_FIELDS), "drive.layout.get")

    def _save(self, state: RootLayoutState, prior: RootLayoutState | None) -> None:
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        key = f"{self.root.profile_id}:root-layout:root"
        record = self.repository.load(
            definition.namespace,
            key,
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        )
        existing = RootLayoutState.model_validate_json(record.payload) if record is not None else None
        if existing != prior:
            raise managed_artifact_refusal("layout_changed_concurrently")
        self.commit(
            lambda: self.repository.save(
                namespace=definition.namespace,
                object_key=key,
                classification=definition.sensitivity,
                schema_version=definition.schema_version,
                written_at=now(),
                payload=state.model_dump_json().encode(),
                expected_revision_id=record.revision_id if record else ABSENT_SECURE_OBJECT_REVISION_ID,
            ),
            changed=lambda _: True,
        )

    def _find_parent(self) -> list[dict[str, object]]:
        # Explicitly authorized organizational-parent metadata exception. Never
        # list contents, search by name alone, or adopt a profile root here.
        query = (
            "'root' in parents and trashed = false "
            f"and mimeType = '{GOOGLE_DRIVE_FOLDER_MIME_TYPE}' "
            f"and appProperties has {{ key='{OWNERSHIP_KEY}' and value='{OWNERSHIP_VALUE}' }} "
            f"and appProperties has {{ key='{KIND_MARKER}' and value='{_APP_KIND}' }}"
        )
        found = []
        page = None
        seen = set()
        while True:
            result = self._call(
                self.drive.files().list(
                    q=query,
                    spaces="drive",
                    fields=f"nextPageToken,files({_FIELDS})",
                    pageToken=page,
                ),
                "drive.layout.find-parent",
            )
            found.extend(result.get("files", []))
            page = result.get("nextPageToken")
            if not page:
                return found
            if page in seen:
                raise managed_artifact_refusal("layout_repeated_page")
            seen.add(page)

    def _validate_parent(self, entry: Mapping[str, object], creation_id: UUID, my_drive: str) -> None:
        props = entry.get("appProperties", {})
        if not is_str_keyed_dict(props):
            raise managed_artifact_refusal("layout_parent_identity_mismatch")
        if (
            entry.get("mimeType") != GOOGLE_DRIVE_FOLDER_MIME_TYPE
            or entry.get("trashed") is not False
            or entry.get("name") != "Cadrumo"
            or entry.get("parents") != [my_drive]
            or entry.get("ownedByMe") is not True
            or props.get(APPLICATION_ROOT_ID_MARKER) != entry.get("id")
            or props.get(OWNERSHIP_KEY) != OWNERSHIP_VALUE
            or props.get(KIND_MARKER) != _APP_KIND
            or props.get(CREATION_MARKER) != str(creation_id)
        ):
            raise managed_artifact_refusal("layout_parent_identity_mismatch")

    def organize(self) -> str:
        """Move a known root once; uncertain moves reconcile by exact metadata."""
        root = self._get(self.root.artifact_id)
        validate_creation_metadata(self.root, root)
        state = load_root_layout(self.repository, self.root.profile_id)
        if state is not None and state.root_id != self.root.artifact_id:
            raise managed_artifact_refusal("layout_root_mismatch")
        # drive.file cannot read My Drive itself. Retain the known root's
        # source and verify it against the application folder created/listed
        # directly under 'root'; no ancestor resource read is necessary.
        parents = root.get("parents")
        my_drive = state.source_parent if state is not None else None
        if my_drive is None:
            if not isinstance(parents, list) or len(parents) != 1 or not isinstance(parents[0], str):
                raise managed_artifact_refusal("layout_source_parent_missing")
            my_drive = parents[0]
        if state is None or state.parent_id is None:
            candidates = self._find_parent()
            if len(candidates) > 1:
                raise managed_artifact_refusal("layout_parent_ambiguous")
            if candidates:
                parent = candidates[0]
                try:
                    props = parent.get("appProperties", {})
                    if not is_str_keyed_dict(props) or not isinstance(value := props.get(CREATION_MARKER), str):
                        raise ValueError("missing creation marker")
                    creation_id = UUID(value)
                except (ValueError, TypeError):
                    raise managed_artifact_refusal("layout_parent_creation_missing") from None
                if state is not None and state.parent_creation_id != creation_id:
                    raise managed_artifact_refusal("layout_parent_creation_uncertain", uncertain=True)
                self._validate_parent(parent, creation_id, my_drive)
                updated = RootLayoutState(
                    profile_id=self.root.profile_id,
                    root_id=self.root.artifact_id,
                    parent_creation_id=creation_id,
                    parent_id=str(parent["id"]),
                    phase="ready",
                    source_parent=my_drive,
                )
                self._save(updated, state)
                state = updated
            else:
                if state is not None:
                    raise managed_artifact_refusal("layout_parent_creation_uncertain", uncertain=True)
                generated = self._call(
                    self.drive.files().generateIds(count=1, space="drive", type="files"),
                    "drive.layout.generate-parent-id",
                )
                identifiers = generated.get("ids")
                if not isinstance(identifiers, list) or len(identifiers) != 1 or not isinstance(identifiers[0], str):
                    raise managed_artifact_refusal("layout_parent_id_missing")
                state = RootLayoutState(
                    profile_id=self.root.profile_id,
                    root_id=self.root.artifact_id,
                    parent_creation_id=uuid4(),
                    parent_id=identifiers[0],
                    source_parent=my_drive,
                )
                self._save(state, None)
                parent_identifier = identifiers[0]
                parent = self._call(
                    self.drive.files().create(
                        body={
                            "id": parent_identifier,
                            "name": "Cadrumo",
                            "mimeType": GOOGLE_DRIVE_FOLDER_MIME_TYPE,
                            "parents": ["root"],
                            "appProperties": {
                                OWNERSHIP_KEY: OWNERSHIP_VALUE,
                                KIND_MARKER: _APP_KIND,
                                CREATION_MARKER: str(state.parent_creation_id),
                                APPLICATION_ROOT_ID_MARKER: parent_identifier,
                            },
                        },
                        fields="id",
                    ),
                    "drive.layout.create-parent",
                    writes=True,
                )
                identifier = parent.get("id")
                if identifier != state.parent_id:
                    raise managed_artifact_refusal("layout_parent_response_missing", uncertain=True)
                updated = state.model_copy(update={"parent_id": identifier, "phase": "ready"})
                self._save(updated, state)
                state = updated
        if state.parent_id is None:
            raise managed_artifact_refusal("layout_parent_missing")
        self._validate_parent(self._get(state.parent_id), state.parent_creation_id, my_drive)
        root = self._get(self.root.artifact_id)
        validate_creation_metadata(self.root, root)
        if root.get("parents") == [state.parent_id]:
            if state.phase != "complete":
                self._save(state.model_copy(update={"phase": "complete", "source_parent": my_drive}), state)
            return state.parent_id
        if state.phase in {"moving", "complete"}:
            raise managed_artifact_refusal("layout_move_uncertain_or_displaced", uncertain=state.phase == "moving")
        if root.get("parents") != [my_drive]:
            raise managed_artifact_refusal("layout_source_not_my_drive")
        moving = state.model_copy(update={"phase": "moving", "source_parent": my_drive})
        self._save(moving, state)
        self._call(
            self.drive.files().update(
                fileId=self.root.artifact_id,
                body={},
                addParents=state.parent_id,
                removeParents=my_drive,
                fields=_FIELDS,
            ),
            "drive.layout.move-root",
            writes=True,
        )
        confirmed = self._get(self.root.artifact_id)
        validate_creation_metadata(self.root, confirmed)
        if confirmed.get("parents") != [state.parent_id]:
            raise managed_artifact_refusal("layout_move_unconfirmed", uncertain=True)
        self._save(moving.model_copy(update={"phase": "complete"}), moving)
        return state.parent_id
