"""Registry definitions and admission for the review read operations."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from ..ledger.read_access import resolve_ledger_request_read_access
from ..operations.capabilities import RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES
from ..operations.models import OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationPublicDefinitionRegistrationV1
from .read_contracts import (
    REVIEW_QUEUE_OPERATION_DEFINITION_ID,
    REVIEW_VIEW_OPERATION_DEFINITION_ID,
    ReviewQueueReadRequest,
    ReviewReadOperationPorts,
    ReviewViewReadRequest,
)
from .read_operation import ReviewQueueReadExecutor, ReviewViewReadExecutor
from .read_projections import (
    ReviewQueueReadExecutionResult,
    ReviewQueueReadProjection,
    ReviewViewReadExecutionResult,
    ReviewViewReadProjection,
    project_queue_read_result,
    project_view_read_result,
)


def _build_definition(
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    build: Callable[[], object],
) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_type=executor_type,
        build=build,
        capabilities=RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_review_read_definitions(ports: ReviewReadOperationPorts) -> tuple[OperationDefinition, ...]:
    """Build the exact queue and item-view definitions over shared read ports."""
    return (
        _build_definition(
            definition_id=REVIEW_QUEUE_OPERATION_DEFINITION_ID,
            request_type=ReviewQueueReadRequest,
            result_type=ReviewQueueReadExecutionResult,
            executor_type=ReviewQueueReadExecutor,
            build=lambda: ReviewQueueReadExecutor(ports),
        ),
        _build_definition(
            definition_id=REVIEW_VIEW_OPERATION_DEFINITION_ID,
            request_type=ReviewViewReadRequest,
            result_type=ReviewViewReadExecutionResult,
            executor_type=ReviewViewReadExecutor,
            build=lambda: ReviewViewReadExecutor(ports),
        ),
    )


def _registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    projector: Callable[[BaseModel, OperationTerminalReceipt], BaseModel],
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=result_type,
        result_projector=projector,
        access_resolver=lambda request, context: resolve_ledger_request_read_access(
            request,
            context,
            definition_id=definition.definition_id,
            request_type=request_type,
        ),
    )


def build_review_read_registrations(
    definitions: tuple[OperationDefinition, ...],
) -> tuple[OperationPublicDefinitionRegistrationV1, ...]:
    """Bind both exact-profile requests to independent closed projections."""
    by_id = {definition.definition_id: definition for definition in definitions}
    expected = {REVIEW_QUEUE_OPERATION_DEFINITION_ID, REVIEW_VIEW_OPERATION_DEFINITION_ID}
    if len(by_id) != len(definitions) or set(by_id) != expected:
        raise ValueError("review registration requires the exact queue and view definitions")
    return (
        _registration(
            by_id[REVIEW_QUEUE_OPERATION_DEFINITION_ID],
            request_type=ReviewQueueReadRequest,
            result_type=ReviewQueueReadProjection,
            projector=project_queue_read_result,
        ),
        _registration(
            by_id[REVIEW_VIEW_OPERATION_DEFINITION_ID],
            request_type=ReviewViewReadRequest,
            result_type=ReviewViewReadProjection,
            projector=project_view_read_result,
        ),
    )


__all__ = ["build_review_read_definitions", "build_review_read_registrations"]
