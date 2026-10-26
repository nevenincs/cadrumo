"""Evidence and attachment operations through the installed TUI's retained runtime session.

All twelve doors share one session pinned to the admitted profile, so composing
them observes the session once. Each door refuses a result its terminal receipt
does not support: another profile, another record, a refusal where a success
was reported, or an effect the result contradicts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Final
from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE,
    LEDGER_DETACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationResult,
    LedgerAttachRequest,
    LedgerDetachRequest,
)
from cadrumo.application.ledger.evidence_followup_contracts import (
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceAttachmentQueueProjection,
    LedgerEvidenceAttachmentQueueRequest,
    LedgerEvidenceAttachmentViewProjection,
    LedgerEvidenceAttachmentViewRequest,
    LedgerEvidenceConsentListProjection,
    LedgerEvidenceConsentListRequest,
    LedgerEvidenceReviewSummaryProjection,
    LedgerEvidenceReviewViewProjection,
    LedgerEvidenceReviewViewRequest,
)
from cadrumo.application.ledger.evidence_ingestion_contracts import (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
)
from cadrumo.application.ledger.evidence_mutation_operation import (
    LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID,
    LedgerEvidenceRemoveProjection,
    LedgerEvidenceRemoveRequest,
    LedgerEvidenceUpdateField,
    LedgerEvidenceUpdateProjection,
    LedgerEvidenceUpdateRequest,
)
from cadrumo.application.ledger.evidence_read_operation import (
    LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID,
    LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE,
    LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceQueryProjection,
    LedgerEvidenceQueryRequest,
    LedgerEvidenceViewProjection,
    LedgerEvidenceViewRequest,
    LedgerEvidenceViewSuccess,
)
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.entrypoints.tui.ledger.evidence_files_doors import LedgerEvidenceFilesDoorsV1
from cadrumo.entrypoints.tui.ledger.evidence_files_records import evidence_field_value
from cadrumo.entrypoints.tui.ledger.evidence_files_tools import evidence_files_tools
from cadrumo.entrypoints.tui.ledger.tools import LedgerToolV1
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .operations.runtime_profile_session import RuntimeProfileSession

_DECIMAL_UPDATE_FIELDS: Final = frozenset({"taxable_base", "iva_rate", "iva_amount"})
_WRITE_EFFECTS: Final = frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL})


@dataclass(frozen=True, slots=True)
class _DoorSpec[RequestT: BaseModel, ResultT: BaseModel]:
    """One registered operation: its identity, public result schema and receipt correlation."""

    definition_id: str
    result_type: type[ResultT]
    matches: Callable[[ResultT, RequestT, OperationTerminalCondition, OperationPublicProjectionV1], bool]
    result_version: int = 1
    allow_refusal_detail: bool = False


def _settled(
    condition: OperationTerminalCondition, terminal: OperationPublicProjectionV1, effect: OperationEffect
) -> bool:
    """A success with no refusal whose receipt reports exactly ``effect``."""
    return (
        condition is OperationTerminalCondition.SUCCEEDED and terminal.refusal_ref is None and terminal.effect is effect
    )


def _refused(condition: OperationTerminalCondition, terminal: OperationPublicProjectionV1, code: str) -> bool:
    """A declared refusal that wrote nothing."""
    return (
        condition is OperationTerminalCondition.REFUSED
        and terminal.refusal_ref == code
        and terminal.effect is OperationEffect.NONE
    )


def _query_matches(
    result: LedgerEvidenceQueryProjection,
    request: LedgerEvidenceQueryRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        result.profile_id == request.profile_id
        and result.evidence_id == request.evidence_id
        and _settled(condition, terminal, OperationEffect.NONE)
    )


def _view_matches(
    result: LedgerEvidenceViewProjection,
    request: LedgerEvidenceViewRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    if result.profile_id != request.profile_id:
        return False
    if isinstance(result.outcome, LedgerEvidenceViewSuccess):
        return result.outcome.record.evidence_id == request.evidence_id and _settled(
            condition, terminal, OperationEffect.NONE
        )
    return _refused(condition, terminal, LEDGER_EVIDENCE_VIEW_NOT_FOUND_REFUSAL_CODE)


def _patched_value_holds(
    result: LedgerEvidenceUpdateProjection, request: LedgerEvidenceUpdateRequest, field: LedgerEvidenceUpdateField
) -> bool:
    recorded = evidence_field_value(result.record, field)
    requested = evidence_field_value(request.patch, field)
    if field in _DECIMAL_UPDATE_FIELDS and recorded is not None and requested is not None:
        return Decimal(recorded) == Decimal(requested)
    return recorded == requested


def _update_matches(
    result: LedgerEvidenceUpdateProjection,
    request: LedgerEvidenceUpdateRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    effect = OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
    return (
        result.profile_id == request.profile_id
        and result.record.evidence_id == request.evidence_id
        and all(_patched_value_holds(result, request, field) for field in request.patch_fields)
        and _settled(condition, terminal, effect)
    )


def _remove_matches(
    result: LedgerEvidenceRemoveProjection,
    request: LedgerEvidenceRemoveRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        result.profile_id == request.profile_id
        and result.record.evidence_id == request.evidence_id
        and _settled(condition, terminal, OperationEffect.UPDATED)
    )


def _batch_matches(
    result: LedgerEvidenceBatchProjection,
    request: LedgerEvidenceBatchRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        result.profile_id == request.profile_id
        and result.direction is request.direction
        and result.effect in _WRITE_EFFECTS
        and _settled(condition, terminal, result.effect)
    )


def _queue_matches(
    result: LedgerEvidenceAttachmentQueueProjection,
    request: LedgerEvidenceAttachmentQueueRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return result.profile_id == request.profile_id and _settled(condition, terminal, OperationEffect.NONE)


def _attachment_view_matches(
    result: LedgerEvidenceAttachmentViewProjection,
    request: LedgerEvidenceAttachmentViewRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        result.profile_id == request.profile_id
        and result.item.attachment_id == request.attachment_id
        and _settled(condition, terminal, OperationEffect.NONE)
    )


def _consent_matches(
    result: LedgerEvidenceConsentListProjection,
    request: LedgerEvidenceConsentListRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return result.profile_id == request.profile_id and _settled(condition, terminal, OperationEffect.NONE)


def _review_view_matches(
    result: LedgerEvidenceReviewViewProjection,
    request: LedgerEvidenceReviewViewRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        result.profile_id == request.profile_id
        and result.evidence_reference == request.evidence_reference
        and _settled(condition, terminal, OperationEffect.NONE)
    )


def _review_summary_matches(
    result: LedgerEvidenceReviewSummaryProjection,
    request: LedgerEvidenceReviewViewRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        result.profile_id == request.profile_id
        and result.evidence_reference == request.evidence_reference
        and _settled(condition, terminal, OperationEffect.NONE)
    )


def _attachment_matches(
    definition_id: str,
) -> Callable[
    [
        LedgerAttachmentOperationResult,
        LedgerAttachRequest | LedgerDetachRequest,
        OperationTerminalCondition,
        OperationPublicProjectionV1,
    ],
    bool,
]:
    def matches(
        result: LedgerAttachmentOperationResult,
        request: LedgerAttachRequest | LedgerDetachRequest,
        condition: OperationTerminalCondition,
        terminal: OperationPublicProjectionV1,
    ) -> bool:
        if result.profile_id != request.profile_id or result.operation_id != definition_id:
            return False
        projection = result.result
        if result.outcome == "validation_error" or projection is None:
            return _refused(condition, terminal, LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE)
        effect = OperationEffect.UPDATED if projection.bucket_event_ids else OperationEffect.NONE
        return projection.transaction.transaction_id == request.transaction_id and _settled(condition, terminal, effect)

    return matches


_QUERY: Final = _DoorSpec(LEDGER_EVIDENCE_QUERY_OPERATION_DEFINITION_ID, LedgerEvidenceQueryProjection, _query_matches)
# The view publishes a missing record as a declared refusal carrying its own result, under result schema 2.
_VIEW: Final = _DoorSpec(
    LEDGER_EVIDENCE_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceViewProjection,
    _view_matches,
    result_version=2,
    allow_refusal_detail=True,
)
_UPDATE: Final = _DoorSpec(
    LEDGER_EVIDENCE_UPDATE_OPERATION_DEFINITION_ID, LedgerEvidenceUpdateProjection, _update_matches
)
_REMOVE: Final = _DoorSpec(
    LEDGER_EVIDENCE_REMOVE_OPERATION_DEFINITION_ID, LedgerEvidenceRemoveProjection, _remove_matches
)
_BATCH: Final = _DoorSpec(LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID, LedgerEvidenceBatchProjection, _batch_matches)
_ATTACHMENT_QUEUE: Final = _DoorSpec(
    LEDGER_EVIDENCE_ATTACHMENT_QUEUE_OPERATION_DEFINITION_ID, LedgerEvidenceAttachmentQueueProjection, _queue_matches
)
_ATTACHMENT_VIEW: Final = _DoorSpec(
    LEDGER_EVIDENCE_ATTACHMENT_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceAttachmentViewProjection,
    _attachment_view_matches,
)
_CONSENT_LIST: Final = _DoorSpec(
    LEDGER_EVIDENCE_CONSENT_LIST_OPERATION_DEFINITION_ID, LedgerEvidenceConsentListProjection, _consent_matches
)
# The review view's public result is registered under schema 2.
_REVIEW_VIEW: Final = _DoorSpec(
    LEDGER_EVIDENCE_REVIEW_VIEW_OPERATION_DEFINITION_ID,
    LedgerEvidenceReviewViewProjection,
    _review_view_matches,
    result_version=2,
)
_REVIEW_SUMMARY: Final = _DoorSpec(
    LEDGER_EVIDENCE_REVIEW_SUMMARY_OPERATION_DEFINITION_ID,
    LedgerEvidenceReviewSummaryProjection,
    _review_summary_matches,
)
# A pre-write refusal of an attach or detach is a declared refusal carrying its validation messages.
_ATTACH: Final = _DoorSpec[LedgerAttachRequest, LedgerAttachmentOperationResult](
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationResult,
    _attachment_matches(LEDGER_ATTACH_OPERATION_DEFINITION_ID),
    allow_refusal_detail=True,
)
_DETACH: Final = _DoorSpec[LedgerDetachRequest, LedgerAttachmentOperationResult](
    LEDGER_DETACH_OPERATION_DEFINITION_ID,
    LedgerAttachmentOperationResult,
    _attachment_matches(LEDGER_DETACH_OPERATION_DEFINITION_ID),
    allow_refusal_detail=True,
)


class RuntimeEvidenceFilesTuiDoorV1[RequestT: BaseModel, ResultT: BaseModel]:
    """Submit one evidence operation's requests for the exact profile and session the session pins."""

    def __init__(self, session: RuntimeProfileSession, spec: _DoorSpec[RequestT, ResultT]) -> None:
        """Bind the shared pinned session and the operation this door submits."""
        self._session = session
        self._spec = spec

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    @property
    def definition_id(self) -> str:
        """The registered operation this door submits."""
        return self._spec.definition_id

    async def __call__(self, request: RequestT) -> ResultT:
        """Run one request and refuse a result its terminal receipt does not support."""
        spec = self._spec

        def settle(
            result: ResultT,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not spec.matches(result, request, condition, terminal):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=spec.definition_id,
            result_type=spec.result_type,
            settle=settle,
            result_version=spec.result_version,
            allow_refusal_detail=spec.allow_refusal_detail,
            explain_failure=True,
        )


def compose_runtime_evidence_files_doors(client: FrontendClient, *, profile_label: str) -> LedgerEvidenceFilesDoorsV1:
    """Bind the twelve evidence doors to one session pinned on the workbench's runtime client."""
    session = RuntimeProfileSession(client, profile_label=profile_label)
    return LedgerEvidenceFilesDoorsV1(
        query=RuntimeEvidenceFilesTuiDoorV1(session, _QUERY),
        view=RuntimeEvidenceFilesTuiDoorV1(session, _VIEW),
        update=RuntimeEvidenceFilesTuiDoorV1(session, _UPDATE),
        remove=RuntimeEvidenceFilesTuiDoorV1(session, _REMOVE),
        batch=RuntimeEvidenceFilesTuiDoorV1(session, _BATCH),
        attachment_queue=RuntimeEvidenceFilesTuiDoorV1(session, _ATTACHMENT_QUEUE),
        attachment_view=RuntimeEvidenceFilesTuiDoorV1(session, _ATTACHMENT_VIEW),
        consent_list=RuntimeEvidenceFilesTuiDoorV1(session, _CONSENT_LIST),
        review_view=RuntimeEvidenceFilesTuiDoorV1(session, _REVIEW_VIEW),
        review_summary=RuntimeEvidenceFilesTuiDoorV1(session, _REVIEW_SUMMARY),
        attach=RuntimeEvidenceFilesTuiDoorV1(session, _ATTACH),
        detach=RuntimeEvidenceFilesTuiDoorV1(session, _DETACH),
    )


def compose_evidence_files_tools(client: FrontendClient, profile_label: str) -> tuple[LedgerToolV1, ...]:
    """The evidence and attachment tools, bound to the workbench's exact profile session."""
    return evidence_files_tools(compose_runtime_evidence_files_doors(client, profile_label=profile_label))


__all__ = [
    "RuntimeEvidenceFilesTuiDoorV1",
    "compose_evidence_files_tools",
    "compose_runtime_evidence_files_doors",
]
