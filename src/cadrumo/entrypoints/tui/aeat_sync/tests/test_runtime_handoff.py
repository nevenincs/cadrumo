"""Exact-profile supervision for the enrolled AEAT Sync filed-history action."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient, RuntimeFrontendRefusedError
from cadrumo.application.live.filed_history_operation import (
    FILED_HISTORY_OPERATION_DEFINITION_ID,
    FiledHistoryOperationRequest,
)
from cadrumo.application.live.notifications_read_operation import (
    NOTIFICATIONS_LIST_DEFINITION_ID,
    NotificationsListRequest,
)
from cadrumo.application.operations.frontend_projection import (
    OperationNoPendingInteractionV1,
    OperationPublicProjectionV1,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationSuccessV1,
    OperationPublicEventPageV1,
    OperationPublicPhaseEventV1,
    OperationPublicTerminalEventV1,
)
from cadrumo.application.operations.persistence.replay import OperationReplayStatus
from cadrumo.application.operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionContractV1,
)
from cadrumo.application.operator_actions.models import ActionReference
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.censal_operation import (
    CENSAL_OPERATION_DEFINITION_ID,
    CensalFieldIntent,
    CensalOperationRequest,
    CensalProfileBaseline,
    CensalReviewedFieldIntent,
)
from cadrumo.application.user_profile.censal_prepare_operation import (
    CENSAL_PREPARE_OPERATION_DEFINITION_ID,
    CensalPrepareFieldProjection,
    CensalPrepareFieldState,
    CensalPrepareOperationProjection,
    CensalPrepareOperationRequest,
)
from cadrumo.application.user_profile.censo_sync import CENSAL_ADOPTABLE_PATHS
from cadrumo.core.hashing import content_hash_hex
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.tui.aeat_sync.models import AeatSyncOperationRequestV1
from cadrumo.entrypoints.tui.aeat_sync.runtime_handoff import compose_runtime_aeat_sync_handoff
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PROFILE_ID = UUID("aa000000-0000-4000-8000-0000000000aa")
_SESSION_ID = UUID("bb000000-0000-4000-8000-0000000000bb")
_TODAY = date(2026, 9, 29)
_NOW = datetime(2026, 9, 29, tzinfo=UTC)
_FILED_ACTION = ActionReference(action_id="operator.live.filed.pull_all")
_NOTIFICATIONS_LIST_ACTION = ActionReference(action_id="operator.live.notifications.list")
_CENSAL_REVIEW_ACTION = ActionReference(action_id="operator.profile.edit")


class _RuntimeClient:
    frontend = OperationFrontendProjection.TUI
    profile_id = _PROFILE_ID
    session_id = _SESSION_ID

    def __init__(self, *contracts: OperationPublicDefinitionContractV1) -> None:
        self._contracts = {contract.definition_id: contract for contract in contracts}
        self.contract_reads: list[tuple[str, float]] = []

    def contract(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionContractV1:
        self.contract_reads.append((definition_id, deadline))
        try:
            return self._contracts[definition_id]
        except KeyError:
            raise RuntimeFrontendRefusedError("operation unavailable") from None


class _StartedController:
    operation_id = "3" * 64

    def __init__(self, events: list[str] | None = None) -> None:
        self.started = False
        self.events = events

    async def start(self) -> str:
        self.started = True
        if self.events is not None:
            self.events.append("start:censo-review")
        return self.operation_id


class _PreparedController:
    def __init__(
        self,
        *,
        client: RuntimeFrontendClient,
        contract: OperationPublicDefinitionContractV1,
        profile_id: UUID,
        prepared: CensalPrepareOperationProjection,
        events: list[str],
    ) -> None:
        self.client = client
        self.contract = contract
        self.profile_id = profile_id
        self.prepared = prepared
        self.events = events
        self.operation_id = "5" * 64
        self.session_id = _SESSION_ID

    async def start(self) -> str:
        self.events.append("start:censo-prepare")
        return self.operation_id

    async def observe(self, after_cursor: int, *, page_limit: int = 256) -> OperationObservationSuccessV1:
        self.events.append("observe:censo-prepare")
        assert after_cursor == 0
        assert page_limit == 1
        contract_set_digest = "c" * 64
        terminal_result_ref = "censo-review:" + "d" * 64 + ":applied"
        projection = OperationPublicProjectionV1(
            operation_id=self.operation_id,
            definition_id=CENSAL_PREPARE_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(self.profile_id)),
            revision=2,
            anchor_cursor=2,
            definition_contract=self.contract,
            contract_set_digest=contract_set_digest,
            lifecycle=OperationLifecycle.TERMINAL,
            terminal_condition=OperationTerminalCondition.SUCCEEDED,
            effect=OperationEffect.NONE,
            phase_code="user-profile.censo-prepare.read",
            started_at=_NOW,
            updated_at=_NOW,
            progress=None,
            close_policy=self.contract.close_policy,
            cancellation=self.contract.cancellation,
            cancellable_now=False,
            cancellation_requested=False,
            cancellation_acknowledged=False,
            execution_deadline_at=None,
            cleanup_deadline_at=None,
            pending_interaction=OperationNoPendingInteractionV1(),
            result_ref=terminal_result_ref,
            refusal_ref=None,
            failure_error_code=None,
            diagnostic_ref=None,
        )
        event_page = OperationPublicEventPageV1(
            operation_id=self.operation_id,
            anchor_cursor=2,
            requested_cursor=0,
            status=OperationReplayStatus.PAGE,
            events=(
                OperationPublicPhaseEventV1(
                    revision=1,
                    sequence=1,
                    timestamp=_NOW,
                    code="user-profile.censo-prepare.read",
                    phase_code="user-profile.censo-prepare.read",
                ),
                OperationPublicTerminalEventV1(
                    revision=2,
                    sequence=2,
                    timestamp=_NOW,
                    code="operation.terminal",
                    condition=OperationTerminalCondition.SUCCEEDED,
                    effect=OperationEffect.NONE,
                    result_ref=terminal_result_ref,
                    refusal_ref=None,
                    failure_error_code=None,
                    diagnostic_ref=None,
                ),
            ),
            next_cursor=2,
            restart_cursor=None,
        )
        return OperationObservationSuccessV1(projection=projection, event_page=event_page)

    async def read_settled_result(
        self,
        projection: OperationPublicProjectionV1,
        result_type: type[BaseModel],
        *,
        result_version: int,
    ) -> CensalPrepareOperationProjection:
        self.events.append("read:censo-prepare")
        assert projection.operation_id == self.operation_id
        assert result_type is CensalPrepareOperationProjection
        assert result_version == 1
        return self.prepared


def _prepared_projection(profile_id: UUID) -> CensalPrepareOperationProjection:
    baseline = CensalProfileBaseline(
        profile_id=str(profile_id),
        record_revision=3,
        content_digest=content_hash_hex({"profile_id": str(profile_id), "revision": 3}),
    )
    operation_request = CensalOperationRequest(
        baseline=baseline,
        field_intents=tuple(
            CensalReviewedFieldIntent(path=path, intent=CensalFieldIntent.ADOPT) for path in CENSAL_ADOPTABLE_PATHS
        ),
    )
    return CensalPrepareOperationProjection(
        profile_id=profile_id,
        operation_request=operation_request,
        effective_fields=tuple(
            CensalPrepareFieldProjection(path=path, state=CensalPrepareFieldState.UNSET)
            for path in CENSAL_ADOPTABLE_PATHS
        ),
    )


def _install_censal_bridge(
    monkeypatch: pytest.MonkeyPatch,
    client: _RuntimeClient,
    prepared: CensalPrepareOperationProjection,
) -> tuple[list[str], list[tuple[RuntimeFrontendClient, dict[str, object]]], _StartedController]:
    events: list[str] = []
    submitted: list[tuple[RuntimeFrontendClient, dict[str, object]]] = []
    started = _StartedController(events)
    prepare_contract = client._contracts[CENSAL_PREPARE_OPERATION_DEFINITION_ID]

    async def submit(
        _controller_type: type[RuntimeOperationController],
        received_client: RuntimeFrontendClient,
        **kwargs: object,
    ) -> object:
        definition_id = str(kwargs["definition_id"])
        events.append(f"submit:{definition_id}")
        submitted.append((received_client, kwargs))
        if definition_id == CENSAL_PREPARE_OPERATION_DEFINITION_ID:
            return _PreparedController(
                client=received_client,
                contract=prepare_contract,
                profile_id=_PROFILE_ID,
                prepared=prepared,
                events=events,
            )
        return started

    async def start(controller: RuntimeOperationController) -> str:
        events.append("start:censo-review")
        controller_id = getattr(controller, "operation_id", started.operation_id)
        return str(controller_id)

    monkeypatch.setattr(RuntimeOperationController, "submit", classmethod(submit))
    monkeypatch.setattr(RuntimeOperationController, "start", start)
    return events, submitted, started


def _contract(definition_id: str) -> OperationPublicDefinitionContractV1:
    return build_production_operation_registry().lookup_public_contract(definition_id)


def test_runtime_handoff_submits_exact_profile_and_starts_before_return(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _RuntimeClient(_contract(FILED_HISTORY_OPERATION_DEFINITION_ID))
    output_root = tmp_path / "filed-declarations"
    submitted: list[tuple[object, dict[str, object]]] = []
    started = _StartedController()

    async def submit(
        _controller_type: type[RuntimeOperationController],
        received_client: RuntimeFrontendClient,
        **kwargs: object,
    ) -> _StartedController:
        submitted.append((received_client, kwargs))
        return started

    monkeypatch.setattr(RuntimeOperationController, "submit", classmethod(submit))
    monkeypatch.setattr("cadrumo.entrypoints.tui.aeat_sync.runtime_handoff.today_madrid", lambda: _TODAY)

    handoff, contracts = compose_runtime_aeat_sync_handoff(cast(RuntimeFrontendClient, client), output_root=output_root)
    assert handoff is not None
    assert contracts is not None
    assert tuple(contract.definition_id for contract in contracts.definitions) == (
        FILED_HISTORY_OPERATION_DEFINITION_ID,
    )
    assert client.contract_reads[0][0] == FILED_HISTORY_OPERATION_DEFINITION_ID

    request = AeatSyncOperationRequestV1(action=_FILED_ACTION, operation=FILED_HISTORY_OPERATION_DEFINITION_ID)
    controller = asyncio.run(handoff(request))

    assert controller is started
    assert started.started
    assert len(submitted) == 1
    received_client, options = submitted[0]
    assert received_client is client
    assert options == {
        "definition_id": FILED_HISTORY_OPERATION_DEFINITION_ID,
        "subject_ref": profile_operation_subject(str(_PROFILE_ID)),
        "payload": FiledHistoryOperationRequest(
            profile_id=_PROFILE_ID,
            output_root=output_root,
            today=_TODAY,
            limit=None,
            dry_run=False,
        ),
        "expected_session_id": _SESSION_ID,
    }


def test_notifications_list_handoff_submits_the_bound_profile_and_starts_its_result_reader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _RuntimeClient(
        _contract(FILED_HISTORY_OPERATION_DEFINITION_ID),
        _contract(NOTIFICATIONS_LIST_DEFINITION_ID),
    )
    submitted: list[tuple[object, dict[str, object]]] = []
    started: list[RuntimeOperationController] = []

    async def submit(
        _controller_type: type[RuntimeOperationController],
        received_client: RuntimeFrontendClient,
        **kwargs: object,
    ) -> RuntimeOperationController:
        submitted.append((received_client, kwargs))
        return RuntimeOperationController(
            client=received_client,
            operation_id="4" * 64,
            session_id=_SESSION_ID,
        )

    async def start(controller: RuntimeOperationController) -> str:
        started.append(controller)
        return controller.operation_id

    monkeypatch.setattr(RuntimeOperationController, "submit", classmethod(submit))
    monkeypatch.setattr(RuntimeOperationController, "start", start)

    handoff, contracts = compose_runtime_aeat_sync_handoff(
        cast(RuntimeFrontendClient, client), output_root=tmp_path / "filed-declarations"
    )
    assert handoff is not None
    assert contracts is not None
    assert tuple(contract.definition_id for contract in contracts.definitions) == (
        FILED_HISTORY_OPERATION_DEFINITION_ID,
        NOTIFICATIONS_LIST_DEFINITION_ID,
    )

    controller = asyncio.run(
        handoff(
            AeatSyncOperationRequestV1(
                action=_NOTIFICATIONS_LIST_ACTION,
                operation=NOTIFICATIONS_LIST_DEFINITION_ID,
            )
        )
    )

    assert len(submitted) == 1
    received_client, options = submitted[0]
    assert received_client is client
    assert options == {
        "definition_id": NOTIFICATIONS_LIST_DEFINITION_ID,
        "subject_ref": profile_operation_subject(str(_PROFILE_ID)),
        "payload": NotificationsListRequest(profile_id=_PROFILE_ID),
        "expected_session_id": _SESSION_ID,
    }
    assert started == [controller]
    assert callable(getattr(controller, "read_notifications_list_result", None))


@pytest.mark.parametrize(
    "operation_request",
    (
        AeatSyncOperationRequestV1(
            action=ActionReference(action_id="operator.profile.edit"),
            operation="user-profile.censo-preview",
        ),
        AeatSyncOperationRequestV1(
            action=_FILED_ACTION,
            operation="live.filed-list",
        ),
        AeatSyncOperationRequestV1(
            action=_NOTIFICATIONS_LIST_ACTION,
            operation="live.notifications.show",
        ),
    ),
)
def test_runtime_handoff_refuses_other_action_operation_pairs_before_submission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    operation_request: AeatSyncOperationRequestV1,
) -> None:
    client = _RuntimeClient(_contract(FILED_HISTORY_OPERATION_DEFINITION_ID))
    handoff, _contracts = compose_runtime_aeat_sync_handoff(
        cast(RuntimeFrontendClient, client), output_root=tmp_path / "filed-declarations"
    )
    assert handoff is not None
    submitted: list[object] = []

    async def submit(
        _controller_type: type[RuntimeOperationController],
        received_client: RuntimeFrontendClient,
        **kwargs: object,
    ) -> _StartedController:
        submitted.append((received_client, kwargs))
        return _StartedController()

    monkeypatch.setattr(RuntimeOperationController, "submit", classmethod(submit))

    with pytest.raises(RuntimeRefusalError) as refusal:
        asyncio.run(handoff(operation_request))

    assert refusal.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert submitted == []


def test_runtime_handoff_leaves_action_unavailable_for_wrong_installed_contract() -> None:
    forged_contract = _contract(FILED_HISTORY_OPERATION_DEFINITION_ID).model_copy(
        update={"action_reference": ActionReference(action_id="operator.profile.edit")}
    )
    client = _RuntimeClient(forged_contract)

    handoff, contracts = compose_runtime_aeat_sync_handoff(
        cast(RuntimeFrontendClient, client), output_root=Path("filed-declarations")
    )

    assert handoff is None
    assert contracts is None


def test_notifications_list_action_stays_unavailable_for_wrong_contract() -> None:
    forged_contract = _contract(NOTIFICATIONS_LIST_DEFINITION_ID).model_copy(
        update={"request_schema": _contract(FILED_HISTORY_OPERATION_DEFINITION_ID).request_schema}
    )
    client = _RuntimeClient(forged_contract)

    handoff, contracts = compose_runtime_aeat_sync_handoff(
        cast(RuntimeFrontendClient, client), output_root=Path("filed-declarations")
    )

    assert handoff is None
    assert contracts is None


def test_censal_handoff_prepares_worker_baseline_before_review_submission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _RuntimeClient(
        _contract(CENSAL_PREPARE_OPERATION_DEFINITION_ID),
        _contract(CENSAL_OPERATION_DEFINITION_ID),
    )
    prepared = _prepared_projection(_PROFILE_ID)
    events, submitted, started = _install_censal_bridge(monkeypatch, client, prepared)
    handoff, contracts = compose_runtime_aeat_sync_handoff(
        cast(RuntimeFrontendClient, client), output_root=tmp_path / "filed-declarations"
    )

    assert handoff is not None
    assert contracts is not None
    assert tuple(contract.definition_id for contract in contracts.definitions) == (CENSAL_OPERATION_DEFINITION_ID,)
    controller = asyncio.run(
        handoff(
            AeatSyncOperationRequestV1(
                action=_CENSAL_REVIEW_ACTION,
                operation=CENSAL_OPERATION_DEFINITION_ID,
            )
        )
    )

    assert controller is started
    assert len(submitted) == 2
    prepare_client, prepare_options = submitted[0]
    assert prepare_client is client
    assert set(prepare_options) == {
        "definition_id",
        "subject_ref",
        "payload",
        "expected_session_id",
        "deadline",
    }
    assert prepare_options["definition_id"] == CENSAL_PREPARE_OPERATION_DEFINITION_ID
    assert prepare_options["subject_ref"] == profile_operation_subject(str(_PROFILE_ID))
    assert prepare_options["payload"] == CensalPrepareOperationRequest(profile_id=_PROFILE_ID)
    assert prepare_options["expected_session_id"] == _SESSION_ID
    assert isinstance(prepare_options["deadline"], float)
    review_client, review_options = submitted[1]
    assert review_client is client
    assert review_options == {
        "definition_id": CENSAL_OPERATION_DEFINITION_ID,
        "subject_ref": str(_PROFILE_ID),
        "payload": prepared.operation_request,
        "expected_session_id": _SESSION_ID,
    }
    assert events == [
        f"submit:{CENSAL_PREPARE_OPERATION_DEFINITION_ID}",
        "start:censo-prepare",
        "observe:censo-prepare",
        "read:censo-prepare",
        f"submit:{CENSAL_OPERATION_DEFINITION_ID}",
        "start:censo-review",
    ]


def test_censal_handoff_refuses_a_foreign_worker_prepared_profile_before_review_submission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    client = _RuntimeClient(
        _contract(CENSAL_PREPARE_OPERATION_DEFINITION_ID),
        _contract(CENSAL_OPERATION_DEFINITION_ID),
    )
    foreign_profile = UUID("cc000000-0000-4000-8000-0000000000cc")
    events, submitted, _started = _install_censal_bridge(
        monkeypatch,
        client,
        _prepared_projection(foreign_profile),
    )
    handoff, _contracts = compose_runtime_aeat_sync_handoff(
        cast(RuntimeFrontendClient, client), output_root=tmp_path / "filed-declarations"
    )
    assert handoff is not None

    with pytest.raises(RuntimeRefusalError) as refusal:
        asyncio.run(
            handoff(
                AeatSyncOperationRequestV1(
                    action=_CENSAL_REVIEW_ACTION,
                    operation=CENSAL_OPERATION_DEFINITION_ID,
                )
            )
        )

    assert refusal.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert [options["definition_id"] for _received_client, options in submitted] == [
        CENSAL_PREPARE_OPERATION_DEFINITION_ID
    ]
    assert events == [
        f"submit:{CENSAL_PREPARE_OPERATION_DEFINITION_ID}",
        "start:censo-prepare",
        "observe:censo-prepare",
        "read:censo-prepare",
    ]
