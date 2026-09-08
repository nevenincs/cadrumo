"""Public frontend driver for the canonical reviewed censal operation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from ..application.operations.composition import OperationComposedServices, OperationSubmission
from ..application.operations.frontend_contracts import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionResultV1,
    OperationReviewProjectionSuccessV1,
)
from ..application.operations.models import OperationRequest
from ..application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CensalOperationOutcome,
    CensalOperationRequest,
    CensalOperationResult,
    CensalReviewProjectionV1,
    build_censal_operation_request,
)
from ..application.user_profile.profile_record_repository import ProfileRecordRepository
from ..core.bucket_pointer import require_active_bucket_id
from ..core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ..core.time.clock import now
from .operation_composition import compose_operation_dependencies

_OBSERVATION_LIMIT = 256
_SETTLEMENT_POLLS = 500


@dataclass(frozen=True, slots=True)
class CensalReviewedFrontendResult:
    """Safe terminal result retained by a frontend after exact review."""

    operation_id: str
    applied: bool
    projection: CensalReviewProjectionV1


async def _observe(services: OperationComposedServices, operation_id: str) -> OperationObservationSuccessV1:
    observed = await services.observation.observe(
        OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=_OBSERVATION_LIMIT)
    )
    if not isinstance(observed, OperationObservationSuccessV1):
        raise RuntimeError("censal operation observation was refused")
    return observed


def _active_censal_operation_request() -> OperationRequest[CensalOperationRequest]:
    """Build the registered request from the one authenticated profile record."""
    profile_id = require_active_bucket_id()
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    payload = build_censal_operation_request(record)
    return OperationRequest(
        definition_id=CENSAL_OPERATION_DEFINITION_ID,
        subject_ref=profile_id,
        payload=payload,
    )


def _require_review_interaction(observed: OperationObservationSuccessV1) -> OperationReviewAvailableInteractionV1:
    """Require the operation to expose the reviewed interaction it promised."""
    pending = observed.projection.pending_interaction
    if not isinstance(pending, OperationReviewAvailableInteractionV1):
        raise RuntimeError("censal operation did not publish its reviewed proposal")
    return pending


async def _resolve_censal_projection(
    services: OperationComposedServices,
    pending: OperationReviewAvailableInteractionV1,
) -> CensalReviewProjectionV1:
    """Resolve and type-check the safe projection shown to the reviewer."""
    projected: OperationReviewProjectionResultV1[CensalReviewProjectionV1] = await services.review.resolve(
        OperationReviewProjectionRequestV1(reference=pending.review_reference)
    )
    if not isinstance(projected, OperationReviewProjectionSuccessV1) or not isinstance(
        projected.projection, CensalReviewProjectionV1
    ):
        raise RuntimeError("censal reviewed projection was unavailable")
    return projected.projection


async def _answer_censal_review(
    services: OperationComposedServices,
    submission: OperationSubmission,
    pending: OperationReviewAvailableInteractionV1,
    *,
    actor_ref: str,
    apply: bool,
) -> None:
    """Submit exactly one operator answer through the held response authority."""
    operation_id = submission.receipt.operation_id
    control = await services.response(
        OperationResponseControlRequestV1(
            operation_id=operation_id,
            interaction_id=pending.interaction_id,
            revision=pending.revision,
            actor_ref=actor_ref,
        ),
        submission.response_capability,
    )
    if apply:
        accepted = await control.apply(
            OperationResponseApplyRequestV1(
                operation_id=operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=actor_ref,
                responded_at=now(),
            )
        )
    else:
        accepted = await control.reject(
            OperationResponseRejectRequestV1(
                operation_id=operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=actor_ref,
                responded_at=now(),
                reason_code="censo.review.operator-rejected",
            )
        )
    if not isinstance(accepted, OperationResponseMutationSuccessV1):
        raise RuntimeError("censal reviewed response was refused")


def _parse_censal_result_reference(
    result_ref: str,
    *,
    expected_outcome: CensalOperationOutcome,
) -> CensalOperationResult:
    """Validate and type the backend result reference after settlement."""
    prefix, separator, outcome = result_ref.rpartition(":")
    family, digest_separator, reviewed_digest = prefix.partition(":")
    if not separator or not digest_separator or family != "censo-review":
        raise RuntimeError("censal reviewed operation returned an invalid result reference")
    typed_result = CensalOperationResult(
        outcome=CensalOperationOutcome(outcome),
        reviewed_proposal_digest=reviewed_digest,
    )
    if typed_result.outcome is not expected_outcome:
        raise RuntimeError("censal reviewed operation returned a mismatched outcome")
    return typed_result


def _assert_censal_terminal_success(
    observed: OperationObservationSuccessV1,
    *,
    apply: bool,
) -> None:
    """Require a successful terminal projection with the declared effect."""
    expected_outcome = CensalOperationOutcome.APPLIED if apply else CensalOperationOutcome.REJECTED
    expected_effect = OperationEffect.UPDATED if apply else OperationEffect.NONE
    projection = observed.projection
    result_ref = projection.result_ref
    if (
        projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        or projection.effect is not expected_effect
        or result_ref is None
    ):
        raise RuntimeError("censal reviewed operation did not succeed with its declared effect")
    _parse_censal_result_reference(result_ref, expected_outcome=expected_outcome)


async def _await_censal_settlement(
    services: OperationComposedServices,
    operation_id: str,
    *,
    apply: bool,
) -> None:
    """Poll the bounded public observation surface until the operation settles."""
    for _ in range(_SETTLEMENT_POLLS):
        observed = await _observe(services, operation_id)
        if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
            _assert_censal_terminal_success(observed, apply=apply)
            return
        await asyncio.sleep(0)
    raise RuntimeError("censal reviewed operation did not settle")


async def _run(
    *,
    actor_ref: str,
    decide: Callable[[CensalReviewProjectionV1], bool],
    services: OperationComposedServices | None = None,
) -> CensalReviewedFrontendResult:
    request = _active_censal_operation_request()
    composed = services or compose_operation_dependencies()
    owns_services = services is None
    try:
        submitted = await composed.submission.submit(
            request,
            actor_ref=actor_ref,
        )
        operation_id = submitted.receipt.operation_id
        await composed.submission.start(operation_id)
        waiting = await _observe(composed, operation_id)
        pending = _require_review_interaction(waiting)
        projection = await _resolve_censal_projection(composed, pending)
        apply = decide(projection)
        await _answer_censal_review(composed, submitted, pending, actor_ref=actor_ref, apply=apply)
        await _await_censal_settlement(composed, operation_id, apply=apply)
        return CensalReviewedFrontendResult(operation_id=operation_id, applied=apply, projection=projection)
    finally:
        if owns_services:
            await composed.shutdown()


def run_censal_review(
    *,
    actor_ref: str,
    decide: Callable[[CensalReviewProjectionV1], bool],
) -> CensalReviewedFrontendResult:
    """Acquire once, show the exact safe projection, and answer its review."""
    return asyncio.run(_run(actor_ref=actor_ref, decide=decide))


__all__ = ["CensalReviewedFrontendResult", "run_censal_review"]
