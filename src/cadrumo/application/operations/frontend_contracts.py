"""Validation helpers and local result aliases for public operation contracts."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from ...core.operations import (
    LIFECYCLES_BEFORE_ANY_CANCELLATION_REQUEST,
    OperationCancellation,
    OperationLifecycle,
    OperationTerminalCondition,
)
from .frontend_projection import OperationPublicProjectionV1
from .frontend_requests import (
    OperationCancellationRefusalV1,
    OperationCancellationSuccessV1,
    OperationDetachRefusalV1,
    OperationDetachSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRefusalV1,
    OperationResponseControlSuccessV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationResultProjectionRefusalV1,
    OperationResultProjectionSuccessV1,
    OperationReviewProjectionRefusalV1,
    OperationReviewProjectionSuccessV1,
    OperationWorkspaceRefreshTargetRefusalV1,
    OperationWorkspaceRefreshTargetSuccessV1,
)


def validate_projection_contract(projection: OperationPublicProjectionV1) -> None:
    """Refuse a projection whose embedded public contract does not identify it."""
    contract = projection.definition_contract
    if contract.definition_id != projection.definition_id:
        raise ValueError("public projection definition does not match its contract")
    if projection.close_policy is not contract.close_policy:
        raise ValueError("public projection close policy does not match its definition contract")
    if projection.cancellation is not contract.cancellation:
        raise ValueError("public projection cancellation does not match its definition contract")


def validate_projection_settlement(projection: OperationPublicProjectionV1) -> None:
    """Validate the mutually consistent terminal settlement references."""
    _validate_projection_settlement_references(projection)
    _validate_projection_failure(projection)
    _validate_projection_nonterminal_settlement(projection)


def _validate_projection_settlement_references(projection: OperationPublicProjectionV1) -> None:
    references = (projection.result_ref, projection.refusal_ref)
    if all(value is not None for value in references):
        raise ValueError("public projection cannot expose result and refusal references together")
    if projection.terminal_condition is OperationTerminalCondition.SUCCEEDED and projection.result_ref is None:
        raise ValueError("successful public projection requires a result reference")
    if projection.terminal_condition is OperationTerminalCondition.REFUSED and projection.refusal_ref is None:
        raise ValueError("refused public projection requires a refusal reference")


def _validate_projection_failure(projection: OperationPublicProjectionV1) -> None:
    if (
        projection.terminal_condition is not OperationTerminalCondition.FAILED
        and projection.failure_error_code is not None
    ):
        raise ValueError("public failure error code requires a failed terminal condition")
    if projection.failure_error_code is not None:
        from ...core.errors.error_codes import get_registered_error_code_by_code

        get_registered_error_code_by_code(projection.failure_error_code)


def _validate_projection_nonterminal_settlement(projection: OperationPublicProjectionV1) -> None:
    references = (projection.result_ref, projection.refusal_ref)
    if projection.lifecycle is not OperationLifecycle.TERMINAL and (
        any(value is not None for value in references) or projection.failure_error_code is not None
    ):
        raise ValueError("nonterminal public projection cannot expose settlement references")


def validate_projection_cancellation_facts(projection: OperationPublicProjectionV1) -> None:
    """Validate cancellation facts against the projection lifecycle."""
    _validate_unsupported_cancellation_facts(projection)
    _validate_cancellation_request_fact(projection)
    _validate_cancellation_lifecycle(projection)
    _validate_cancellation_acknowledgement(projection)
    _validate_cancelled_terminal_fact(projection)


def _validate_unsupported_cancellation_facts(projection: OperationPublicProjectionV1) -> None:
    if projection.cancellation is OperationCancellation.UNSUPPORTED and (
        projection.cancellation_requested or projection.cancellation_acknowledged
    ):
        raise ValueError("unsupported cancellation cannot carry request or acknowledgement facts")


def _validate_cancellation_request_fact(projection: OperationPublicProjectionV1) -> None:
    if projection.cancellation_requested != (projection.cleanup_deadline_at is not None):
        raise ValueError("public cleanup deadline and cancellation request must be declared together")


def _validate_cancellation_lifecycle(projection: OperationPublicProjectionV1) -> None:
    if projection.lifecycle is OperationLifecycle.CANCELLATION_REQUESTED and not projection.cancellation_requested:
        raise ValueError("cancellation-requested lifecycle requires its declared request fact")
    if projection.cancellation_requested and projection.lifecycle in LIFECYCLES_BEFORE_ANY_CANCELLATION_REQUEST:
        raise ValueError("public cancellation request disagrees with the current lifecycle")


def _validate_cancellation_acknowledgement(projection: OperationPublicProjectionV1) -> None:
    if projection.cancellation_acknowledged and not projection.cancellation_requested:
        raise ValueError("cancellation acknowledgement requires a cancellation request")
    if projection.cancellation_acknowledged and projection.lifecycle not in {
        OperationLifecycle.SETTLING,
        OperationLifecycle.TERMINAL,
    }:
        raise ValueError("cancellation acknowledgement requires settling or terminal lifecycle")


def _validate_cancelled_terminal_fact(projection: OperationPublicProjectionV1) -> None:
    if (
        projection.terminal_condition is OperationTerminalCondition.CANCELLED
        and not projection.cancellation_acknowledged
        and not projection.financial_operand_cancelled_before_delivery
    ):
        raise ValueError("cancelled public operation requires cancellation acknowledgement")


type OperationReviewProjectionResultV1[ReviewProjectionT: BaseModel] = Annotated[
    OperationReviewProjectionSuccessV1[ReviewProjectionT] | OperationReviewProjectionRefusalV1,
    Field(discriminator="outcome"),
]


type OperationResponseControlResultV1 = Annotated[
    OperationResponseControlSuccessV1 | OperationResponseControlRefusalV1,
    Field(discriminator="outcome"),
]


type OperationResponseMutationRequestV1 = Annotated[
    OperationResponseApplyRequestV1 | OperationResponseRejectRequestV1,
    Field(discriminator="response_action"),
]


type OperationResponseMutationResultV1 = Annotated[
    OperationResponseMutationSuccessV1 | OperationResponseControlRefusalV1,
    Field(discriminator="outcome"),
]


type OperationCancellationResultV1 = Annotated[
    OperationCancellationSuccessV1 | OperationCancellationRefusalV1,
    Field(discriminator="outcome"),
]


type OperationDetachResultV1 = Annotated[
    OperationDetachSuccessV1 | OperationDetachRefusalV1,
    Field(discriminator="outcome"),
]


type OperationWorkspaceRefreshTargetResultV1[RefreshTargetT: BaseModel] = Annotated[
    OperationWorkspaceRefreshTargetSuccessV1[RefreshTargetT] | OperationWorkspaceRefreshTargetRefusalV1,
    Field(discriminator="outcome"),
]


type OperationResultProjectionResultV1[ResultProjectionT: BaseModel] = Annotated[
    OperationResultProjectionSuccessV1[ResultProjectionT] | OperationResultProjectionRefusalV1,
    Field(discriminator="outcome"),
]


__all__ = [
    "OperationCancellationResultV1",
    "OperationDetachResultV1",
    "OperationResponseControlResultV1",
    "OperationResponseMutationRequestV1",
    "OperationResponseMutationResultV1",
    "OperationResultProjectionResultV1",
    "OperationReviewProjectionResultV1",
    "OperationWorkspaceRefreshTargetResultV1",
    "validate_projection_cancellation_facts",
    "validate_projection_contract",
    "validate_projection_settlement",
]
