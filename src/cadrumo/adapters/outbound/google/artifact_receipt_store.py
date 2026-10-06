"""Encrypted, insert-only custody of acknowledged Google creation identities."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel

from ....application.export.managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind
from ....application.export.publication_receipt import PublicationReceipt
from ....application.user_profile.google_configuration_operation_ports import GoogleConfigurationCommit
from ....core.classification.policies import SensitivityClass
from ....core.hashing import sha256_hex
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ....core.time.clock import now
from ...persistence.storage.secure_object_namespaces import GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
from ...persistence.storage.sql.secure_objects import SecureObjectRepository
from ..storage.errors import OutboundStorageConflictError


class RootCreationAttempt(BaseModel):
    """Durable root intent; a missing response is never treated as absence."""

    model_config = STRICT_FROZEN_CONFIG

    creation_id: UUID
    receipt: ArtifactCreationReceipt | None = None


class ArtifactCreationAttempt(BaseModel):
    """One retained child-create intent, including the exact reconciliation identity."""

    model_config = STRICT_FROZEN_CONFIG

    creation_id: UUID
    parent: ArtifactCreationReceipt
    name: str
    kind: ManagedArtifactKind
    publication_id: UUID
    receipt: ArtifactCreationReceipt | None = None


class GoogleArtifactReceiptStore:
    """Local evidence that a particular profile created an exact provider identity."""

    def __init__(
        self, repository: SecureObjectRepository, *, profile_id: UUID, commit: GoogleConfigurationCommit | None = None
    ) -> None:
        """Bind receipt reads and insert-only writes to one admitted profile repository."""
        self._repository = repository
        self._profile_id = profile_id
        self._commit = commit

    def begin_creation(
        self, *, parent: ArtifactCreationReceipt, name: str, kind: ManagedArtifactKind, publication_id: UUID
    ) -> ArtifactCreationAttempt:
        """Record intent before creation; the same publication target cannot be recreated."""
        if parent.profile_id != self._profile_id:
            raise OutboundStorageConflictError("creation parent belongs to another profile")
        attempt = ArtifactCreationAttempt(
            creation_id=uuid4(), parent=parent, name=name, kind=kind, publication_id=publication_id
        )
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        self._save(
            namespace=definition.namespace,
            object_key=self._creation_key(attempt),
            classification=definition.sensitivity,
            schema_version=definition.schema_version,
            written_at=now(),
            payload=attempt.model_dump_json().encode(),
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )
        return attempt

    def creation_attempt(
        self, *, parent: ArtifactCreationReceipt, name: str, kind: ManagedArtifactKind, publication_id: UUID
    ) -> ArtifactCreationAttempt | None:
        """Recover only the locally retained intent for one exact publication target."""
        selector = ArtifactCreationAttempt(
            creation_id=publication_id, parent=parent, name=name, kind=kind, publication_id=publication_id
        )
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        record = self._repository.load(
            definition.namespace,
            self._creation_key(selector),
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        )
        return ArtifactCreationAttempt.model_validate_json(record.payload) if record is not None else None

    def complete_creation(self, attempt: ArtifactCreationAttempt, receipt: ArtifactCreationReceipt) -> None:
        """Retain the exact acknowledged result without replacing a competing intent."""
        if (
            receipt.profile_id != self._profile_id
            or receipt.parent_id != attempt.parent.artifact_id
            or receipt.root_folder_id != attempt.parent.root_folder_id
            or receipt.creation_id != attempt.creation_id
            or receipt.kind is not attempt.kind
            or receipt.publication_id != attempt.publication_id
        ):
            raise OutboundStorageConflictError("creation acknowledgement contradicts retained intent")
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        key = self._creation_key(attempt)
        record = self._repository.load(
            definition.namespace,
            key,
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        )
        if record is None or ArtifactCreationAttempt.model_validate_json(record.payload) != attempt:
            raise OutboundStorageConflictError("creation intent changed before acknowledgement")
        self.record(receipt)
        completed = ArtifactCreationAttempt.model_validate({**attempt.model_dump(), "receipt": receipt})
        self._save(
            namespace=definition.namespace,
            object_key=key,
            classification=definition.sensitivity,
            schema_version=definition.schema_version,
            written_at=now(),
            payload=completed.model_dump_json().encode(),
            expected_revision_id=record.revision_id,
        )

    def reserve_content_write(self, receipt: ArtifactCreationReceipt, *, digest: str) -> None:
        """A write intent is single-use, including when its response is lost."""
        if self.load(receipt.artifact_id) != receipt:
            raise OutboundStorageConflictError("content write lacks retained creation identity")
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        self._save(
            namespace=definition.namespace,
            object_key=f"{self._profile_id}:content-write:{receipt.artifact_id}",
            classification=definition.sensitivity,
            schema_version=definition.schema_version,
            written_at=now(),
            payload=digest.encode("ascii"),
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )

    def _creation_key(self, attempt: ArtifactCreationAttempt) -> str:
        identity = sha256_hex(
            f"{attempt.parent.artifact_id}\0{attempt.kind.value}\0{attempt.publication_id}\0{attempt.name}".encode()
        )
        return f"{self._profile_id}:creation:{identity}"

    def load_publication(self, publication_id: UUID) -> PublicationReceipt | None:
        """Read the exact local publication checkpoint without inspecting provider content."""
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        record = self._repository.load(
            definition.namespace,
            f"{self._profile_id}:publication:{publication_id}",
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        )
        if record is None:
            return None
        receipt = PublicationReceipt.model_validate_json(record.payload)
        if receipt.profile_id != self._profile_id or receipt.publication_id != publication_id:
            raise OutboundStorageConflictError("stored publication does not match its custody key")
        return receipt

    def save_publication(self, receipt: PublicationReceipt, *, previous: PublicationReceipt | None) -> None:
        """Advance one exact publication with optimistic custody; never replace another snapshot."""
        if receipt.profile_id != self._profile_id:
            raise OutboundStorageConflictError("publication belongs to another profile")
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        key = f"{self._profile_id}:publication:{receipt.publication_id}"
        record = self._repository.load(
            definition.namespace,
            key,
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        )
        prior = PublicationReceipt.model_validate_json(record.payload) if record is not None else None
        if prior != previous:
            raise OutboundStorageConflictError("publication checkpoint changed concurrently")
        if previous is not None and (
            previous.publication_id != receipt.publication_id
            or previous.snapshot_digest != receipt.snapshot_digest
            or previous.root != receipt.root
            or previous.profile_id != receipt.profile_id
            or previous.advance(receipt.state, artifacts=receipt.artifacts, failure=receipt.failure) != receipt
        ):
            raise OutboundStorageConflictError("publication transition contradicts its retained checkpoint")
        self._save(
            namespace=definition.namespace,
            object_key=key,
            classification=definition.sensitivity,
            schema_version=definition.schema_version,
            written_at=now(),
            payload=receipt.model_dump_json().encode(),
            expected_revision_id=record.revision_id if record is not None else ABSENT_SECURE_OBJECT_REVISION_ID,
        )

    def load(self, artifact_id: str) -> ArtifactCreationReceipt | None:
        """Return only an exact-profile record, never a provider-derived receipt."""
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        record = self._repository.load(
            definition.namespace,
            f"{self._profile_id}:artifact:{artifact_id}",
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        )
        if record is None:
            return None
        receipt = ArtifactCreationReceipt.model_validate_json(record.payload)
        if receipt.profile_id != self._profile_id or receipt.artifact_id != artifact_id:
            raise OutboundStorageConflictError("stored artifact creation identity does not match its custody key")
        return receipt

    def record(self, receipt: ArtifactCreationReceipt) -> None:
        """Insert an acknowledged creation once; existing identity must match exactly."""
        if receipt.profile_id != self._profile_id:
            raise OutboundStorageConflictError("artifact creation receipt belongs to another profile")
        existing = self.load(receipt.artifact_id)
        if existing is not None:
            if existing != receipt:
                raise OutboundStorageConflictError("artifact already has a different creation receipt")
            return
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        self._save(
            namespace=definition.namespace,
            object_key=f"{self._profile_id}:artifact:{receipt.artifact_id}",
            classification=definition.sensitivity,
            schema_version=definition.schema_version,
            written_at=now(),
            payload=receipt.model_dump_json().encode("utf-8"),
            expected_revision_id=ABSENT_SECURE_OBJECT_REVISION_ID,
        )

    def root_attempt(self) -> RootCreationAttempt | None:
        """Read prior root creation intent without searching the provider account."""
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        record = self._repository.load(
            definition.namespace,
            f"{self._profile_id}:root-attempt:root",
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        )
        return RootCreationAttempt.model_validate_json(record.payload) if record is not None else None

    def root_placement(self, root_id: str) -> tuple[str, str, str] | None:
        """Require completed placement before content access after a move starts."""
        from .root_layout import load_root_layout

        state = load_root_layout(self._repository, self._profile_id)
        if state is None or state.phase in {"parent_pending", "ready"}:
            return None
        if (
            state.root_id != root_id
            or state.phase != "complete"
            or state.parent_id is None
            or state.source_parent is None
        ):
            raise OutboundStorageConflictError("root layout requires exact placement reconciliation")
        return state.parent_id, str(state.parent_creation_id), state.source_parent

    def begin_root_creation(self) -> RootCreationAttempt:
        """Persist a single intent before any remote create; ambiguity blocks retry."""
        attempt = RootCreationAttempt(creation_id=uuid4())
        self._save_root_attempt(attempt, expected_revision=ABSENT_SECURE_OBJECT_REVISION_ID)
        return attempt

    def complete_root_creation(self, receipt: ArtifactCreationReceipt) -> None:
        """Retain the acknowledged identity even when later sign-in persistence fails."""
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        record = self._repository.load(
            definition.namespace,
            f"{self._profile_id}:root-attempt:root",
            expected_class=definition.sensitivity,
            max_supported_version=definition.schema_version,
        )
        if record is None:
            raise OutboundStorageConflictError("root creation has no retained intent")
        attempt = RootCreationAttempt.model_validate_json(record.payload)
        if attempt.creation_id != receipt.creation_id or receipt.profile_id != self._profile_id:
            raise OutboundStorageConflictError("root creation acknowledgement does not match its intent")
        self.record(receipt)
        self._save_root_attempt(
            RootCreationAttempt(creation_id=attempt.creation_id, receipt=receipt), expected_revision=record.revision_id
        )

    def _save_root_attempt(self, attempt: RootCreationAttempt, *, expected_revision: str) -> None:
        definition = GOOGLE_ARTIFACT_RECEIPTS_NAMESPACE
        self._save(
            namespace=definition.namespace,
            object_key=f"{self._profile_id}:root-attempt:root",
            classification=definition.sensitivity,
            schema_version=definition.schema_version,
            written_at=now(),
            payload=attempt.model_dump_json().encode("utf-8"),
            expected_revision_id=expected_revision,
        )

    def _save(
        self,
        *,
        namespace: str,
        object_key: str,
        classification: SensitivityClass,
        schema_version: int,
        written_at: datetime,
        payload: bytes,
        expected_revision_id: str,
    ) -> None:
        """Retain evidence under the caller's canonical write admission."""

        def save() -> None:
            self._repository.save(
                namespace=namespace,
                object_key=object_key,
                classification=classification,
                schema_version=schema_version,
                written_at=written_at,
                payload=payload,
                expected_revision_id=expected_revision_id,
            )

        if self._commit is None:
            save()
        else:
            self._commit(save, changed=lambda _result: True)
