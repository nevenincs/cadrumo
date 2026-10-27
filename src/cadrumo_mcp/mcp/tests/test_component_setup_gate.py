"""Recovery offers follow a single registered local status read."""

from __future__ import annotations

import time
from typing import Any, cast
from uuid import uuid4

import pytest

from cadrumo.application.components_operations import (
    COMPONENTS_OPERATION_SUBJECT,
    COMPONENTS_STATUS_OPERATION_ID,
    ProvisionOutcome,
    ProvisionReadRequest,
    ProvisionResult,
)
from cadrumo.application.dependency_contracts import (
    DependencyCheckMode,
    DependencyItemKind,
    DependencyRecoveryAction,
    DependencyState,
    DependencyStatusRow,
)
from cadrumo.application.operator_actions.projection import PreconditionVerdictSnapshot
from cadrumo.application.provisioning_browser import browser_not_provisioned_verdict
from cadrumo.core.operations import OperationEffect
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.transport.frontend_client import FrontendClient

from .. import component_setup
from ..component_setup import gate_setup_actions
from ..runtime_adapter import RuntimeMcpAdapter
from .test_result_page_tool import _auth_registry, _observed_operation_id, _ObservedClient, _settled_request

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_BROWSER = "operator.provision.browser"
_LOCAL_AI = "operator.provision.local_ai"


def _rows() -> tuple[DependencyStatusRow, ...]:
    return (
        DependencyStatusRow(
            item_id="browser",
            kind=DependencyItemKind.BROWSER,
            mode=DependencyCheckMode.QUICK,
            state=DependencyState.ABSENT,
            recovery=DependencyRecoveryAction.SET_UP,
            recovery_action_id=_BROWSER,
        ),
        DependencyStatusRow(
            item_id="local_ai",
            kind=DependencyItemKind.LOCAL_AI,
            mode=DependencyCheckMode.QUICK,
            state=DependencyState.ABSENT,
            recovery=DependencyRecoveryAction.SET_UP_IN_DESKTOP,
            recovery_action_id=_LOCAL_AI,
        ),
    )


def _status(monkeypatch: pytest.MonkeyPatch, *, fail: bool = False) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def run(
        client: FrontendClient, payload: ProvisionReadRequest, **options: Any
    ) -> RegisteredOperationCompletion[ProvisionResult]:
        del client
        calls.append({"payload": payload, **options})
        if fail:
            raise OSError("status unavailable")
        return RegisteredOperationCompletion(
            operation_id="a" * 64,
            projection=ProvisionResult(outcome=ProvisionOutcome.OK, rows=_rows()),
            effect=OperationEffect.NONE,
        )

    monkeypatch.setattr(component_setup, "run_registered_operation", run)
    return calls


def test_gate_uses_one_local_operation_and_the_typed_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _status(monkeypatch)
    named, held = gate_setup_actions(
        cast(FrontendClient, object()),
        [_BROWSER, _LOCAL_AI, _BROWSER, "operator.other"],
        language=lambda: "en",
        deadline=time.monotonic() + 10,
        status_allowed=True,
    )
    assert named == [_BROWSER, "operator.other"]
    assert held == [
        {
            "recovery_action_id": _LOCAL_AI,
            "item_id": "local_ai",
            "state": "absent",
            "sentence": "Local AI: Not set up yet. Set it up in the Cadrumo desktop app.",
        }
    ]
    assert len(calls) == 1
    assert calls[0]["definition_id"] == COMPONENTS_STATUS_OPERATION_ID
    assert calls[0]["subject_ref"] == COMPONENTS_OPERATION_SUBJECT
    assert calls[0]["payload"] == ProvisionReadRequest()
    assert calls[0]["result_type"] is ProvisionResult


def test_gate_suppresses_only_setup_when_status_unavailable_or_disallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _status(monkeypatch, fail=True)
    client = cast(FrontendClient, object())
    for allowed in (True, False):
        named, held = gate_setup_actions(
            client,
            [_BROWSER, "operator.other"],
            language=lambda: "en",
            deadline=time.monotonic() + 10,
            status_allowed=allowed,
        )
        assert named == ["operator.other"] and held == []
    assert len(calls) == 1


@pytest.mark.anyio
async def test_result_gates_repeated_verdicts_once_and_status_result_does_not_recurse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _status(monkeypatch)
    registry = _auth_registry()
    client = _ObservedClient(uuid4(), registry)
    verdict = PreconditionVerdictSnapshot.from_verdict(browser_not_provisioned_verdict({"chromium_installed": False}))
    client.document = {
        "outcome": "success",
        "projection": {
            "rows": [
                {"precondition_verdict": verdict.model_dump(mode="json")},
                {"precondition_verdict": verdict.model_dump(mode="json")},
            ]
        },
    }
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(FrontendClient, client))
    request = _settled_request(registry)
    try:
        reply = await adapter.call("result", {"result": {"operation_id": _observed_operation_id()}})
        assert reply["recovery_action_ids"] == [_BROWSER]
        assert len(calls) == 1
        schema = request.result_schema.model_copy(update={"schema_id": COMPONENTS_STATUS_OPERATION_ID + ".result"})
        status_request = request.model_copy(update={"result_schema": schema})
        await adapter.call("result", {"result": status_request.model_dump(mode="json")})
        assert len(calls) == 1
    finally:
        await adapter.close()
