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
from .frontend_projection import (
    OperationNoPendingInteractionV1 as _OperationNoPendingInteractionV1,
)
from .frontend_projection import (
    OperationPublicProjectionV1 as _OperationPublicProjectionV1,
)
from .frontend_projection import (
    OperationReviewAvailableInteractionV1 as _OperationReviewAvailableInteractionV1,
)
from .frontend_projection import (
    OperationUnsupportedInteractionV1 as _OperationUnsupportedInteractionV1,
)
from .frontend_requests import (
    OperationCancellationRefusalV1 as _OperationCancellationRefusalV1,
)
from .frontend_requests import (
    OperationCancellationSuccessV1 as _OperationCancellationSuccessV1,
)
from .frontend_requests import (
    OperationDetachRefusalV1 as _OperationDetachRefusalV1,
)
from .frontend_requests import (
    OperationDetachSuccessV1 as _OperationDetachSuccessV1,
)
from .frontend_requests import (
    OperationObservationRefusalV1 as _OperationObservationRefusalV1,
)
from .frontend_requests import (
    OperationObservationSuccessV1 as _OperationObservationSuccessV1,
)
from .frontend_requests import (
    OperationPublicDiagnosticEventV1 as _OperationPublicDiagnosticEventV1,
)
from .frontend_requests import (
    OperationPublicEffectEventV1 as _OperationPublicEffectEventV1,
)
from .frontend_requests import (
    OperationPublicInteractionEventV1 as _OperationPublicInteractionEventV1,
)
from .frontend_requests import (
    OperationPublicLogEventV1 as _OperationPublicLogEventV1,
)
from .frontend_requests import (
    OperationPublicNoticeEventV1 as _OperationPublicNoticeEventV1,
)
from .frontend_requests import (
    OperationPublicPhaseEventV1 as _OperationPublicPhaseEventV1,
)
from .frontend_requests import (
    OperationPublicProgressEventV1 as _OperationPublicProgressEventV1,
)
from .frontend_requests import (
    OperationPublicReconciliationEventV1 as _OperationPublicReconciliationEventV1,
)
from .frontend_requests import (
    OperationPublicTerminalEventV1 as _OperationPublicTerminalEventV1,
)
from .frontend_requests import (
    OperationResponseApplyRequestV1 as _OperationResponseApplyRequestV1,
)
from .frontend_requests import (
    OperationResponseControlRefusalV1 as _OperationResponseControlRefusalV1,
)
from .frontend_requests import (
    OperationResponseControlSuccessV1 as _OperationResponseControlSuccessV1,
)
from .frontend_requests import (
    OperationResponseMutationSuccessV1 as _OperationResponseMutationSuccessV1,
)
from .frontend_requests import (
    OperationResponseRejectRequestV1 as _OperationResponseRejectRequestV1,
)
from .frontend_requests import (
    OperationResultProjectionRefusalV1 as _OperationResultProjectionRefusalV1,
)
from .frontend_requests import (
    OperationResultProjectionSuccessV1 as _OperationResultProjectionSuccessV1,
)
from .frontend_requests import (
    OperationReviewProjectionRefusalV1 as _OperationReviewProjectionRefusalV1,
)
from .frontend_requests import (
    OperationReviewProjectionSuccessV1 as _OperationReviewProjectionSuccessV1,
)
from .frontend_requests import (
    OperationWorkspaceRefreshTargetRefusalV1 as _OperationWorkspaceRefreshTargetRefusalV1,
)
from .frontend_requests import (
    OperationWorkspaceRefreshTargetSuccessV1 as _OperationWorkspaceRefreshTargetSuccessV1,
)


def validate_projection_contract(projection: _OperationPublicProjectionV1) -> None:
    contract = projection.definition_contract
    if contract.definition_id != projection.definition_id:
        raise ValueError("public projection definition does not match its contract")
    if projection.close_policy is not contract.close_policy:
        raise ValueError("public projection close policy does not match its definition contract")
    if projection.cancellation is not contract.cancellation:
        raise ValueError("public projection cancellation does not match its definition contract")


def validate_projection_settlement(projection: _OperationPublicProjectionV1) -> None:
    _validate_projection_settlement_references(projection)
    _validate_projection_failure(projection)
    _validate_projection_nonterminal_settlement(projection)


def _validate_projection_settlement_references(projection: _OperationPublicProjectionV1) -> None:
    references = (projection.result_ref, projection.refusal_ref)
    if all(value is not None for value in references):
        raise ValueError("public projection cannot expose result and refusal references together")
    if projection.terminal_condition is OperationTerminalCondition.SUCCEEDED and projection.result_ref is None:
        raise ValueError("successful public projection requires a result reference")
    if projection.terminal_condition is OperationTerminalCondition.REFUSED and projection.refusal_ref is None:
        raise ValueError("refused public projection requires a refusal reference")


def _validate_projection_failure(projection: _OperationPublicProjectionV1) -> None:
    if (
        projection.terminal_condition is not OperationTerminalCondition.FAILED
        and projection.failure_error_code is not None
    ):
        raise ValueError("public failure error code requires a failed terminal condition")
    if projection.failure_error_code is not None:
        from ...core.errors.error_codes import get_registered_error_code_by_code

        get_registered_error_code_by_code(projection.failure_error_code)


def _validate_projection_nonterminal_settlement(projection: _OperationPublicProjectionV1) -> None:
    references = (projection.result_ref, projection.refusal_ref)
    if projection.lifecycle is not OperationLifecycle.TERMINAL and (
        any(value is not None for value in references) or projection.failure_error_code is not None
    ):
        raise ValueError("nonterminal public projection cannot expose settlement references")


def validate_projection_cancellation_facts(projection: _OperationPublicProjectionV1) -> None:
    _validate_unsupported_cancellation_facts(projection)
    _validate_cancellation_request_fact(projection)
    _validate_cancellation_lifecycle(projection)
    _validate_cancellation_acknowledgement(projection)
    _validate_cancelled_terminal_fact(projection)


def _validate_unsupported_cancellation_facts(projection: _OperationPublicProjectionV1) -> None:
    if projection.cancellation is OperationCancellation.UNSUPPORTED and (
        projection.cancellation_requested or projection.cancellation_acknowledged
    ):
        raise ValueError("unsupported cancellation cannot carry request or acknowledgement facts")


def _validate_cancellation_request_fact(projection: _OperationPublicProjectionV1) -> None:
    if projection.cancellation_requested != (projection.cleanup_deadline_at is not None):
        raise ValueError("public cleanup deadline and cancellation request must be declared together")


def _validate_cancellation_lifecycle(projection: _OperationPublicProjectionV1) -> None:
    if projection.lifecycle is OperationLifecycle.CANCELLATION_REQUESTED and not projection.cancellation_requested:
        raise ValueError("cancellation-requested lifecycle requires its declared request fact")
    if projection.cancellation_requested and projection.lifecycle in LIFECYCLES_BEFORE_ANY_CANCELLATION_REQUEST:
        raise ValueError("public cancellation request disagrees with the current lifecycle")


def _validate_cancellation_acknowledgement(projection: _OperationPublicProjectionV1) -> None:
    if projection.cancellation_acknowledged and not projection.cancellation_requested:
        raise ValueError("cancellation acknowledgement requires a cancellation request")
    if projection.cancellation_acknowledged and projection.lifecycle not in {
        OperationLifecycle.SETTLING,
        OperationLifecycle.TERMINAL,
    }:
        raise ValueError("cancellation acknowledgement requires settling or terminal lifecycle")


def _validate_cancelled_terminal_fact(projection: _OperationPublicProjectionV1) -> None:
    if (
        projection.terminal_condition is OperationTerminalCondition.CANCELLED
        and not projection.cancellation_acknowledged
    ):
        raise ValueError("cancelled public operation requires cancellation acknowledgement")


type OperationPublicPendingInteractionV1 = Annotated[
    _OperationNoPendingInteractionV1 | _OperationReviewAvailableInteractionV1 | _OperationUnsupportedInteractionV1,
    Field(discriminator="disposition"),
]


type OperationPublicEventV1 = Annotated[
    _OperationPublicPhaseEventV1
    | _OperationPublicProgressEventV1
    | _OperationPublicLogEventV1
    | _OperationPublicEffectEventV1
    | _OperationPublicNoticeEventV1
    | _OperationPublicReconciliationEventV1
    | _OperationPublicDiagnosticEventV1
    | _OperationPublicInteractionEventV1
    | _OperationPublicTerminalEventV1,
    Field(discriminator="kind"),
]


type OperationObservationResultV1 = Annotated[
    _OperationObservationSuccessV1 | _OperationObservationRefusalV1,
    Field(discriminator="outcome"),
]


type OperationReviewProjectionResultV1[ReviewProjectionT: BaseModel] = Annotated[
    _OperationReviewProjectionSuccessV1[ReviewProjectionT] | _OperationReviewProjectionRefusalV1,
    Field(discriminator="outcome"),
]


type OperationResponseControlResultV1 = Annotated[
    _OperationResponseControlSuccessV1 | _OperationResponseControlRefusalV1,
    Field(discriminator="outcome"),
]


type OperationResponseMutationRequestV1 = Annotated[
    _OperationResponseApplyRequestV1 | _OperationResponseRejectRequestV1,
    Field(discriminator="response_action"),
]


type OperationResponseMutationResultV1 = Annotated[
    _OperationResponseMutationSuccessV1 | _OperationResponseControlRefusalV1,
    Field(discriminator="outcome"),
]


type OperationCancellationResultV1 = Annotated[
    _OperationCancellationSuccessV1 | _OperationCancellationRefusalV1,
    Field(discriminator="outcome"),
]


type OperationDetachResultV1 = Annotated[
    _OperationDetachSuccessV1 | _OperationDetachRefusalV1,
    Field(discriminator="outcome"),
]


type OperationWorkspaceRefreshTargetResultV1[RefreshTargetT: BaseModel] = Annotated[
    _OperationWorkspaceRefreshTargetSuccessV1[RefreshTargetT] | _OperationWorkspaceRefreshTargetRefusalV1,
    Field(discriminator="outcome"),
]


type OperationResultProjectionResultV1[ResultProjectionT: BaseModel] = Annotated[
    _OperationResultProjectionSuccessV1[ResultProjectionT] | _OperationResultProjectionRefusalV1,
    Field(discriminator="outcome"),
]


__all__ = [
    "OperationCancellationResultV1",
    "OperationDetachResultV1",
    "OperationObservationResultV1",
    "OperationPublicEventV1",
    "OperationPublicPendingInteractionV1",
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
