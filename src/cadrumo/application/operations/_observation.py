"""Canonical public projection of one atomically read operation observation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from ...core import OperationCancellation, OperationInteractionKind, OperationLifecycle
from ._events import (
    OperationDiagnosticEvent,
    OperationEffectEvent,
    OperationEvent,
    OperationInteractionEvent,
    OperationLogRecord,
    OperationNoticeEvent,
    OperationPhaseEvent,
    OperationProgressEvent,
    OperationReconciliationEvent,
    OperationTerminalEvent,
)
from ._interactions import OperationPendingInteraction
from ._journal import (
    OperationObservationCursorAheadError,
    OperationObservationMaterialization,
    OperationObservationReader,
    OperationObservationUnknownOperationError,
    OperationProgressFoldInput,
)
from ._public import (
    OperationNoPendingInteractionV1,
    OperationObservationRefusalCode,
    OperationObservationRefusalV1,
    OperationObservationRequestV1,
    OperationObservationResultV1,
    OperationObservationSuccessV1,
    OperationObservationVersionHeader,
    OperationPublicDiagnosticEventV1,
    OperationPublicEffectEventV1,
    OperationPublicEventPageV1,
    OperationPublicEventV1,
    OperationPublicInteractionEventV1,
    OperationPublicLogEventV1,
    OperationPublicNoticeEventV1,
    OperationPublicPendingInteractionV1,
    OperationPublicPhaseEventV1,
    OperationPublicProgressEventV1,
    OperationPublicProgressV1,
    OperationPublicProjectionV1,
    OperationPublicReconciliationEventV1,
    OperationPublicTerminalEventV1,
    OperationReviewAvailableInteractionV1,
    OperationReviewProjectionReferenceV1,
    OperationUnsupportedInteractionV1,
)
from ._registry import (
    OperationPublicDefinitionContractV1,
    OperationRegistry,
    operation_public_schema_reference,
)
from ._replay import OperationReplayStatus

_SUPPORTED_OBSERVATION_VERSION = 1
_UNSUPPORTED_INTERACTION_CODE = "operation.interaction.unsupported"
_PublicReplayStatus = Literal[
    OperationReplayStatus.PAGE,
    OperationReplayStatus.CAUGHT_UP,
    OperationReplayStatus.EXPIRED,
    OperationReplayStatus.COMPACTED,
]
_CANCELLABLE_LIFECYCLES = frozenset(
    {
        OperationLifecycle.CREATED,
        OperationLifecycle.QUEUED,
        OperationLifecycle.RUNNING,
        OperationLifecycle.WAITING_FOR_INTERACTION,
        OperationLifecycle.WAITING_FOR_EXTERNAL,
    }
)


@dataclass(frozen=True, slots=True)
class OperationObservationService:
    """Return one renderer-neutral projection without mutating operation state."""

    reader: OperationObservationReader
    registry: OperationRegistry

    async def observe(
        self,
        request: OperationObservationVersionHeader | OperationObservationRequestV1,
    ) -> OperationObservationResultV1:
        """Dispatch the current request version and collapse internal failures safely."""
        if request.observation_version != _SUPPORTED_OBSERVATION_VERSION:
            return _refusal(
                OperationObservationRefusalCode.UNSUPPORTED_VERSION,
                requested_version=request.observation_version,
            )
        if not isinstance(request, OperationObservationRequestV1):
            return _refusal(OperationObservationRefusalCode.INVALID_CURSOR, requested_version=1)
        try:
            materialization = await self.reader.read_observation(
                request.operation_id,
                request.after_cursor,
                limit=request.page_limit,
            )
        except OperationObservationUnknownOperationError:
            return _refusal(OperationObservationRefusalCode.UNKNOWN_OPERATION, requested_version=1)
        except OperationObservationCursorAheadError:
            return _refusal(OperationObservationRefusalCode.CURSOR_AHEAD, requested_version=1)
        except Exception:
            return _refusal(OperationObservationRefusalCode.OBSERVATION_UNAVAILABLE, requested_version=1)

        try:
            return self._project(materialization)
        except KeyError:
            return _refusal(
                OperationObservationRefusalCode.DEFINITION_CONTRACT_MISMATCH,
                requested_version=1,
            )
        except _DefinitionContractMismatchError:
            return _refusal(
                OperationObservationRefusalCode.DEFINITION_CONTRACT_MISMATCH,
                requested_version=1,
            )
        except Exception:
            return _refusal(OperationObservationRefusalCode.OBSERVATION_UNAVAILABLE, requested_version=1)

    def _project(self, materialization: OperationObservationMaterialization) -> OperationObservationSuccessV1:
        snapshot = materialization.snapshot
        contract = self.registry.lookup_public_contract(snapshot.identity.definition_id)
        if snapshot.definition_contract_digest != contract.definition_contract_digest:
            raise _DefinitionContractMismatchError
        contract_set = self.registry.public_contract_set
        if contract not in contract_set.definitions:
            raise _DefinitionContractMismatchError

        progress, folded_phase = _fold_progress(materialization.progress_fold)
        if folded_phase != snapshot.phase_code:
            raise ValueError("progress fold phase disagrees with the anchored snapshot")
        receipt = snapshot.terminal_receipt
        projection = OperationPublicProjectionV1(
            operation_id=snapshot.operation_id,
            definition_id=snapshot.identity.definition_id,
            subject_ref=snapshot.identity.subject_ref,
            revision=snapshot.revision,
            anchor_cursor=materialization.anchor_cursor,
            definition_contract=contract,
            contract_set_digest=contract_set.contract_set_digest,
            lifecycle=snapshot.lifecycle,
            terminal_condition=snapshot.terminal_condition,
            effect=snapshot.effect,
            phase_code=snapshot.phase_code,
            started_at=snapshot.started_at,
            updated_at=snapshot.updated_at,
            progress=progress,
            close_policy=contract.close_policy,
            cancellation=contract.cancellation,
            cancellable_now=(
                contract.cancellation is not OperationCancellation.UNSUPPORTED
                and snapshot.lifecycle in _CANCELLABLE_LIFECYCLES
                and snapshot.cancellation_requested_at is None
                and not snapshot.cancellation_deferred
            ),
            cancellation_requested=snapshot.cancellation_requested_at is not None,
            cancellation_acknowledged=snapshot.cancellation_acknowledged_at is not None,
            execution_deadline_at=snapshot.execution_deadline,
            cleanup_deadline_at=snapshot.cleanup_deadline,
            pending_interaction=_project_pending_interaction(snapshot.pending_interaction, contract),
            result_ref=None if receipt is None else receipt.result_ref,
            refusal_ref=None if receipt is None else receipt.refusal_ref,
            diagnostic_ref=None if receipt is None else receipt.diagnostic_ref,
        )
        replay = materialization.replay
        replay_status = cast(_PublicReplayStatus, replay.status)
        event_page = OperationPublicEventPageV1(
            operation_id=snapshot.operation_id,
            anchor_cursor=materialization.anchor_cursor,
            requested_cursor=replay.requested_cursor,
            status=replay_status,
            events=tuple(_project_event(event) for event in replay.events),
            next_cursor=replay.next_cursor,
            restart_cursor=replay.restart_cursor,
        )
        return OperationObservationSuccessV1(projection=projection, event_page=event_page)


class _DefinitionContractMismatchError(RuntimeError):
    pass


def _refusal(
    code: OperationObservationRefusalCode,
    *,
    requested_version: int | None,
) -> OperationObservationRefusalV1:
    return OperationObservationRefusalV1(
        code=code,
        requested_version=requested_version,
        diagnostic_ref=None,
    )


def _fold_progress(
    fold: OperationProgressFoldInput,
) -> tuple[OperationPublicProgressV1 | None, str | None]:
    checkpoint = fold.checkpoint
    phase_code = None if checkpoint is None else checkpoint.phase_code
    progress_event = None if checkpoint is None else checkpoint.progress_event
    for event in fold.events:
        if isinstance(event, OperationPhaseEvent):
            phase_code = event.phase_code
            progress_event = None
        elif isinstance(event, OperationProgressEvent):
            progress_event = event
    progress = (
        None
        if progress_event is None
        else OperationPublicProgressV1(
            completed=progress_event.completed,
            total=progress_event.total,
            unit_code=progress_event.unit_code,
            phase_code=phase_code,
            event_sequence=progress_event.sequence,
            revision=progress_event.revision,
        )
    )
    return progress, phase_code


def _project_pending_interaction(
    pending: OperationPendingInteraction | None,
    contract: OperationPublicDefinitionContractV1,
) -> OperationPublicPendingInteractionV1:
    if pending is None:
        return OperationNoPendingInteractionV1()
    request = pending.request
    if request.kind not in contract.interaction_kinds:
        raise _DefinitionContractMismatchError
    if request.kind is OperationInteractionKind.REVIEW:
        review_schema = contract.review_projection_schema
        response_schema = contract.interaction_response_schema
        if review_schema is None or response_schema is None:
            raise _DefinitionContractMismatchError
        if request.response_schema_ref != operation_public_schema_reference(response_schema):
            raise _DefinitionContractMismatchError
        reference = OperationReviewProjectionReferenceV1(
            operation_id=request.identity.operation_id,
            interaction_id=request.interaction_id,
            revision=request.revision,
            review_projection_schema=review_schema,
            definition_contract_digest=contract.definition_contract_digest,
            expires_at=request.expires_at,
        )
        return OperationReviewAvailableInteractionV1(
            operation_id=request.identity.operation_id,
            interaction_id=request.interaction_id,
            revision=request.revision,
            presentation_code=request.presentation_code,
            response_schema=response_schema,
            expires_at=request.expires_at,
            review_reference=reference,
        )
    if request.kind in {OperationInteractionKind.INPUT, OperationInteractionKind.CHOICE}:
        return OperationUnsupportedInteractionV1(
            interaction_kind=request.kind,
            interaction_id=request.interaction_id,
            revision=request.revision,
            presentation_code=request.presentation_code,
            unsupported_code=_UNSUPPORTED_INTERACTION_CODE,
            expires_at=request.expires_at,
        )
    raise ValueError("pending interaction kind has no public observation contract")


def _project_event(event: OperationEvent) -> OperationPublicEventV1:
    if isinstance(event, OperationPhaseEvent):
        return OperationPublicPhaseEventV1(
            revision=event.revision,
            sequence=event.sequence,
            timestamp=event.timestamp,
            code=event.code,
            phase_code=event.phase_code,
        )
    if isinstance(event, OperationProgressEvent):
        return OperationPublicProgressEventV1(
            revision=event.revision,
            sequence=event.sequence,
            timestamp=event.timestamp,
            code=event.code,
            completed=event.completed,
            total=event.total,
            unit_code=event.unit_code,
        )
    if isinstance(event, OperationLogRecord):
        return OperationPublicLogEventV1(
            revision=event.revision,
            sequence=event.sequence,
            timestamp=event.timestamp,
            code=event.code,
            severity=event.severity,
            diagnostic_ref=event.diagnostic_ref,
        )
    if isinstance(event, OperationEffectEvent):
        return OperationPublicEffectEventV1(
            revision=event.revision,
            sequence=event.sequence,
            timestamp=event.timestamp,
            code=event.code,
            effect=event.effect,
        )
    if isinstance(event, OperationNoticeEvent):
        return OperationPublicNoticeEventV1(
            revision=event.revision,
            sequence=event.sequence,
            timestamp=event.timestamp,
            code=event.code,
            notice_code=event.notice_code,
        )
    if isinstance(event, OperationReconciliationEvent):
        return OperationPublicReconciliationEventV1(
            revision=event.revision,
            sequence=event.sequence,
            timestamp=event.timestamp,
            code=event.code,
            outcome=event.outcome,
        )
    if isinstance(event, OperationDiagnosticEvent):
        return OperationPublicDiagnosticEventV1(
            revision=event.revision,
            sequence=event.sequence,
            timestamp=event.timestamp,
            code=event.code,
            diagnostic_ref=event.diagnostic_ref,
        )
    if isinstance(event, OperationInteractionEvent):
        return OperationPublicInteractionEventV1(
            revision=event.revision,
            sequence=event.sequence,
            timestamp=event.timestamp,
            code=event.code,
            interaction_id=event.interaction_id,
        )
    if isinstance(event, OperationTerminalEvent):
        receipt = event.receipt
        return OperationPublicTerminalEventV1(
            revision=event.revision,
            sequence=event.sequence,
            timestamp=event.timestamp,
            code=event.code,
            condition=receipt.condition,
            effect=receipt.effect,
            result_ref=receipt.result_ref,
            refusal_ref=receipt.refusal_ref,
            diagnostic_ref=receipt.diagnostic_ref,
        )
    raise TypeError("unknown operation event variant")


__all__ = ["OperationObservationService"]
