"""Exact-profile runtime bridges for enrolled AEAT Sync actions."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from ....adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ....application.live.filed_history_operation import (
    FILED_HISTORY_OPERATION_DEFINITION_ID,
    FiledHistoryOperationRequest,
    FiledHistoryPublicResultV1,
)
from ....application.live.notifications_read_operation import (
    NOTIFICATIONS_LIST_DEFINITION_ID,
    NotificationsListPublicResultV1,
    NotificationsListRequest,
)
from ....application.operations.frontend_projection import OperationPublicProjectionV1
from ....application.operations.frontend_requests import OperationObservationRefusalV1, OperationObservationSuccessV1
from ....application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
from ....application.operator_actions.models import ActionReference
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING,
    CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING,
    CensalOperationRequest,
    CensalOperationResult,
)
from ....application.user_profile.censal_prepare_operation import (
    CENSAL_PREPARE_OPERATION_DEFINITION_ID,
    CensalPrepareOperationProjection,
    CensalPrepareOperationRequest,
)
from ....core.operations import (
    OperationEffect,
    OperationInteractionKind,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ....core.time.clock import today_madrid
from ..operations.runtime_controller import RuntimeOperationController
from .models import AeatSyncOperationHandoffV1, AeatSyncOperationRequestV1

if TYPE_CHECKING:
    from pathlib import Path

    from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient

_FILED_HISTORY_ACTION_ID = "operator.live.filed.pull_all"
_FILED_HISTORY_ACTION = ActionReference(action_id=_FILED_HISTORY_ACTION_ID)
_NOTIFICATIONS_LIST_ACTION_ID = "operator.live.notifications.list"
_NOTIFICATIONS_LIST_ACTION = ActionReference(action_id=_NOTIFICATIONS_LIST_ACTION_ID)
_CENSAL_REVIEW_ACTION_ID = "operator.profile.edit"
_CENSAL_REVIEW_ACTION = ActionReference(action_id=_CENSAL_REVIEW_ACTION_ID)
_CONTRACT_TIMEOUT_SECONDS = 10.0
_CENSAL_PREPARE_TIMEOUT_SECONDS = 60.0


def _contract_matches(
    contract: OperationPublicDefinitionContractV1,
    *,
    definition_id: str,
    action: ActionReference | None,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
) -> bool:
    """Require one exact public operation/action and both schema identities."""
    return (
        contract.definition_id == definition_id
        and contract.action_reference == action
        and OperationFrontendProjection.TUI in contract.permitted_frontends
        and contract.request_schema
        == OperationSchemaIdentityV1.from_model(
            schema_id=definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        )
        and contract.result_schema
        == OperationSchemaIdentityV1.from_model(
            schema_id=definition_id + ".result",
            schema_version=1,
            model_type=result_type,
        )
        and not contract.ephemeral_secret_required
    )


def _censal_review_contract_matches(contract: OperationPublicDefinitionContractV1) -> bool:
    """Require the complete registered REVIEW contract used by the TUI modal."""
    return (
        _contract_matches(
            contract,
            definition_id=CENSAL_OPERATION_DEFINITION_ID,
            action=_CENSAL_REVIEW_ACTION,
            request_type=CensalOperationRequest,
            result_type=CensalOperationResult,
        )
        and contract.interaction_kinds == frozenset({OperationInteractionKind.REVIEW})
        and contract.review_projection_schema == CENSAL_REVIEW_PROJECTION_SCHEMA_BINDING.identity
        and contract.interaction_response_schema == CENSAL_REVIEW_RESPONSE_SCHEMA_BINDING.identity
    )


def _client_still_bound(
    client: RuntimeFrontendClient,
    *,
    profile_id: UUID,
    session_id: UUID,
) -> bool:
    """Keep internal preparation and the visible action on the originating worker."""
    return (
        client.frontend is OperationFrontendProjection.TUI
        and client.profile_id == profile_id
        and client.session_id == session_id
    )


async def _current_contract(
    client: RuntimeFrontendClient,
    *,
    definition_id: str,
    expected: OperationPublicDefinitionContractV1,
    profile_id: UUID,
    session_id: UUID,
    deadline: float,
) -> None:
    """Recheck an exact enrolled contract before allowing its submitted work to start."""
    if not _client_still_bound(client, profile_id=profile_id, session_id=session_id):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    current = await asyncio.to_thread(client.contract, definition_id, deadline=deadline)
    if not _client_still_bound(client, profile_id=profile_id, session_id=session_id) or current != expected:
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)


async def _prepare_censal_request(
    client: RuntimeFrontendClient,
    *,
    profile_id: UUID,
    session_id: UUID,
    contract: OperationPublicDefinitionContractV1,
) -> CensalOperationRequest:
    """Read the exact review baseline through the registered profile worker operation."""
    deadline = time.monotonic() + _CENSAL_PREPARE_TIMEOUT_SECONDS
    subject_ref = profile_operation_subject(str(profile_id))
    if not _client_still_bound(client, profile_id=profile_id, session_id=session_id):
        raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    controller = await RuntimeOperationController.submit(
        client,
        definition_id=CENSAL_PREPARE_OPERATION_DEFINITION_ID,
        subject_ref=subject_ref,
        payload=CensalPrepareOperationRequest(profile_id=profile_id),
        expected_session_id=session_id,
        deadline=deadline,
    )
    await _current_contract(
        client,
        definition_id=CENSAL_PREPARE_OPERATION_DEFINITION_ID,
        expected=contract,
        profile_id=profile_id,
        session_id=session_id,
        deadline=deadline,
    )
    await controller.start()

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
        observed = await controller.observe(0, page_limit=1)
        if isinstance(observed, OperationObservationRefusalV1):
            raise RuntimeFrontendRefusedError(observed.code.value)
        if not isinstance(observed, OperationObservationSuccessV1):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        projection = observed.projection
        expected_request_schema = OperationSchemaIdentityV1.from_model(
            schema_id=CENSAL_PREPARE_OPERATION_DEFINITION_ID + ".request",
            schema_version=1,
            model_type=CensalPrepareOperationRequest,
        )
        if (
            projection.operation_id != controller.operation_id
            or projection.definition_id != CENSAL_PREPARE_OPERATION_DEFINITION_ID
            or projection.subject_ref != subject_ref
            or projection.definition_contract != contract
            or contract.request_schema != expected_request_schema
            or projection.definition_contract.result_schema
            != OperationSchemaIdentityV1.from_model(
                schema_id=CENSAL_PREPARE_OPERATION_DEFINITION_ID + ".result",
                schema_version=1,
                model_type=CensalPrepareOperationProjection,
            )
            or not _client_still_bound(client, profile_id=profile_id, session_id=session_id)
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            if (
                projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
                or projection.effect is not OperationEffect.NONE
                or projection.result_ref is None
            ):
                raise RuntimeFrontendRefusedError(
                    projection.refusal_ref or projection.failure_error_code or "censo_preparation_not_successful"
                )
            prepared = await controller.read_settled_result(
                projection,
                CensalPrepareOperationProjection,
                result_version=1,
            )
            if (
                prepared.profile_id != profile_id
                or prepared.operation_request.baseline.profile_id != str(profile_id)
                or not _client_still_bound(client, profile_id=profile_id, session_id=session_id)
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return prepared.operation_request
        await asyncio.sleep(min(0.05, remaining))


@dataclass(frozen=True, slots=True, kw_only=True)
class _RuntimeNotificationsListController(RuntimeOperationController):
    """Resolve only the list result bound to its admitted contract and profile."""

    profile_id: UUID
    expected_contract: OperationPublicDefinitionContractV1

    async def read_notifications_list_result(
        self, projection: OperationPublicProjectionV1, /
    ) -> NotificationsListPublicResultV1:
        """Return exact-profile public summaries from a settled list operation."""
        if (
            self.client.frontend is not OperationFrontendProjection.TUI
            or self.client.profile_id != self.profile_id
            or self.client.session_id != self.session_id
            or projection.definition_id != NOTIFICATIONS_LIST_DEFINITION_ID
            or projection.definition_contract != self.expected_contract
            or projection.subject_ref != profile_operation_subject(str(self.profile_id))
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        result = await self.read_settled_result(
            projection,
            NotificationsListPublicResultV1,
            result_version=1,
        )
        if result.bucket_id != str(self.profile_id) or result.count != len(result.rows):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return result


def compose_runtime_aeat_sync_handoff(
    client: RuntimeFrontendClient,
    *,
    output_root: Path,
) -> tuple[AeatSyncOperationHandoffV1 | None, OperationPublicContractSetV1 | None]:
    """Bind only the enrolled AEAT Sync operations to the originating TUI session.

    Each action remains independently unavailable unless its exact public
    contract, action join, TUI permission, request schema, and result schema
    compose in this session. The handoff accepts only those admitted pairs and
    starts the selected operation before returning its modal controller.
    """
    if client.frontend is not OperationFrontendProjection.TUI:
        return None, None
    profile_id, session_id = client.profile_id, client.session_id
    candidates = (
        (
            FILED_HISTORY_OPERATION_DEFINITION_ID,
            _FILED_HISTORY_ACTION,
            FiledHistoryOperationRequest,
            FiledHistoryPublicResultV1,
        ),
        (
            NOTIFICATIONS_LIST_DEFINITION_ID,
            _NOTIFICATIONS_LIST_ACTION,
            NotificationsListRequest,
            NotificationsListPublicResultV1,
        ),
    )
    admitted: dict[str, OperationPublicDefinitionContractV1] = {}
    for definition_id, action, request_type, result_type in candidates:
        try:
            contract = client.contract(
                definition_id,
                deadline=time.monotonic() + _CONTRACT_TIMEOUT_SECONDS,
            )
        except (RuntimeFrontendRefusedError, RuntimeRefusalError):
            continue
        if not _client_still_bound(client, profile_id=profile_id, session_id=session_id):
            return None, None
        if _contract_matches(
            contract,
            definition_id=definition_id,
            action=action,
            request_type=request_type,
            result_type=result_type,
        ):
            admitted[definition_id] = contract

    # CENSO review is exposed only when its worker-side baseline preparation is
    # also admitted. The preparation operation has no user action join and is
    # kept out of the screen's action contract set.
    prepare_contract: OperationPublicDefinitionContractV1 | None = None
    try:
        candidate_prepare_contract = client.contract(
            CENSAL_PREPARE_OPERATION_DEFINITION_ID,
            deadline=time.monotonic() + _CONTRACT_TIMEOUT_SECONDS,
        )
    except (RuntimeFrontendRefusedError, RuntimeRefusalError):
        candidate_prepare_contract = None
    if not _client_still_bound(client, profile_id=profile_id, session_id=session_id):
        return None, None
    if candidate_prepare_contract is not None and _contract_matches(
        candidate_prepare_contract,
        definition_id=CENSAL_PREPARE_OPERATION_DEFINITION_ID,
        action=None,
        request_type=CensalPrepareOperationRequest,
        result_type=CensalPrepareOperationProjection,
    ):
        prepare_contract = candidate_prepare_contract

    if prepare_contract is not None:
        try:
            candidate_censal_contract = client.contract(
                CENSAL_OPERATION_DEFINITION_ID,
                deadline=time.monotonic() + _CONTRACT_TIMEOUT_SECONDS,
            )
        except (RuntimeFrontendRefusedError, RuntimeRefusalError):
            candidate_censal_contract = None
        if not _client_still_bound(client, profile_id=profile_id, session_id=session_id):
            return None, None
        if candidate_censal_contract is not None and _censal_review_contract_matches(candidate_censal_contract):
            admitted[CENSAL_OPERATION_DEFINITION_ID] = candidate_censal_contract

    if not admitted:
        return None, None
    operation_contracts = OperationPublicContractSetV1.build(tuple(admitted.values()))

    async def handoff(request: AeatSyncOperationRequestV1, /) -> RuntimeOperationController:
        subject_ref = profile_operation_subject(str(profile_id))
        if request.action == _FILED_HISTORY_ACTION and request.operation == FILED_HISTORY_OPERATION_DEFINITION_ID:
            definition_id = FILED_HISTORY_OPERATION_DEFINITION_ID
            contract = admitted.get(definition_id)
            payload = FiledHistoryOperationRequest(
                profile_id=profile_id,
                output_root=output_root,
                today=today_madrid(),
                limit=None,
                dry_run=False,
            )
        elif request.action == _NOTIFICATIONS_LIST_ACTION and request.operation == NOTIFICATIONS_LIST_DEFINITION_ID:
            definition_id = NOTIFICATIONS_LIST_DEFINITION_ID
            contract = admitted.get(definition_id)
            payload = NotificationsListRequest(profile_id=profile_id)
        elif request.action == _CENSAL_REVIEW_ACTION and request.operation == CENSAL_OPERATION_DEFINITION_ID:
            definition_id = CENSAL_OPERATION_DEFINITION_ID
            contract = admitted.get(definition_id)
            if contract is None or prepare_contract is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
            payload = await _prepare_censal_request(
                client,
                profile_id=profile_id,
                session_id=session_id,
                contract=prepare_contract,
            )
            subject_ref = str(profile_id)
        else:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if contract is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        await _current_contract(
            client,
            definition_id=definition_id,
            expected=contract,
            profile_id=profile_id,
            session_id=session_id,
            deadline=time.monotonic() + _CONTRACT_TIMEOUT_SECONDS,
        )

        controller = await RuntimeOperationController.submit(
            client,
            definition_id=definition_id,
            subject_ref=subject_ref,
            payload=payload,
            expected_session_id=session_id,
        )
        # Submission is inert until start. Recheck the immutable contract after
        # the controller's own contract-bound submission before authorizing it
        # to execute, so a session whose installed contract changed stays idle.
        await _current_contract(
            client,
            definition_id=definition_id,
            expected=contract,
            profile_id=profile_id,
            session_id=session_id,
            deadline=time.monotonic() + _CONTRACT_TIMEOUT_SECONDS,
        )

        if definition_id == NOTIFICATIONS_LIST_DEFINITION_ID:
            controller = _RuntimeNotificationsListController(
                client=client,
                operation_id=controller.operation_id,
                session_id=session_id,
                deadline=controller.deadline,
                profile_id=profile_id,
                expected_contract=contract,
            )
        await controller.start()
        return controller

    return handoff, operation_contracts


__all__ = ["compose_runtime_aeat_sync_handoff"]
