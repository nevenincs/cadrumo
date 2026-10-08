"""Declaration contract shared by registered live AEAT operations.

Every live operation is recorded, has no interactive prompts, interrupts on
reconciliation and is offered on every frontend. A capture that persists what
it read takes a fresh COMMIT fence for those local writes.
"""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..ledger.read_access import resolve_ledger_commit_access, resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import OperationCapabilities
from ..operations.models import (
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_receipt_references,
    require_terminal_receipt_match,
    require_terminal_receipt_match_any_effect,
)
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.profile_guard import ProfileAccessPayload, require_access_request_profile_payload
from ..operations.registry import ALL_OPERATION_FRONTENDS, OperationReconciliationPolicy
from ..operator_actions.models import ActionReference


def build_live_operation_definition[ExecutorT](
    *,
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[ExecutorT],
    build: Callable[[], ExecutorT],
    phase_codes: tuple[str, ...],
    capabilities: OperationCapabilities,
    action_reference: ActionReference | None = None,
) -> OperationDefinition:
    """Declare one non-interactive live operation offered on every frontend."""
    return OperationDefinition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_factory=OperationExecutorFactory(request_type=request_type, executor_type=executor_type, build=build),
        phase_codes=phase_codes,
        interaction_kinds=frozenset(),
        action_reference=action_reference,
        capabilities=capabilities,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def resolve_whole_profile_read_access[PayloadT: ProfileAccessPayload](
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    definition_id: str,
    payload_type: type[PayloadT],
) -> ResolvedOperationAccess:
    """Grant ledger reads over every period of the request's own profile."""
    payload = require_access_request_profile_payload(
        request, definition_id=definition_id, payload_type=payload_type, access_profile_id=context.profile_id
    )
    return resolve_ledger_read_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def resolve_whole_profile_capture_access[PayloadT: ProfileAccessPayload](
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
    *,
    definition_id: str,
    payload_type: type[PayloadT],
) -> ResolvedOperationAccess:
    """Grant whole-profile ledger reads plus a fresh COMMIT fence for the capture's local writes."""
    payload = require_access_request_profile_payload(
        request, definition_id=definition_id, payload_type=payload_type, access_profile_id=context.profile_id
    )
    return resolve_ledger_commit_access(request, context, profile_id=payload.profile_id, periods=frozenset())


def require_live_read_receipt(
    receipt: OperationTerminalReceipt, *, definition_id: str, bucket_id: str, message: str
) -> None:
    """Raise ``ValueError(message)`` unless ``receipt`` settled this profile's read with no effect."""
    require_terminal_receipt_match(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(bucket_id),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message=message,
    )


_STORED_CAPTURE_EFFECTS = frozenset({OperationEffect.UPDATED})
_UNSTORED_CAPTURE_EFFECTS = frozenset({OperationEffect.NONE, OperationEffect.UPDATED})


def require_live_capture_receipt(
    receipt: OperationTerminalReceipt, *, definition_id: str, bucket_id: str, stored: bool, message: str
) -> None:
    """Raise ``ValueError(message)`` unless ``receipt`` settled this profile's capture as its executor reports it.

    A capture that stored something reports UPDATED. One that stored nothing
    reports NONE, or UPDATED when it still refreshed the provider session.
    """
    require_terminal_receipt_match_any_effect(
        receipt,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(bucket_id),
        condition=OperationTerminalCondition.SUCCEEDED,
        effects=_STORED_CAPTURE_EFFECTS if stored else _UNSTORED_CAPTURE_EFFECTS,
        message=message,
    )
    require_succeeded_receipt_references(receipt, message=message)
