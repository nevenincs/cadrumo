"""Records entry tools and review exclusion through the installed TUI's retained runtime session.

Every door here submits one registered ``ledger.*`` operation for the exact
profile and session the workbench was admitted for, and refuses a result its
terminal receipt does not support: another profile, another record, a refusal
receipt, or an effect the request cannot have caused.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Final
from uuid import UUID

from pydantic import BaseModel

from cadrumo.application.ledger.check_operation import (
    LEDGER_CHECK_OPERATION_DEFINITION_ID,
    LedgerCheckProjection,
    LedgerCheckRequest,
)
from cadrumo.application.ledger.export_operation import (
    LEDGER_EXPORT_OPERATION_DEFINITION_ID,
    LedgerExportProjection,
    LedgerExportRequest,
)
from cadrumo.application.ledger.history_operation import (
    LEDGER_HISTORY_OPERATION_DEFINITION_ID,
    LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID,
    LedgerHistoryProjection,
    LedgerHistoryRequest,
    LedgerHistoryTypedProjection,
)
from cadrumo.application.ledger.ledger_add_contracts import (
    LEDGER_ADD_OPERATION_DEFINITION_ID,
    LEDGER_ADD_VALIDATION_REFUSAL_CODE,
    LedgerAddOperationResult,
    LedgerAddRequest,
)
from cadrumo.application.ledger.lifecycle_contracts import (
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
    LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID,
    LEDGER_STASH_OPERATION_DEFINITION_ID,
    LedgerLifecycleMutationProjection,
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationId,
    LedgerLifecycleOperationResult,
)
from cadrumo.application.ledger.lifecycle_mutation_operation import LedgerLifecycleValidationRefusedError
from cadrumo.application.ledger.list_operation import (
    LEDGER_LIST_OPERATION_DEFINITION_ID,
    LedgerListProjection,
    LedgerListRequest,
)
from cadrumo.application.ledger.merge_operation import (
    LEDGER_MERGE_OPERATION_DEFINITION_ID,
    LedgerMergeOperationResult,
    LedgerMergeRequest,
)
from cadrumo.application.ledger.preflight_operation import (
    LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
    LedgerPreflightProjection,
    LedgerPreflightRequest,
)
from cadrumo.application.ledger.remove_operation import (
    LEDGER_REMOVE_OPERATION_DEFINITION_ID,
    LedgerRemoveOperationResult,
    LedgerRemoveRequest,
)
from cadrumo.application.ledger.reset_operation import (
    LEDGER_RESET_OPERATION_DEFINITION_ID,
    LedgerResetOperationResult,
    LedgerResetRequest,
)
from cadrumo.application.ledger.status_operation import (
    LEDGER_STATUS_OPERATION_DEFINITION_ID,
    LedgerStatusProjection,
    LedgerStatusRequest,
)
from cadrumo.application.ledger.track_operation import (
    LEDGER_TRACK_OPERATION_DEFINITION_ID,
    LedgerTrackProjection,
    LedgerTrackRequest,
)
from cadrumo.application.ledger.workspace import LedgerWorkspaceArea
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operator_actions.catalogue import lookup_action
from cadrumo.application.review.filter import LedgerReviewStatus
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition
from cadrumo.entrypoints.tui.ledger.entries_add import LedgerEntryAddScreen
from cadrumo.entrypoints.tui.ledger.entries_browse import LedgerEntriesBrowseScreen
from cadrumo.entrypoints.tui.ledger.entries_doors import (
    LedgerEntriesDoorsV1,
)
from cadrumo.entrypoints.tui.ledger.entries_export import LedgerEntriesExportScreen
from cadrumo.entrypoints.tui.ledger.entries_health import LedgerHealthScreen
from cadrumo.entrypoints.tui.ledger.entries_reset import LedgerResetScreen
from cadrumo.entrypoints.tui.ledger.models import (
    LedgerExclusionResultV1,
    LedgerExclusionSubmissionV1,
    LedgerExclusionSubmitterV1,
)
from cadrumo.entrypoints.tui.ledger.tools import LedgerToolV1
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.transport.frontend_client import FrontendClient

from .operations.runtime_profile_session import RuntimeProfileSession

_LIFECYCLE_SUCCESS_STATES: Final[dict[LedgerLifecycleOperationId, str]] = {
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID: "ARCHIVED",
    LEDGER_STASH_OPERATION_DEFINITION_ID: "STASHED",
    LEDGER_RESTORE_OPERATION_DEFINITION_ID: "ACTIVE",
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID: "ACTIVE",
}

type _Correlation[RequestT, ResultT] = Callable[
    [ResultT, RequestT, OperationTerminalCondition, OperationPublicProjectionV1], bool
]


def _settled(
    condition: OperationTerminalCondition, terminal: OperationPublicProjectionV1, effect: OperationEffect
) -> bool:
    """A successful receipt with no refusal and exactly the expected effect."""
    return (
        condition is OperationTerminalCondition.SUCCEEDED
        and terminal.refusal_ref is None
        and terminal.failure_error_code is None
        and terminal.effect is effect
    )


def _refused_with_detail(
    condition: OperationTerminalCondition, terminal: OperationPublicProjectionV1, code: str
) -> bool:
    """A refusal receipt carrying exactly the declared detail code and no effect."""
    return (
        condition is OperationTerminalCondition.REFUSED
        and terminal.refusal_ref == code
        and terminal.effect is OperationEffect.NONE
    )


def _decimal(text: str) -> Decimal | None:
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _names_transaction(transaction_id: str, prefix: str) -> bool:
    return transaction_id.startswith(prefix.strip().lower())


def _list_matches(
    result: LedgerListProjection,
    request: LedgerListRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        _settled(condition, terminal, OperationEffect.NONE)
        and result.profile_id == request.profile_id
        and result.offset == request.offset
        and result.limit == request.limit
        and result.by_group == request.by_group
        and (request.limit is None or len(result.rows) <= request.limit)
    )


def _history_matches(
    result: LedgerHistoryProjection | LedgerHistoryTypedProjection,
    request: LedgerHistoryRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        _settled(condition, terminal, OperationEffect.NONE)
        and result.profile_id == request.profile_id
        and result.transaction_prefix == request.transaction_prefix
        and result.include_split_siblings == request.include_split_siblings
    )


def _track_matches(
    result: LedgerTrackProjection,
    request: LedgerTrackRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        _settled(condition, terminal, OperationEffect.NONE)
        and result.profile_id == request.profile_id
        and result.transaction_prefix == request.transaction_prefix
    )


def _status_matches(
    result: LedgerStatusProjection,
    request: LedgerStatusRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        _settled(condition, terminal, OperationEffect.NONE)
        and result.profile_id == request.profile_id
        and result.period == request.period
    )


def _check_matches(
    result: LedgerCheckProjection,
    request: LedgerCheckRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        _settled(condition, terminal, OperationEffect.NONE)
        and result.profile_id == request.profile_id
        and result.bucket_id == str(request.profile_id)
        and result.period == request.period
    )


def _preflight_matches(
    result: LedgerPreflightProjection,
    request: LedgerPreflightRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        _settled(condition, terminal, OperationEffect.NONE)
        and result.profile_id == request.profile_id
        and result.bucket_id == str(request.profile_id)
        and result.period == request.period
    )


def _add_matches(
    result: LedgerAddOperationResult,
    request: LedgerAddRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    if result.profile_id != request.profile_id:
        return False
    if result.outcome == "validation_error":
        return _refused_with_detail(condition, terminal, LEDGER_ADD_VALIDATION_REFUSAL_CODE)
    transaction = result.transaction
    expected_effect = OperationEffect.UPDATED if result.bucket_event_ids else OperationEffect.NONE
    return (
        transaction is not None
        and _settled(condition, terminal, expected_effect)
        and transaction.booked_date == request.booked_date.strip()
        and transaction.direction == request.direction
        and transaction.description == request.description.strip()
        and _decimal(transaction.amount) == _decimal(request.amount)
        and len(result.bucket_event_ids) <= 1
    )


def _remove_matches(
    result: LedgerRemoveOperationResult,
    request: LedgerRemoveRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    report = result.report
    removed = report.removed and not request.dry_run
    return (
        _settled(condition, terminal, OperationEffect.UPDATED if removed else OperationEffect.NONE)
        and result.profile_id == request.profile_id
        and str(report.bucket_id) == str(request.profile_id)
        and _names_transaction(report.transaction_id, request.transaction_id)
        and report.dry_run is request.dry_run
        and not (request.dry_run and report.removed)
    )


def _lifecycle_projection_matches(
    projection: LedgerLifecycleMutationProjection,
    request: LedgerLifecycleMutationRequest,
    operation_id: LedgerLifecycleOperationId,
) -> bool:
    """Match the exact lifecycle mutation and transaction result."""
    transaction = projection.transaction
    excluded = (
        transaction.business_classification == "REVIEWED_EXCLUDED"
        and projection.review_status is LedgerReviewStatus.EXCLUDED
    )
    return (
        projection.profile_id == request.profile_id
        and projection.operation_id == operation_id
        and _names_transaction(transaction.transaction_id, request.transaction_id)
        and transaction.lifecycle_state == _LIFECYCLE_SUCCESS_STATES[operation_id]
        and len(projection.bucket_event_ids) == 1
        and (operation_id != LEDGER_EXCLUDE_OPERATION_DEFINITION_ID or excluded)
    )


def _lifecycle_matches(
    operation_id: LedgerLifecycleOperationId,
) -> _Correlation[LedgerLifecycleMutationRequest, LedgerLifecycleOperationResult]:
    def matches(
        result: LedgerLifecycleOperationResult,
        request: LedgerLifecycleMutationRequest,
        condition: OperationTerminalCondition,
        terminal: OperationPublicProjectionV1,
    ) -> bool:
        if result.profile_id != request.profile_id or result.operation_id != operation_id:
            return False
        if result.outcome == "validation_error":
            return _refused_with_detail(condition, terminal, LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE)
        projection = result.result
        if projection is None or not _settled(condition, terminal, OperationEffect.UPDATED):
            return False
        return _lifecycle_projection_matches(projection, request, operation_id)

    return matches


def _merge_matches(
    result: LedgerMergeOperationResult,
    request: LedgerMergeRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    children = result.source_child_ids
    return (
        _settled(condition, terminal, OperationEffect.UPDATED)
        and result.profile_id == request.profile_id
        and len(children) == len(request.child_ids)
        and all(sum(1 for child in children if child.startswith(prefix)) == 1 for prefix in request.child_ids)
    )


def _reset_matches(
    result: LedgerResetOperationResult,
    request: LedgerResetRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    report = result.report
    return (
        _settled(condition, terminal, OperationEffect.NONE if request.dry_run else OperationEffect.UPDATED)
        and result.profile_id == request.profile_id
        and str(report.bucket_id) == str(request.profile_id)
        and report.dry_run is request.dry_run
        and report.reset is (not request.dry_run)
        and report.reason == request.reason.strip()
    )


def _export_matches(
    result: LedgerExportProjection,
    request: LedgerExportRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    return (
        _settled(condition, terminal, OperationEffect.UPDATED)
        and result.profile_id == request.profile_id
        and result.bucket_id == str(request.profile_id)
        and result.output_path == request.output_path
        and result.export_format is request.export_format
        and result.row_count == len(result.rows)
        and len(result.bucket_event_ids) == 1
    )


class RuntimeLedgerEntryTuiDoorV1[RequestT: BaseModel, ResultT: BaseModel]:
    """Submit one registered ledger operation for the exact profile and session of its session."""

    def __init__(
        self,
        session: RuntimeProfileSession,
        *,
        definition_id: str,
        result_type: type[ResultT],
        correlate: _Correlation[RequestT, ResultT],
        allow_refusal_detail: bool = False,
    ) -> None:
        """Pin the admitted session, the operation and how its result is correlated."""
        self._session = session
        self._definition_id = definition_id
        self._result_type = result_type
        self._correlate = correlate
        self._allow_refusal_detail = allow_refusal_detail

    @property
    def profile_id(self) -> UUID:
        """The admitted profile every request must name."""
        return self._session.profile_id

    @property
    def definition_id(self) -> str:
        """The registered operation this door submits."""
        return self._definition_id

    async def __call__(self, request: RequestT) -> ResultT:
        """Run one request and refuse a result its terminal receipt does not support."""

        def settle(
            result: ResultT,
            condition: OperationTerminalCondition,
            terminal: OperationPublicProjectionV1,
            _operation_id: str,
        ) -> None:
            if not self._correlate(result, request, condition, terminal):
                raise RefusalError(RefusalCode.INVALID_FRAME)

        return await self._session.run_operation(
            request,
            definition_id=self._definition_id,
            result_type=self._result_type,
            settle=settle,
            allow_refusal_detail=self._allow_refusal_detail,
            explain_failure=True,
        )


class RuntimeLedgerLifecycleTuiDoorV1(
    RuntimeLedgerEntryTuiDoorV1[LedgerLifecycleMutationRequest, LedgerLifecycleOperationResult]
):
    """Submit one lifecycle operation: archive, stash, restore or exclude."""

    def __init__(self, session: RuntimeProfileSession, *, operation_id: LedgerLifecycleOperationId) -> None:
        """Pin the session and the one lifecycle operation this door submits."""
        super().__init__(
            session,
            definition_id=operation_id,
            result_type=LedgerLifecycleOperationResult,
            correlate=_lifecycle_matches(operation_id),
            allow_refusal_detail=True,
        )
        self._operation_id: LedgerLifecycleOperationId = operation_id

    @property
    def operation_id(self) -> LedgerLifecycleOperationId:
        """The lifecycle operation this door submits."""
        return self._operation_id


class RuntimeLedgerExclusionSubmitterV1:
    """Exclude one reviewed entry through ``ledger.exclude``, answering with the identity it settled."""

    def __init__(self, session: RuntimeProfileSession) -> None:
        """Pin the admitted session every exclusion is submitted under."""
        self._door = RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
            result_type=LedgerLifecycleOperationResult,
            correlate=_exclusion_matches,
            allow_refusal_detail=True,
        )

    async def __call__(self, submission: LedgerExclusionSubmissionV1) -> LedgerExclusionResultV1:
        """Exclude exactly the submitted entry and refuse any other settled identity."""
        if submission.action.action_id != lookup_action("operator.ledger.classify").action_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        request = LedgerLifecycleMutationRequest(
            profile_id=self._door.profile_id, transaction_id=submission.transaction_id
        )
        result = await self._door(request)
        # The correlation already held the receipt to this: a validation refusal committed nothing,
        # and a success names exactly the submitted entry.
        if result.validation is not None:
            raise LedgerLifecycleValidationRefusedError(result.validation)
        projection = result.result
        if projection is None:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return LedgerExclusionResultV1(transaction_id=projection.transaction.transaction_id)


def _exclusion_matches(
    result: LedgerLifecycleOperationResult,
    request: LedgerLifecycleMutationRequest,
    condition: OperationTerminalCondition,
    terminal: OperationPublicProjectionV1,
) -> bool:
    """An exclusion receipt that settled exactly the submitted entry, not merely one it names by prefix."""
    projection = result.result
    return _lifecycle_matches(LEDGER_EXCLUDE_OPERATION_DEFINITION_ID)(result, request, condition, terminal) and (
        projection is None or projection.transaction.transaction_id == request.transaction_id
    )


def compose_runtime_ledger_entries_doors(client: FrontendClient, *, profile_label: str) -> LedgerEntriesDoorsV1:
    """Bind every entry door to one retained session of the workbench's exact profile."""
    session = RuntimeProfileSession(client, profile_label=profile_label)
    return LedgerEntriesDoorsV1(
        list_entries=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_LIST_OPERATION_DEFINITION_ID,
            result_type=LedgerListProjection,
            correlate=_list_matches,
        ),
        add=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_ADD_OPERATION_DEFINITION_ID,
            result_type=LedgerAddOperationResult,
            correlate=_add_matches,
            allow_refusal_detail=True,
        ),
        remove=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_REMOVE_OPERATION_DEFINITION_ID,
            result_type=LedgerRemoveOperationResult,
            correlate=_remove_matches,
        ),
        archive=RuntimeLedgerLifecycleTuiDoorV1(session, operation_id=LEDGER_ARCHIVE_OPERATION_DEFINITION_ID),
        stash=RuntimeLedgerLifecycleTuiDoorV1(session, operation_id=LEDGER_STASH_OPERATION_DEFINITION_ID),
        restore=RuntimeLedgerLifecycleTuiDoorV1(session, operation_id=LEDGER_RESTORE_OPERATION_DEFINITION_ID),
        exclude=RuntimeLedgerLifecycleTuiDoorV1(session, operation_id=LEDGER_EXCLUDE_OPERATION_DEFINITION_ID),
        merge=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_MERGE_OPERATION_DEFINITION_ID,
            result_type=LedgerMergeOperationResult,
            correlate=_merge_matches,
        ),
        history=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_HISTORY_OPERATION_DEFINITION_ID,
            result_type=LedgerHistoryProjection,
            correlate=_history_matches,
        ),
        history_typed=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID,
            result_type=LedgerHistoryTypedProjection,
            correlate=_history_matches,
        ),
        track=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_TRACK_OPERATION_DEFINITION_ID,
            result_type=LedgerTrackProjection,
            correlate=_track_matches,
        ),
        status=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_STATUS_OPERATION_DEFINITION_ID,
            result_type=LedgerStatusProjection,
            correlate=_status_matches,
        ),
        check=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_CHECK_OPERATION_DEFINITION_ID,
            result_type=LedgerCheckProjection,
            correlate=_check_matches,
        ),
        preflight=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_PREFLIGHT_OPERATION_DEFINITION_ID,
            result_type=LedgerPreflightProjection,
            correlate=_preflight_matches,
        ),
        reset=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_RESET_OPERATION_DEFINITION_ID,
            result_type=LedgerResetOperationResult,
            correlate=_reset_matches,
        ),
        export=RuntimeLedgerEntryTuiDoorV1(
            session,
            definition_id=LEDGER_EXPORT_OPERATION_DEFINITION_ID,
            result_type=LedgerExportProjection,
            correlate=_export_matches,
        ),
    )


def compose_runtime_ledger_exclusion_submitter(
    client: FrontendClient, *, profile_label: str
) -> LedgerExclusionSubmitterV1:
    """Bind the Review area's exclusion to ``ledger.exclude`` in the workbench's exact session."""
    return RuntimeLedgerExclusionSubmitterV1(RuntimeProfileSession(client, profile_label=profile_label))


def compose_entries_tools(client: FrontendClient, profile_label: str) -> tuple[LedgerToolV1, ...]:
    """The entry and export tools, all bound to one retained session of the workbench's profile."""
    doors = compose_runtime_ledger_entries_doors(client, profile_label=profile_label)
    return (
        LedgerToolV1(
            key="ledger.tool.entries.browse",
            label_key="tui.ledger.entry_tools.tool.browse",
            area=LedgerWorkspaceArea.ENTRIES,
            build=lambda controller: LedgerEntriesBrowseScreen(controller, doors),
        ),
        LedgerToolV1(
            key="ledger.tool.entries.add",
            label_key="tui.ledger.entry_tools.tool.add",
            area=LedgerWorkspaceArea.ENTRIES,
            build=lambda controller: LedgerEntryAddScreen(controller, doors),
        ),
        LedgerToolV1(
            key="ledger.tool.entries.export",
            label_key="tui.ledger.entry_tools.tool.export",
            area=LedgerWorkspaceArea.ENTRIES,
            build=lambda controller: LedgerEntriesExportScreen(controller, doors),
        ),
        LedgerToolV1(
            key="ledger.tool.entries.health",
            label_key="tui.ledger.entry_tools.tool.health",
            area=LedgerWorkspaceArea.OVERVIEW,
            build=lambda controller: LedgerHealthScreen(controller, doors),
        ),
        LedgerToolV1(
            key="ledger.tool.entries.reset",
            label_key="tui.ledger.entry_tools.tool.reset",
            area=LedgerWorkspaceArea.OVERVIEW,
            build=lambda controller: LedgerResetScreen(controller, doors),
        ),
    )


__all__ = [
    "RuntimeLedgerEntryTuiDoorV1",
    "RuntimeLedgerExclusionSubmitterV1",
    "RuntimeLedgerLifecycleTuiDoorV1",
    "compose_entries_tools",
    "compose_runtime_ledger_entries_doors",
    "compose_runtime_ledger_exclusion_submitter",
]
