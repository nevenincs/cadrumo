"""Profile-bound saved-revision publication and human disclosure contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.hashing import content_hash_hex
from ...core.hex import Hex64Str
from ...core.identity.digest import ContentDigest
from ...core.identity.hex_ids import CalculationRevisionId
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.interactions import OperationResponseIntentValue
from ..operations.models import CredentialFreeOperationRequest, OperationIdentity, OperationRevision
from ..operations.registry import OperationSchemaBindingV1
from ..user_profile.google_configuration_operation_ports import (
    GoogleConfigurationAcknowledgement,
    GoogleConfigurationCommit,
    GoogleConfigurationHandoff,
)
from .managed_artifact_ports import ArtifactCreationReceipt
from .publication_receipt import PublicationReceipt, ReadableExportAuthorization, ReadablePayloadCategory
from .review_snapshot import ReviewSnapshot

GOOGLE_REVIEW_OPERATION_DEFINITION_ID = "export.google-review"


class GoogleReviewRequest(CredentialFreeOperationRequest):
    """Select retained local evidence, never caller-provided financial contents."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    calculation_revision_id: CalculationRevisionId
    publication_id: UUID
    filing_record_id: Hex64Str | None = Field(default=None, exclude_if=lambda value: value is None)


class GoogleReviewProposal(BaseModel):
    """Exact immutable baseline and destination inspected before publication."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: OperationIdentity
    revision: OperationRevision
    request: GoogleReviewRequest
    snapshot_ref: ContentDigest
    snapshot_digest: ContentDigest
    publication: PublicationReceipt
    payload_categories: tuple[ReadablePayloadCategory, ...]

    @property
    def digest(self) -> ContentDigest:
        """Bind consent to contents, destination and operation identity."""
        return content_hash_hex(self.model_dump(mode="json"))


class GoogleReviewProjection(BaseModel):
    """Human disclosure of the exact selected revision and readable destination."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: OperationIdentity
    revision: OperationRevision
    profile_id: UUID
    publication_id: UUID
    calculation_revision_id: CalculationRevisionId
    filing_record_id: Hex64Str | None = Field(default=None, exclude_if=lambda value: value is None)
    root_folder_id: str
    snapshot_digest: ContentDigest
    payload_categories: tuple[ReadablePayloadCategory, ...]
    readable_by_authorized_users: Literal[True] = True
    reviewed_proposal_digest: ContentDigest


class GoogleReviewResponse(BaseModel):
    """Human intent; only the runtime's consumed response grants authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    response_version: Literal[1] = 1
    intent: OperationResponseIntentValue


class GoogleReviewResult(BaseModel):
    """Verified publication identity, without credentials or financial rows."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    profile_id: UUID
    publication_id: UUID
    snapshot_digest: ContentDigest
    root_folder_id: str
    spreadsheet_id: str
    spreadsheet_url: str


class GoogleReviewExecutionResult(BaseModel):
    """Encrypted terminal result correlated to the exact invocation."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    identity: OperationIdentity
    result: GoogleReviewResult
    effect: Literal["none", "updated"]


class GoogleReviewPublish(Protocol):
    """Publish using admitted effect and receipt custody callbacks."""

    def __call__(
        self,
        snapshot: ReviewSnapshot,
        publication: PublicationReceipt,
        authorization: ReadableExportAuthorization,
        *,
        commit: GoogleConfigurationCommit,
        before_handoff: GoogleConfigurationHandoff,
        acknowledged: GoogleConfigurationAcknowledgement,
    ) -> PublicationReceipt:
        """Return the persisted provider-verified publication receipt."""
        ...


@dataclass(frozen=True, slots=True)
class GoogleReviewOperationPorts:
    """Immutable worker profile and authority binding; preparation is local only."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    load_snapshot: Callable[[CalculationRevisionId], ReviewSnapshot]
    load_root: Callable[[], ArtifactCreationReceipt]
    publish: GoogleReviewPublish
    load_publication: Callable[[UUID], PublicationReceipt | None]
    load_filing_snapshot: Callable[[CalculationRevisionId, Hex64Str], ReviewSnapshot] | None = None


class GoogleReviewOperationPortsFactory(Protocol):
    """Compose local ports without acquiring credentials or contacting Google."""

    def __call__(self, *, profile_id: UUID, operation: PinnedAuthorityOperation) -> GoogleReviewOperationPorts:
        """Bind the exact worker authority pin and active profile."""
        ...


GOOGLE_REVIEW_REVIEW_SCHEMA_BINDING = OperationSchemaBindingV1.bind(
    schema_id=GOOGLE_REVIEW_OPERATION_DEFINITION_ID + ".review", schema_version=1, model_type=GoogleReviewProjection
)
GOOGLE_REVIEW_RESPONSE_SCHEMA_BINDING = OperationSchemaBindingV1.bind(
    schema_id=GOOGLE_REVIEW_OPERATION_DEFINITION_ID + ".response", schema_version=1, model_type=GoogleReviewResponse
)
