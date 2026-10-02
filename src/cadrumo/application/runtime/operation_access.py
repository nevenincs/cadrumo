"""Typed local operation projections over the canonical application services."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, JsonValue

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.frontend_requests import (
    OperationCancellationRequestV1,
    OperationDetachRequestV1,
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRequestV1,
    OperationReviewProjectionRequestV1,
    OperationSubmissionReceiptV1,
)
from ..operations.models import OperationDefinitionId, OperationId, OperationReference
from ..operations.registry import OperationPublicDefinitionContractV1
from ..operations.secret_submission import OperationSecretRequirement
from ..user_profile.access_contracts import AccessAction
from .projection_pages import ProjectionPage, ProjectionPageRequest
from .submission_payload import SUBMISSION_PAYLOAD_MAX_BYTES, SubmissionPayloadDescriptor

type OperationManagementRequest = (
    OperationCancellationRequestV1
    | OperationDetachRequestV1
    | OperationResponseApplyRequestV1
    | OperationResponseRejectRequestV1
    | OperationResponseControlRequestV1
)


def operation_management_action(request: OperationManagementRequest) -> AccessAction:
    """Map the canonical control request to its independently scoped access door."""
    if isinstance(request, OperationCancellationRequestV1):
        return AccessAction.CANCEL
    if isinstance(request, OperationDetachRequestV1):
        return AccessAction.DETACH
    return AccessAction.RESPOND


class RuntimeOperationTarget(BaseModel):
    """Exact connection/session coordinates, never a credential or ambient profile."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    profile_id: UUID
    session_id: UUID


class RuntimeOperationSubmit(RuntimeOperationTarget):
    """Private operands decoded only by the worker's current registered owner."""

    action: Literal["operation_submit"] = "operation_submit"
    definition_id: OperationDefinitionId
    subject_ref: OperationReference
    payload_json: str = Field(min_length=2, max_length=SUBMISSION_PAYLOAD_MAX_BYTES, repr=False)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256, repr=False)


class RuntimeOperationSubmitPayload(RuntimeOperationTarget):
    """Begin one non-resumable protected upload before canonical submission."""

    action: Literal["operation_submit_payload"] = "operation_submit_payload"
    definition_id: OperationDefinitionId
    subject_ref: OperationReference
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256, repr=False)
    descriptor: SubmissionPayloadDescriptor


class RuntimeOperationControl(RuntimeOperationTarget):
    """Explicit start or freshly authorized canonical continuation."""

    action: Literal["operation_start", "operation_resume"]
    operation_id: OperationId


class RuntimeOperationSecret(RuntimeOperationTarget):
    """Exact nonsecret requirement; bytes follow only a protected readiness reply."""

    action: Literal["operation_secret"] = "operation_secret"
    requirement: OperationSecretRequirement


class RuntimeOperationObserve(RuntimeOperationTarget):
    """Bounded canonical observation, requiring separate disclosure permission."""

    action: Literal["operation_observe"] = "operation_observe"
    observation: OperationObservationRequestV1


class RuntimeOperationContract(RuntimeOperationTarget):
    """Discover one permitted current registered definition."""

    action: Literal["operation_contract"] = "operation_contract"
    definition_id: OperationDefinitionId


class RuntimeOperationResult(RuntimeOperationTarget):
    """Request only a registered canonical result projection at its exact revision."""

    action: Literal["operation_result"] = "operation_result"
    result: OperationResultProjectionRequestV1


class RuntimeOperationReview(RuntimeOperationTarget):
    """Request a registered review projection, without acquiring response authority."""

    action: Literal["operation_review"] = "operation_review"
    review: OperationReviewProjectionRequestV1


class RuntimeOperationResultPage(RuntimeOperationTarget):
    """Read one bounded page of an exact settled registered result."""

    action: Literal["operation_result_page"] = "operation_result_page"
    result: OperationResultProjectionRequestV1
    page: ProjectionPageRequest


class RuntimeOperationManage(RuntimeOperationTarget):
    """Address one canonical lifecycle or response control through current authority."""

    action: Literal["operation_manage"] = "operation_manage"
    management: OperationManagementRequest


type RuntimeOperationRequest = (
    RuntimeOperationSubmit
    | RuntimeOperationSubmitPayload
    | RuntimeOperationSecret
    | RuntimeOperationControl
    | RuntimeOperationObserve
    | RuntimeOperationContract
    | RuntimeOperationResult
    | RuntimeOperationResultPage
    | RuntimeOperationReview
    | RuntimeOperationManage
)


class RuntimeOperationReplyIdentity(BaseModel):
    """Correlate a public reply to the verified runtime and its current connection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID


class RuntimeOperationSubmitted(RuntimeOperationReplyIdentity):
    """Durable submission receipt; no response capability crosses the wire."""

    kind: Literal["operation_submitted"] = "operation_submitted"
    receipt: OperationSubmissionReceiptV1


class RuntimeOperationPayloadReady(RuntimeOperationReplyIdentity):
    """Exact bounded upload readiness; it confers no operation or effect authority."""

    kind: Literal["operation_payload_ready"] = "operation_payload_ready"
    descriptor: SubmissionPayloadDescriptor


class RuntimeOperationAcknowledged(RuntimeOperationReplyIdentity):
    """Lifecycle admission acknowledgement, never a claim of committed effects."""

    kind: Literal["operation_acknowledged"] = "operation_acknowledged"
    operation_id: OperationId


class RuntimeOperationObserved(RuntimeOperationReplyIdentity):
    """Canonical private observation released under current destination consent."""

    kind: Literal["operation_observed"] = "operation_observed"
    observation: OperationObservationResultV1


class RuntimeOperationContractReply(RuntimeOperationReplyIdentity):
    """The actual registered public contract, with no backend-readiness assertion."""

    kind: Literal["operation_contract"] = "operation_contract"
    contract: OperationPublicDefinitionContractV1
    request_json_schema: dict[str, JsonValue]


class RuntimeOperationProjected(RuntimeOperationReplyIdentity):
    """Canonical projection envelope already validated by its registered owner.

    The JSON object preserves the registered model's complete fields across
    transport. It is never populated from raw secure operands or caller data.
    """

    kind: Literal["operation_projected"] = "operation_projected"
    operation_id: OperationId
    projection_kind: Literal["result", "review"]
    document: dict[str, JsonValue]


class RuntimeOperationManaged(RuntimeOperationReplyIdentity):
    """Canonical validated service outcome released under current policy."""

    kind: Literal["operation_managed"] = "operation_managed"
    operation_id: OperationId
    document: dict[str, JsonValue]


class RuntimeOperationPage(RuntimeOperationReplyIdentity):
    """A result page released under newly checked current disclosure authority."""

    kind: Literal["operation_page"] = "operation_page"
    operation_id: OperationId
    page: ProjectionPage


type RuntimeOperationReply = (
    RuntimeOperationSubmitted
    | RuntimeOperationPayloadReady
    | RuntimeOperationAcknowledged
    | RuntimeOperationObserved
    | RuntimeOperationContractReply
    | RuntimeOperationProjected
    | RuntimeOperationManaged
    | RuntimeOperationPage
)
