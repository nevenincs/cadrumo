"""Typed local operation projections over the canonical application services."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationSubmissionReceiptV1,
)
from ..operations.models import OperationDefinitionId, OperationId, OperationReference
from ..operations.registry import OperationPublicDefinitionContractV1


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
    payload_json: str = Field(min_length=2, max_length=60000, repr=False)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=256, repr=False)


class RuntimeOperationControl(RuntimeOperationTarget):
    """Explicit start or freshly authorized canonical continuation."""

    action: Literal["operation_start", "operation_resume"]
    operation_id: OperationId


class RuntimeOperationObserve(RuntimeOperationTarget):
    """Bounded canonical observation, requiring separate disclosure permission."""

    action: Literal["operation_observe"] = "operation_observe"
    observation: OperationObservationRequestV1


class RuntimeOperationContract(RuntimeOperationTarget):
    """Discover one permitted current registered definition."""

    action: Literal["operation_contract"] = "operation_contract"
    definition_id: OperationDefinitionId


type RuntimeOperationRequest = (
    RuntimeOperationSubmit | RuntimeOperationControl | RuntimeOperationObserve | RuntimeOperationContract
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


type RuntimeOperationReply = (
    RuntimeOperationSubmitted | RuntimeOperationAcknowledged | RuntimeOperationObserved | RuntimeOperationContractReply
)
