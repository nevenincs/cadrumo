"""The MCP server states each operation's subject form and derives the subject on execute."""

from __future__ import annotations

from typing import Any, NoReturn, cast, override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from cadrumo.application.modelo.revision_operation_access import compose_modelo_revision_access
from cadrumo.application.modelo.revision_snapshot_operation import (
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
    build_modelo_work_revision_snapshot_definition,
    build_modelo_work_revision_snapshot_registration,
)
from cadrumo.application.operations.registry import OperationRegistry
from cadrumo.application.runtime.operation_access import RuntimeOperationSubmit
from cadrumo.application.workflow.run_read_operation import (
    WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
    build_workflow_run_read_definition,
    build_workflow_run_read_registration,
)
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session
from cadrumo_harness.mcp.tests.test_operation_search_tool import _AdmittedClient

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_RUN_ID = "a" * 16
_REVISION_ID = "b" * 64
_WORK_UNIT_ID = "c" * 64

_PROFILE_FORM = {"kind": "profile", "payload_path": [], "literal": None}
_RUN_FORM = {"kind": "payload_field", "payload_path": ["run_id"], "literal": None}
_STORED_FORM = {"kind": "stored_work_unit", "payload_path": ["calculation_revision_id"], "literal": None}
_FORMS = {
    AUTH_READ_OPERATION_DEFINITION_ID: _PROFILE_FORM,
    MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID: _STORED_FORM,
    WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID: _RUN_FORM,
}


def _unused_ports(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("no executor or resolver runs behind a transport that never answers")


def _registry() -> OperationRegistry:
    """Compose the real contracts of one operation of each form a client meets."""
    auth = build_auth_read_definition(_unused_ports)
    snapshot = build_modelo_work_revision_snapshot_definition(_unused_ports)
    run = build_workflow_run_read_definition(_unused_ports)
    return OperationRegistry(
        definitions=(auth, snapshot, run),
        public_registrations=(
            build_auth_read_registration(auth),
            build_modelo_work_revision_snapshot_registration(
                snapshot, access_resolver=compose_modelo_revision_access(_unused_ports)
            ),
            build_workflow_run_read_registration(run, _unused_ports),
        ),
    )


class _RecordingClient(_AdmittedClient):
    """The admitted lease, keeping each submission it is handed before its transport times out."""

    def __init__(self, profile_id: UUID) -> None:
        super().__init__(profile_id, _registry())
        self.submitted: list[RuntimeOperationSubmit] = []

    @override
    def operation(self, request: object, *, deadline: float) -> NoReturn:
        if isinstance(request, RuntimeOperationSubmit):
            self.submitted.append(request)
        super().operation(request, deadline=deadline)


async def _execute(client: _RecordingClient, arguments: dict[str, Any]) -> dict[str, Any]:
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        return await adapter.call("execute", arguments)
    finally:
        await adapter.close()


def _run_payload(profile_id: UUID) -> dict[str, object]:
    return {"profile_id": str(profile_id), "run_id": _RUN_ID}


def _snapshot_payload(profile_id: UUID) -> dict[str, object]:
    return {"profile_id": str(profile_id), "calculation_revision_id": _REVISION_ID}


@pytest.mark.anyio
async def test_describe_and_search_state_the_subject_form_of_every_operation() -> None:
    client = _RecordingClient(uuid4())
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        found = await adapter.call("search", {})
        described = {
            definition_id: await adapter.call("describe", {"definition_id": definition_id}) for definition_id in _FORMS
        }
    finally:
        await adapter.close()

    rows = cast("list[dict[str, object]]", found["operations"])
    assert {str(row["definition_id"]): row["subject_reference"] for row in rows} == _FORMS
    for definition_id, form in _FORMS.items():
        description = cast("dict[str, dict[str, object]]", described[definition_id]["description"])
        assert description["contract"]["subject_reference"] == form, definition_id


@pytest.mark.anyio
async def test_execute_without_a_subject_submits_the_admitted_profile_for_a_profile_operation() -> None:
    profile_id = UUID("5aa00000-0000-4000-8000-0000000000aa")
    client = _RecordingClient(profile_id)

    result = await _execute(client, {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID, "payload": {"kind": "status"}})

    assert result["outcome"] == "unresolved"
    assert [item.subject_ref for item in client.submitted] == ["profile:5aa00000-0000-4000-8000-0000000000aa"]


@pytest.mark.anyio
async def test_execute_without_a_subject_submits_the_payload_field_the_contract_names() -> None:
    client = _RecordingClient(uuid4())

    result = await _execute(
        client,
        {"definition_id": WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID, "payload": _run_payload(client.profile_id)},
    )

    assert result["outcome"] == "unresolved"
    assert [item.subject_ref for item in client.submitted] == [_RUN_ID]


@pytest.mark.anyio
async def test_execute_accepts_a_supplied_subject_that_is_the_declared_one() -> None:
    client = _RecordingClient(uuid4())

    result = await _execute(
        client,
        {
            "definition_id": WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
            "subject_ref": _RUN_ID,
            "payload": _run_payload(client.profile_id),
        },
    )

    assert result["outcome"] == "unresolved"
    assert [item.subject_ref for item in client.submitted] == [_RUN_ID]


@pytest.mark.anyio
async def test_execute_refuses_a_subject_that_contradicts_a_profile_operation_before_submitting() -> None:
    client = _RecordingClient(uuid4())

    result = await _execute(
        client,
        {
            "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
            "subject_ref": str(client.profile_id),
            "payload": {"kind": "status"},
        },
    )

    assert result == {
        "outcome": "refused",
        "code": "invalid_request",
        "message": (
            "subject_ref does not match this operation's subject, which is the admitted profile; "
            "leave subject_ref out and it is derived"
        ),
    }
    assert client.submitted == []


@pytest.mark.anyio
async def test_execute_refuses_a_subject_that_contradicts_the_payload_field_before_submitting() -> None:
    client = _RecordingClient(uuid4())

    result = await _execute(
        client,
        {
            "definition_id": WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
            "subject_ref": f"profile:{client.profile_id}",
            "payload": _run_payload(client.profile_id),
        },
    )

    assert result == {
        "outcome": "refused",
        "code": "invalid_request",
        "message": (
            "subject_ref does not match this operation's subject, which is payload field run_id; "
            "leave subject_ref out and it is derived"
        ),
    }
    assert client.submitted == []


@pytest.mark.anyio
async def test_execute_refuses_a_payload_without_the_field_its_subject_is_read_from() -> None:
    client = _RecordingClient(uuid4())

    result = await _execute(
        client,
        {
            "definition_id": WORKFLOW_RUN_READ_OPERATION_DEFINITION_ID,
            "subject_ref": _RUN_ID,
            "payload": {"profile_id": str(client.profile_id)},
        },
    )

    assert result == {
        "outcome": "refused",
        "code": "invalid_request",
        "message": "payload does not carry run_id, which is this operation's subject",
    }
    assert client.submitted == []


@pytest.mark.anyio
async def test_execute_refuses_a_stored_work_unit_operation_without_a_subject_and_names_the_key_field() -> None:
    client = _RecordingClient(uuid4())
    arguments: dict[str, Any] = {
        "definition_id": MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
        "payload": _snapshot_payload(client.profile_id),
    }
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            refused = await sdk.call_tool("execute", arguments)
    finally:
        await adapter.close()

    assert refused.is_error is True
    assert refused.structured_content == {
        "outcome": "refused",
        "code": "invalid_request",
        "message": (
            "subject_ref is required: it is the work unit that owns the record named by "
            "payload field calculation_revision_id"
        ),
    }
    assert client.submitted == []


@pytest.mark.anyio
async def test_execute_passes_on_the_work_unit_a_client_supplies_for_a_stored_record() -> None:
    client = _RecordingClient(uuid4())

    result = await _execute(
        client,
        {
            "definition_id": MODELO_WORK_REVISION_SNAPSHOT_OPERATION_DEFINITION_ID,
            "subject_ref": _WORK_UNIT_ID,
            "payload": _snapshot_payload(client.profile_id),
        },
    )

    assert result["outcome"] == "unresolved"
    assert [item.subject_ref for item in client.submitted] == [_WORK_UNIT_ID]
