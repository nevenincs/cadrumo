"""Strict renderer-neutral DTOs for the public operation application boundary.

Definitions live in cohesive private modules while this module remains the
canonical public import surface and preserves historical class identities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field

from ...core.operations import (
    LIFECYCLES_BEFORE_ANY_CANCELLATION_REQUEST,
    OperationCancellation,
    OperationLifecycle,
    OperationTerminalCondition,
)

if TYPE_CHECKING:
    from ._frontend_projection import (
        OperationNoPendingInteractionV1,
        OperationPublicProgressV1,
        OperationPublicProjectionV1,
        OperationReviewAvailableInteractionV1,
        OperationReviewProjectionReferenceV1,
        OperationUnsupportedInteractionV1,
    )
    from ._frontend_requests import (
        OperationCancellationRefusalCode,
        OperationCancellationRefusalV1,
        OperationCancellationRequestV1,
        OperationCancellationSuccessV1,
        OperationCancellationVersionHeader,
        OperationDetachRefusalCode,
        OperationDetachRefusalV1,
        OperationDetachRequestV1,
        OperationDetachSuccessV1,
        OperationDetachVersionHeader,
        OperationObservationRefusalCode,
        OperationObservationRefusalV1,
        OperationObservationRequestV1,
        OperationObservationSuccessV1,
        OperationObservationVersionHeader,
        OperationPublicDiagnosticEventV1,
        OperationPublicEffectEventV1,
        OperationPublicEventPageV1,
        OperationPublicInteractionEventV1,
        OperationPublicLogEventV1,
        OperationPublicNoticeEventV1,
        OperationPublicPhaseEventV1,
        OperationPublicProgressEventV1,
        OperationPublicReconciliationEventV1,
        OperationPublicTerminalEventV1,
        OperationResponseApplyRequestV1,
        OperationResponseControlRefusalCode,
        OperationResponseControlRefusalV1,
        OperationResponseControlRequestV1,
        OperationResponseControlSuccessV1,
        OperationResponseControlVersionHeader,
        OperationResponseMutationSuccessV1,
        OperationResponseRejectRequestV1,
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
        OperationSubmissionReceiptV1,
        OperationWorkspaceRefreshTargetRefusalCode,
        OperationWorkspaceRefreshTargetRefusalV1,
        OperationWorkspaceRefreshTargetRequestV1,
        OperationWorkspaceRefreshTargetSuccessV1,
        OperationWorkspaceRefreshTargetVersionHeader,
    )


def validate_projection_contract(projection: OperationPublicProjectionV1) -> None:
    contract = projection.definition_contract
    if contract.definition_id != projection.definition_id:
        raise ValueError("public projection definition does not match its contract")
    if projection.close_policy is not contract.close_policy:
        raise ValueError("public projection close policy does not match its definition contract")
    if projection.cancellation is not contract.cancellation:
        raise ValueError("public projection cancellation does not match its definition contract")


def validate_projection_settlement(projection: OperationPublicProjectionV1) -> None:
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
    ):
        raise ValueError("cancelled public operation requires cancellation acknowledgement")


def _load_frontend_contracts() -> None:
    from . import _frontend_projection as _projection
    from . import _frontend_requests as _requests

    exports = {
        "OperationNoPendingInteractionV1": _projection.OperationNoPendingInteractionV1,
        "OperationPublicProgressV1": _projection.OperationPublicProgressV1,
        "OperationPublicProjectionV1": _projection.OperationPublicProjectionV1,
        "OperationReviewAvailableInteractionV1": _projection.OperationReviewAvailableInteractionV1,
        "OperationReviewProjectionReferenceV1": _projection.OperationReviewProjectionReferenceV1,
        "OperationUnsupportedInteractionV1": _projection.OperationUnsupportedInteractionV1,
        "OperationCancellationRefusalCode": _requests.OperationCancellationRefusalCode,
        "OperationCancellationRefusalV1": _requests.OperationCancellationRefusalV1,
        "OperationCancellationRequestV1": _requests.OperationCancellationRequestV1,
        "OperationCancellationSuccessV1": _requests.OperationCancellationSuccessV1,
        "OperationCancellationVersionHeader": _requests.OperationCancellationVersionHeader,
        "OperationDetachRefusalCode": _requests.OperationDetachRefusalCode,
        "OperationDetachRefusalV1": _requests.OperationDetachRefusalV1,
        "OperationDetachRequestV1": _requests.OperationDetachRequestV1,
        "OperationDetachSuccessV1": _requests.OperationDetachSuccessV1,
        "OperationDetachVersionHeader": _requests.OperationDetachVersionHeader,
        "OperationObservationRefusalCode": _requests.OperationObservationRefusalCode,
        "OperationObservationRefusalV1": _requests.OperationObservationRefusalV1,
        "OperationObservationRequestV1": _requests.OperationObservationRequestV1,
        "OperationObservationSuccessV1": _requests.OperationObservationSuccessV1,
        "OperationObservationVersionHeader": _requests.OperationObservationVersionHeader,
        "OperationPublicDiagnosticEventV1": _requests.OperationPublicDiagnosticEventV1,
        "OperationPublicEffectEventV1": _requests.OperationPublicEffectEventV1,
        "OperationPublicEventPageV1": _requests.OperationPublicEventPageV1,
        "OperationPublicInteractionEventV1": _requests.OperationPublicInteractionEventV1,
        "OperationPublicLogEventV1": _requests.OperationPublicLogEventV1,
        "OperationPublicNoticeEventV1": _requests.OperationPublicNoticeEventV1,
        "OperationPublicPhaseEventV1": _requests.OperationPublicPhaseEventV1,
        "OperationPublicProgressEventV1": _requests.OperationPublicProgressEventV1,
        "OperationPublicReconciliationEventV1": _requests.OperationPublicReconciliationEventV1,
        "OperationPublicTerminalEventV1": _requests.OperationPublicTerminalEventV1,
        "OperationResponseApplyRequestV1": _requests.OperationResponseApplyRequestV1,
        "OperationResponseControlRefusalCode": _requests.OperationResponseControlRefusalCode,
        "OperationResponseControlRefusalV1": _requests.OperationResponseControlRefusalV1,
        "OperationResponseControlRequestV1": _requests.OperationResponseControlRequestV1,
        "OperationResponseControlSuccessV1": _requests.OperationResponseControlSuccessV1,
        "OperationResponseControlVersionHeader": _requests.OperationResponseControlVersionHeader,
        "OperationResponseMutationSuccessV1": _requests.OperationResponseMutationSuccessV1,
        "OperationResponseRejectRequestV1": _requests.OperationResponseRejectRequestV1,
        "OperationResultProjectionRefusalCode": _requests.OperationResultProjectionRefusalCode,
        "OperationResultProjectionRefusalV1": _requests.OperationResultProjectionRefusalV1,
        "OperationResultProjectionRequestV1": _requests.OperationResultProjectionRequestV1,
        "OperationResultProjectionSuccessV1": _requests.OperationResultProjectionSuccessV1,
        "OperationResultProjectionVersionHeader": _requests.OperationResultProjectionVersionHeader,
        "OperationReviewProjectionRefusalCode": _requests.OperationReviewProjectionRefusalCode,
        "OperationReviewProjectionRefusalV1": _requests.OperationReviewProjectionRefusalV1,
        "OperationReviewProjectionRequestV1": _requests.OperationReviewProjectionRequestV1,
        "OperationReviewProjectionSuccessV1": _requests.OperationReviewProjectionSuccessV1,
        "OperationReviewProjectionVersionHeader": _requests.OperationReviewProjectionVersionHeader,
        "OperationSubmissionReceiptV1": _requests.OperationSubmissionReceiptV1,
        "OperationWorkspaceRefreshTargetRefusalCode": _requests.OperationWorkspaceRefreshTargetRefusalCode,
        "OperationWorkspaceRefreshTargetRefusalV1": _requests.OperationWorkspaceRefreshTargetRefusalV1,
        "OperationWorkspaceRefreshTargetRequestV1": _requests.OperationWorkspaceRefreshTargetRequestV1,
        "OperationWorkspaceRefreshTargetSuccessV1": _requests.OperationWorkspaceRefreshTargetSuccessV1,
        "OperationWorkspaceRefreshTargetVersionHeader": _requests.OperationWorkspaceRefreshTargetVersionHeader,
    }
    for value in exports.values():
        value.__module__ = __name__
    globals().update(exports)


_load_frontend_contracts()

type OperationPublicPendingInteractionV1 = Annotated[
    OperationNoPendingInteractionV1 | OperationReviewAvailableInteractionV1 | OperationUnsupportedInteractionV1,
    Field(discriminator="disposition"),
]


type OperationPublicEventV1 = Annotated[
    OperationPublicPhaseEventV1
    | OperationPublicProgressEventV1
    | OperationPublicLogEventV1
    | OperationPublicEffectEventV1
    | OperationPublicNoticeEventV1
    | OperationPublicReconciliationEventV1
    | OperationPublicDiagnosticEventV1
    | OperationPublicInteractionEventV1
    | OperationPublicTerminalEventV1,
    Field(discriminator="kind"),
]


type OperationObservationResultV1 = Annotated[
    OperationObservationSuccessV1 | OperationObservationRefusalV1,
    Field(discriminator="outcome"),
]


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
    "OperationCancellationRefusalCode",
    "OperationCancellationRefusalV1",
    "OperationCancellationRequestV1",
    "OperationCancellationResultV1",
    "OperationCancellationSuccessV1",
    "OperationCancellationVersionHeader",
    "OperationDetachRefusalCode",
    "OperationDetachRefusalV1",
    "OperationDetachRequestV1",
    "OperationDetachResultV1",
    "OperationDetachSuccessV1",
    "OperationDetachVersionHeader",
    "OperationNoPendingInteractionV1",
    "OperationObservationRefusalCode",
    "OperationObservationRefusalV1",
    "OperationObservationRequestV1",
    "OperationObservationResultV1",
    "OperationObservationSuccessV1",
    "OperationObservationVersionHeader",
    "OperationPublicDiagnosticEventV1",
    "OperationPublicEffectEventV1",
    "OperationPublicEventPageV1",
    "OperationPublicEventV1",
    "OperationPublicInteractionEventV1",
    "OperationPublicLogEventV1",
    "OperationPublicNoticeEventV1",
    "OperationPublicPendingInteractionV1",
    "OperationPublicPhaseEventV1",
    "OperationPublicProgressEventV1",
    "OperationPublicProgressV1",
    "OperationPublicProjectionV1",
    "OperationPublicReconciliationEventV1",
    "OperationPublicTerminalEventV1",
    "OperationResponseApplyRequestV1",
    "OperationResponseControlRefusalCode",
    "OperationResponseControlRefusalV1",
    "OperationResponseControlRequestV1",
    "OperationResponseControlResultV1",
    "OperationResponseControlSuccessV1",
    "OperationResponseControlVersionHeader",
    "OperationResponseMutationRequestV1",
    "OperationResponseMutationResultV1",
    "OperationResponseMutationSuccessV1",
    "OperationResponseRejectRequestV1",
    "OperationResultProjectionRefusalCode",
    "OperationResultProjectionRefusalV1",
    "OperationResultProjectionRequestV1",
    "OperationResultProjectionResultV1",
    "OperationResultProjectionSuccessV1",
    "OperationResultProjectionVersionHeader",
    "OperationReviewAvailableInteractionV1",
    "OperationReviewProjectionReferenceV1",
    "OperationReviewProjectionRefusalCode",
    "OperationReviewProjectionRefusalV1",
    "OperationReviewProjectionRequestV1",
    "OperationReviewProjectionResultV1",
    "OperationReviewProjectionSuccessV1",
    "OperationReviewProjectionVersionHeader",
    "OperationSubmissionReceiptV1",
    "OperationUnsupportedInteractionV1",
    "OperationWorkspaceRefreshTargetRefusalCode",
    "OperationWorkspaceRefreshTargetRefusalV1",
    "OperationWorkspaceRefreshTargetRequestV1",
    "OperationWorkspaceRefreshTargetResultV1",
    "OperationWorkspaceRefreshTargetSuccessV1",
    "OperationWorkspaceRefreshTargetVersionHeader",
]
