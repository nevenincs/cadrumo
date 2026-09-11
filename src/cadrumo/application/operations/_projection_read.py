"""Read-only operation projection resolution stages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, TypeGuard, cast

from pydantic import BaseModel, TypeAdapter, ValidationError

from ...core.identity.digest import ContentDigest
from ...core.operations import OperationInteractionKind, OperationLifecycle, OperationTerminalCondition
from .frontend_contracts import (
    OperationResultProjectionResultV1,
    OperationReviewProjectionResultV1,
    OperationWorkspaceRefreshTargetResultV1,
)
from .frontend_projection import OperationReviewProjectionReferenceV1
from .frontend_requests import (
    OperationResultProjectionRefusalCode,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationResultProjectionVersionHeader,
    OperationReviewProjectionRefusalCode,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
    OperationReviewProjectionVersionHeader,
    OperationWorkspaceRefreshTargetRefusalCode,
    OperationWorkspaceRefreshTargetRefusalV1,
    OperationWorkspaceRefreshTargetRequestV1,
    OperationWorkspaceRefreshTargetSuccessV1,
    OperationWorkspaceRefreshTargetVersionHeader,
)
from .interactions import OperationInteractionRequest, OperationPendingInteraction
from .models import OperationReference, OperationTerminalReceipt
from .persistence.journal import (
    OperationObservationReader,
    OperationPersistedSnapshot,
    OperationSecureReferenceStore,
)
from .registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
    OperationResultProjector,
    OperationWorkspaceRefreshAdapter,
    operation_public_schema_reference,
)

if TYPE_CHECKING:
    from .projection_services import UnavailableSnapshot

_SUPPORTED_VERSION = 1
_CONTENT_DIGEST_ADAPTER: TypeAdapter[ContentDigest] = TypeAdapter(ContentDigest)


async def _read_snapshot(
    reader: OperationObservationReader,
    operation_id: str,
) -> OperationPersistedSnapshot | UnavailableSnapshot | None:
    from .projection_services import read_snapshot

    return await read_snapshot(reader, operation_id)


def _is_persisted_snapshot(snapshot: object) -> TypeGuard[OperationPersistedSnapshot]:
    return isinstance(snapshot, OperationPersistedSnapshot)


@dataclass(frozen=True, slots=True)
class _ReviewContext:
    """Durable facts that have passed the safe REVIEW reference checks."""

    reference: OperationReviewProjectionReferenceV1
    snapshot: OperationPersistedSnapshot
    pending: OperationPendingInteraction
    interaction: OperationInteractionRequest


@dataclass(frozen=True, slots=True)
class _ReviewRegistration:
    """One REVIEW context bound to its immutable public registration."""

    context: _ReviewContext
    registration: OperationPublicDefinitionRegistrationV1


def _review_request_or_refusal(
    request: OperationReviewProjectionVersionHeader | OperationReviewProjectionRequestV1,
) -> OperationReviewProjectionReferenceV1 | OperationReviewProjectionRefusalV1:
    """Validate the versioned request envelope before reading durable state."""
    if request.review_projection_version != _SUPPORTED_VERSION:
        return _review_refusal(
            OperationReviewProjectionRefusalCode.UNSUPPORTED_VERSION,
            requested_version=request.review_projection_version,
        )
    if not isinstance(request, OperationReviewProjectionRequestV1):
        return _review_refusal(
            OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE,
            requested_version=_SUPPORTED_VERSION,
        )
    return request.reference


def _review_reference_is_current(
    reference: OperationReviewProjectionReferenceV1,
    interaction: OperationInteractionRequest,
) -> bool:
    """Require every public reference coordinate to match the checkpoint."""
    return (
        interaction.identity.operation_id == reference.operation_id
        and interaction.interaction_id == reference.interaction_id
        and interaction.revision == reference.revision
        and interaction.expires_at == reference.expires_at
    )


def _review_is_expired(interaction: OperationInteractionRequest, clock: Callable[[], datetime]) -> bool:
    """Check expiry only when the checkpoint carries a deadline."""
    return interaction.expires_at is not None and clock() > interaction.expires_at


async def _load_review_context(
    reader: OperationObservationReader,
    reference: OperationReviewProjectionReferenceV1,
    clock: Callable[[], datetime],
) -> _ReviewContext | OperationReviewProjectionRefusalV1:
    """Read and validate the exact live REVIEW checkpoint for a reference."""
    snapshot = await _read_snapshot(reader, reference.operation_id)
    if snapshot is None:
        return _review_refusal(OperationReviewProjectionRefusalCode.UNKNOWN_OPERATION, requested_version=1)
    if not _is_persisted_snapshot(snapshot):
        return _review_refusal(
            OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE,
            requested_version=1,
        )
    pending = snapshot.pending_interaction
    if pending is None or pending.request.kind is not OperationInteractionKind.REVIEW:
        return _review_refusal(OperationReviewProjectionRefusalCode.REVIEW_NOT_PENDING, requested_version=1)
    interaction = pending.request
    if not _review_reference_is_current(reference, interaction):
        return _review_refusal(OperationReviewProjectionRefusalCode.STALE_REVIEW_REFERENCE, requested_version=1)
    if _review_is_expired(interaction, clock):
        return _review_refusal(OperationReviewProjectionRefusalCode.REVIEW_EXPIRED, requested_version=1)
    return _ReviewContext(reference=reference, snapshot=snapshot, pending=pending, interaction=interaction)


def _review_definition_contract_is_current(
    context: _ReviewContext,
    registration: OperationPublicDefinitionRegistrationV1,
) -> bool:
    """Require both durable and requested contract digests to be current."""
    digest = registration.contract.definition_contract_digest
    return (
        context.snapshot.definition_contract_digest == digest and context.reference.definition_contract_digest == digest
    )


def _review_response_schema_is_current(
    context: _ReviewContext,
    registration: OperationPublicDefinitionRegistrationV1,
) -> bool:
    """Require the interaction response schema to be the registered identity."""
    response_schema = registration.contract.interaction_response_schema
    return response_schema is not None and context.interaction.response_schema_ref == operation_public_schema_reference(
        response_schema
    )


def _lookup_review_registration(
    registry: OperationRegistry,
    context: _ReviewContext,
) -> _ReviewRegistration | OperationReviewProjectionRefusalV1:
    """Bind the checkpoint to the exact public contract and schema identities."""
    try:
        registration = registry.lookup_public_registration(context.snapshot.identity.definition_id)
    except Exception:
        return _review_refusal(
            OperationReviewProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
            requested_version=1,
        )
    if not _review_definition_contract_is_current(context, registration):
        return _review_refusal(
            OperationReviewProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
            requested_version=1,
        )
    if context.reference.review_projection_schema != registration.contract.review_projection_schema:
        return _review_refusal(OperationReviewProjectionRefusalCode.REVIEW_SCHEMA_MISMATCH, requested_version=1)
    if not _review_response_schema_is_current(context, registration):
        return _review_refusal(
            OperationReviewProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
            requested_version=1,
        )
    return _ReviewRegistration(context=context, registration=registration)


async def _resolve_review_projection[ReviewProjectionT: BaseModel](
    registry: OperationRegistry,
    operands: OperationSecureReferenceStore,
    bound: _ReviewRegistration,
) -> OperationReviewProjectionResultV1[ReviewProjectionT]:
    """Resolve, project, and strictly validate one registered REVIEW model."""
    projector = bound.registration.review_projector
    operand_type = bound.registration.reviewed_operand_type
    if projector is None or operand_type is None:
        return _review_refusal(
            OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE,
            requested_version=1,
        )
    try:
        binding = registry.lookup_public_schema_binding(bound.context.reference.review_projection_schema)
        operand = await operands.resolve(bound.context.pending.reviewed_proposal_digest, operand_type)
        projected = projector(operand, bound.context.interaction)
        del operand
        if type(projected) is not binding.model_type:
            raise TypeError("REVIEW projector returned an unregistered model")
        validated = binding.model_type.model_validate(projected.model_dump(mode="python"))
        return OperationReviewProjectionSuccessV1[ReviewProjectionT](
            projection_schema=binding.identity,
            definition_contract_digest=bound.registration.contract.definition_contract_digest,
            projection=cast(ReviewProjectionT, validated),
        )
    except Exception:
        return _review_refusal(
            OperationReviewProjectionRefusalCode.REVIEW_PROJECTION_UNAVAILABLE,
            requested_version=1,
        )


@dataclass(frozen=True, slots=True)
class _RefreshContext:
    """Durable terminal facts that passed the workspace-refresh checks."""

    request: OperationWorkspaceRefreshTargetRequestV1
    snapshot: OperationPersistedSnapshot
    receipt: OperationTerminalReceipt


@dataclass(frozen=True, slots=True)
class _RefreshRegistration:
    """One refresh context bound to its registered adapter and contract."""

    context: _RefreshContext
    registration: OperationPublicDefinitionRegistrationV1
    adapter: OperationWorkspaceRefreshAdapter


def _refresh_request_or_refusal(
    request: OperationWorkspaceRefreshTargetVersionHeader | OperationWorkspaceRefreshTargetRequestV1,
) -> OperationWorkspaceRefreshTargetRequestV1 | OperationWorkspaceRefreshTargetRefusalV1:
    """Validate the refresh-target request envelope before reading state."""
    if request.refresh_target_version != _SUPPORTED_VERSION:
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.UNSUPPORTED_VERSION,
            requested_version=request.refresh_target_version,
        )
    if not isinstance(request, OperationWorkspaceRefreshTargetRequestV1):
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
            requested_version=1,
        )
    return request


async def _load_refresh_context(
    reader: OperationObservationReader,
    request: OperationWorkspaceRefreshTargetRequestV1,
) -> _RefreshContext | OperationWorkspaceRefreshTargetRefusalV1:
    """Read and validate the exact successful terminal snapshot requested."""
    snapshot = await _read_snapshot(reader, request.operation_id)
    if snapshot is None:
        return _refresh_refusal(OperationWorkspaceRefreshTargetRefusalCode.UNKNOWN_OPERATION, requested_version=1)
    if not _is_persisted_snapshot(snapshot):
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
            requested_version=1,
        )
    receipt = snapshot.terminal_receipt
    if snapshot.lifecycle is not OperationLifecycle.TERMINAL or receipt is None:
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.OPERATION_NOT_TERMINAL,
            requested_version=1,
        )
    if snapshot.revision != request.terminal_revision:
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
            requested_version=1,
        )
    if receipt.condition is not OperationTerminalCondition.SUCCEEDED:
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.OPERATION_NOT_SUCCESSFUL,
            requested_version=1,
        )
    return _RefreshContext(request=request, snapshot=snapshot, receipt=receipt)


def _lookup_refresh_registration(
    registry: OperationRegistry,
    context: _RefreshContext,
) -> _RefreshRegistration | OperationWorkspaceRefreshTargetRefusalV1:
    """Bind terminal facts to the exact refresh adapter and schema contract."""
    try:
        registration = registry.lookup_public_registration(context.snapshot.identity.definition_id)
    except Exception:
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.DEFINITION_CONTRACT_MISMATCH,
            requested_version=1,
        )
    contract = registration.contract
    if (
        context.snapshot.definition_contract_digest != contract.definition_contract_digest
        or context.request.definition_contract_digest != contract.definition_contract_digest
    ):
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.DEFINITION_CONTRACT_MISMATCH,
            requested_version=1,
        )
    adapter = registration.workspace_refresh_adapter
    if contract.workspace_refresh_target_schema is None or adapter is None:
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.REFRESH_ADAPTER_UNAVAILABLE,
            requested_version=1,
        )
    if context.request.target_schema != contract.workspace_refresh_target_schema:
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.REFRESH_SCHEMA_MISMATCH,
            requested_version=1,
        )
    return _RefreshRegistration(context=context, registration=registration, adapter=adapter)


async def _resolve_refresh_target[RefreshTargetT: BaseModel](
    registry: OperationRegistry,
    bound: _RefreshRegistration,
) -> OperationWorkspaceRefreshTargetResultV1[RefreshTargetT]:
    """Resolve, adapt, and strictly validate one registered refresh target."""
    try:
        binding = registry.lookup_public_schema_binding(bound.context.request.target_schema)
        target = bound.adapter(bound.context.receipt)
        if type(target) is not binding.model_type:
            raise TypeError("Workspace refresh adapter returned an unregistered model")
        validated = binding.model_type.model_validate(target.model_dump(mode="python"))
        return OperationWorkspaceRefreshTargetSuccessV1[RefreshTargetT](
            target_schema=binding.identity,
            definition_contract_digest=bound.registration.contract.definition_contract_digest,
            target=cast(RefreshTargetT, validated),
        )
    except Exception:
        return _refresh_refusal(
            OperationWorkspaceRefreshTargetRefusalCode.UNSAFE_REFRESH_TARGET,
            requested_version=1,
        )


@dataclass(frozen=True, slots=True)
class _ResultContext:
    """Durable terminal facts that passed the settled-result checks."""

    request: OperationResultProjectionRequestV1
    snapshot: OperationPersistedSnapshot
    receipt: OperationTerminalReceipt
    result_ref: OperationReference


@dataclass(frozen=True, slots=True)
class _ResultRegistration:
    """One settled-result context bound to its projector and public contract."""

    context: _ResultContext
    registration: OperationPublicDefinitionRegistrationV1
    projector: OperationResultProjector


def _result_request_or_refusal(
    request: OperationResultProjectionVersionHeader | OperationResultProjectionRequestV1,
) -> OperationResultProjectionRequestV1 | OperationResultProjectionRefusalV1:
    """Validate the result-projection request envelope before reading state."""
    if request.result_projection_version != _SUPPORTED_VERSION:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.UNSUPPORTED_VERSION,
            requested_version=request.result_projection_version,
        )
    if not isinstance(request, OperationResultProjectionRequestV1):
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
            requested_version=1,
        )
    return request


async def _load_result_context(
    reader: OperationObservationReader,
    request: OperationResultProjectionRequestV1,
) -> _ResultContext | OperationResultProjectionRefusalV1:
    """Read and validate the exact terminal snapshot named by the request."""
    snapshot = await _read_snapshot(reader, request.operation_id)
    if snapshot is None:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.UNKNOWN_OPERATION,
            requested_version=1,
        )
    if not _is_persisted_snapshot(snapshot):
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
            requested_version=1,
        )
    receipt = snapshot.terminal_receipt
    if snapshot.lifecycle is not OperationLifecycle.TERMINAL or receipt is None:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.OPERATION_NOT_TERMINAL,
            requested_version=1,
        )
    if snapshot.revision != request.terminal_revision:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.STALE_OPERATION_REVISION,
            requested_version=1,
        )
    # A settled result is resolvable whenever the receipt carries one, not only
    # on SUCCEEDED: a FAILED settlement may still carry committed evidence.
    result_ref = receipt.result_ref
    if result_ref is None:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.OPERATION_NOT_SUCCESSFUL,
            requested_version=1,
        )
    return _ResultContext(request=request, snapshot=snapshot, receipt=receipt, result_ref=result_ref)


def _lookup_result_registration(
    registry: OperationRegistry,
    context: _ResultContext,
) -> _ResultRegistration | OperationResultProjectionRefusalV1:
    """Bind terminal facts to the exact projector and public schema contract."""
    try:
        registration = registry.lookup_public_registration(context.snapshot.identity.definition_id)
    except Exception:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
            requested_version=1,
        )
    contract = registration.contract
    if (
        context.snapshot.definition_contract_digest != contract.definition_contract_digest
        or context.request.definition_contract_digest != contract.definition_contract_digest
    ):
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.DEFINITION_CONTRACT_MISMATCH,
            requested_version=1,
        )
    projector = registration.result_projector
    if contract.result_schema is None or projector is None:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
            requested_version=1,
        )
    if context.request.result_schema != contract.result_schema:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.RESULT_SCHEMA_MISMATCH,
            requested_version=1,
        )
    return _ResultRegistration(context=context, registration=registration, projector=projector)


def _result_digest_or_refusal(
    context: _ResultContext,
) -> ContentDigest | OperationResultProjectionRefusalV1:
    """Validate the persisted result reference as the canonical digest type."""
    try:
        return _CONTENT_DIGEST_ADAPTER.validate_python(context.result_ref)
    except ValidationError:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
            requested_version=1,
        )


async def _resolve_result_projection[ResultProjectionT: BaseModel](
    registry: OperationRegistry,
    operands: OperationSecureReferenceStore,
    bound: _ResultRegistration,
    digest: ContentDigest,
) -> OperationResultProjectionResultV1[ResultProjectionT]:
    """Resolve, project, and strictly validate one registered result model."""
    try:
        binding = registry.lookup_public_schema_binding(bound.context.request.result_schema)
        definition = registry.lookup(bound.context.snapshot.identity.definition_id)
        if definition.result_type is None:
            raise TypeError("result-less operation definition cannot resolve a settled result")
        resolved = await operands.resolve(digest, definition.result_type)
        projected = bound.projector(resolved, bound.context.receipt)
        del resolved
        if type(projected) is not binding.model_type:
            raise TypeError("result projector returned an unregistered model")
        validated = binding.model_type.model_validate(projected.model_dump(mode="python"))
        return OperationResultProjectionSuccessV1[ResultProjectionT](
            result_schema=binding.identity,
            definition_contract_digest=bound.registration.contract.definition_contract_digest,
            projection=cast(ResultProjectionT, validated),
        )
    except Exception:
        return _result_projection_refusal(
            OperationResultProjectionRefusalCode.RESULT_PROJECTION_UNAVAILABLE,
            requested_version=1,
        )


def _review_refusal(
    code: OperationReviewProjectionRefusalCode,
    *,
    requested_version: int | None,
) -> OperationReviewProjectionRefusalV1:
    return OperationReviewProjectionRefusalV1(code=code, requested_version=requested_version, diagnostic_ref=None)


def _refresh_refusal(
    code: OperationWorkspaceRefreshTargetRefusalCode,
    *,
    requested_version: int | None,
) -> OperationWorkspaceRefreshTargetRefusalV1:
    return OperationWorkspaceRefreshTargetRefusalV1(code=code, requested_version=requested_version, diagnostic_ref=None)


def _result_projection_refusal(
    code: OperationResultProjectionRefusalCode,
    *,
    requested_version: int | None,
) -> OperationResultProjectionRefusalV1:
    return OperationResultProjectionRefusalV1(code=code, requested_version=requested_version, diagnostic_ref=None)


load_refresh_context = _load_refresh_context
load_result_context = _load_result_context
load_review_context = _load_review_context
lookup_refresh_registration = _lookup_refresh_registration
lookup_result_registration = _lookup_result_registration
lookup_review_registration = _lookup_review_registration
refresh_request_or_refusal = _refresh_request_or_refusal
resolve_refresh_target = _resolve_refresh_target
resolve_result_projection = _resolve_result_projection
resolve_review_projection = _resolve_review_projection
result_digest_or_refusal = _result_digest_or_refusal
result_request_or_refusal = _result_request_or_refusal
review_request_or_refusal = _review_request_or_refusal
