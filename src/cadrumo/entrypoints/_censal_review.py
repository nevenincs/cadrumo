"""Public frontend driver for the canonical reviewed censal operation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from ..application.operations.composition import OperationComposedServices
from ..application.operations.frontend_contracts import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResponseApplyRequestV1,
    OperationResponseControlRequestV1,
    OperationResponseMutationSuccessV1,
    OperationResponseRejectRequestV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionRequestV1,
    OperationReviewProjectionSuccessV1,
)
from ..application.operations.models import OperationRequest
from ..application.user_profile import (
    CENSAL_OPERATION_DEFINITION_ID,
    CensalOperationOutcome,
    CensalOperationResult,
    CensalReviewProjectionV1,
    ProfileRecordRepository,
    build_censal_operation_request,
)
from ..core.bucket_pointer import require_active_bucket_id
from ..core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ..core.time import now
from ._operation_composition import compose_operation_dependencies

_OBSERVATION_LIMIT = 256
_SETTLEMENT_POLLS = 500


@dataclass(frozen=True, slots=True)
class CensalReviewedFrontendResult:
    """Safe terminal result retained by a frontend after exact review."""

    operation_id: str
    applied: bool
    projection: CensalReviewProjectionV1


async def _observe(services, operation_id: str) -> OperationObservationSuccessV1:
    observed = await services.observation.observe(
        OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=_OBSERVATION_LIMIT)
    )
    if not isinstance(observed, OperationObservationSuccessV1):
        raise RuntimeError("censal operation observation was refused")
    return observed


async def _run(
    *,
    actor_ref: str,
    decide: Callable[[CensalReviewProjectionV1], bool],
    services: OperationComposedServices | None = None,
) -> CensalReviewedFrontendResult:
    profile_id = require_active_bucket_id()
    record = ProfileRecordRepository.for_current_session(profile_id).load(profile_id)
    payload = build_censal_operation_request(record)
    composed = services or compose_operation_dependencies()
    owns_services = services is None
    try:
        submitted = await composed.submission.submit(
            OperationRequest(
                definition_id=CENSAL_OPERATION_DEFINITION_ID,
                subject_ref=profile_id,
                payload=payload,
            ),
            actor_ref=actor_ref,
        )
        operation_id = submitted.receipt.operation_id
        await composed.submission.start(operation_id)
        waiting = await _observe(composed, operation_id)
        pending = waiting.projection.pending_interaction
        if not isinstance(pending, OperationReviewAvailableInteractionV1):
            raise RuntimeError("censal operation did not publish its reviewed proposal")
        projected = await composed.review.resolve(
            OperationReviewProjectionRequestV1(reference=pending.review_reference)
        )
        if not isinstance(projected, OperationReviewProjectionSuccessV1) or not isinstance(
            projected.projection, CensalReviewProjectionV1
        ):
            raise RuntimeError("censal reviewed projection was unavailable")
        apply = decide(projected.projection)
        control = await composed.response(
            OperationResponseControlRequestV1(
                operation_id=operation_id,
                interaction_id=pending.interaction_id,
                revision=pending.revision,
                actor_ref=actor_ref,
            ),
            submitted.response_capability,
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
        for _ in range(_SETTLEMENT_POLLS):
            terminal = await _observe(composed, operation_id)
            if terminal.projection.lifecycle is OperationLifecycle.TERMINAL:
                expected_outcome = CensalOperationOutcome.APPLIED if apply else CensalOperationOutcome.REJECTED
                expected_effect = OperationEffect.UPDATED if apply else OperationEffect.NONE
                result_ref = terminal.projection.result_ref
                if (
                    terminal.projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
                    or terminal.projection.effect is not expected_effect
                    or result_ref is None
                ):
                    raise RuntimeError("censal reviewed operation did not succeed with its declared effect")
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
                return CensalReviewedFrontendResult(
                    operation_id=operation_id,
                    applied=apply,
                    projection=projected.projection,
                )
            await asyncio.sleep(0)
        raise RuntimeError("censal reviewed operation did not settle")
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
