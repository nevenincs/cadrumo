"""Immutable publication checkpoints retained independently of mutable review copies."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG
from .managed_artifact_ports import ArtifactCreationReceipt, ManagedArtifactKind


class PublicationState(StrEnum):
    """Acknowledged checkpoints and explicit incomplete effects."""

    PREPARED = "prepared"
    REMOTE_CREATED = "remote-created"
    POPULATED = "populated"
    VERIFIED = "verified"
    PUBLISHED = "published"
    PARTIAL = "partial"
    UNCERTAIN = "uncertain"


class PublicationFailure(StrEnum):
    """Safe classifications without provider messages or private content."""

    ADMISSION = "admission"
    CREATE_UNKNOWN = "create_unknown"
    POPULATION = "population"
    INTEGRITY = "integrity"
    CANCELLED = "cancelled"
    CUSTODY = "custody"


class PublicationReceipt(BaseModel):
    """A single publication's identity and known effects in encrypted custody."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1] = 1
    publication_id: UUID
    profile_id: UUID
    root: ArtifactCreationReceipt
    snapshot_digest: Hex64Str
    package_digest: Hex64Str | None = None
    state: PublicationState = PublicationState.PREPARED
    artifacts: tuple[ArtifactCreationReceipt, ...] = ()
    failure: PublicationFailure | None = None
    predecessor_publication_id: UUID | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _bind_artifacts(self) -> Self:
        if self.root.profile_id != self.profile_id or self.root.kind is not ManagedArtifactKind.ROOT:
            raise ValueError("publication root must bind the exact profile")
        if len({item.artifact_id for item in self.artifacts}) != len(self.artifacts):
            raise ValueError("publication artifacts must have distinct identities")
        for item in self.artifacts:
            if (
                item.profile_id != self.profile_id
                or item.root_folder_id != self.root.artifact_id
                or item.publication_id != self.publication_id
            ):
                raise ValueError("publication artifact identity does not match its receipt")
        if self.state in {PublicationState.PARTIAL, PublicationState.UNCERTAIN}:
            if self.failure is None:
                raise ValueError("incomplete publication requires a failure classification")
        elif self.failure is not None:
            raise ValueError("successful checkpoint cannot carry an unresolved failure")
        if self.state not in {PublicationState.PREPARED, PublicationState.UNCERTAIN} and not self.artifacts:
            raise ValueError("acknowledged remote effects require artifact identities")
        return self

    def advance(
        self,
        state: PublicationState,
        *,
        artifacts: tuple[ArtifactCreationReceipt, ...] | None = None,
        failure: PublicationFailure | None = None,
    ) -> PublicationReceipt:
        """Advance one checkpoint; uncertain effects need reconciliation, never blind creation."""
        following = {
            PublicationState.PREPARED: PublicationState.REMOTE_CREATED,
            PublicationState.REMOTE_CREATED: PublicationState.POPULATED,
            PublicationState.POPULATED: PublicationState.VERIFIED,
            PublicationState.VERIFIED: PublicationState.PUBLISHED,
        }
        if self.state not in following:
            raise ValueError("terminal publication cannot advance without a separate reconciliation")
        if state not in {following[self.state], PublicationState.PARTIAL, PublicationState.UNCERTAIN}:
            raise ValueError("publication checkpoints cannot be skipped")
        values = self.model_dump()
        values.update(state=state, artifacts=self.artifacts if artifacts is None else artifacts, failure=failure)
        return PublicationReceipt.model_validate(values)


class ReadablePayloadCategory(StrEnum):
    """Categories disclosed independently of ciphertext backup authorization."""

    CALCULATION = "calculation"
    LEDGER = "ledger"
    ORIGINAL_ATTACHMENT = "original_attachment"
    EVIDENCE_PACKAGE = "evidence_package"


class ReadableExportAuthorization(BaseModel):
    """Per-publication disclosure, independently admitted from ciphertext backup."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    publication_id: UUID
    root_folder_id: str = Field(min_length=1)
    snapshot_digest: Hex64Str
    payload_categories: tuple[ReadablePayloadCategory, ...] = Field(min_length=1)
    disclosure_digest: Hex64Str
