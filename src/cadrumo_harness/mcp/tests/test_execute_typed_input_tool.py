"""The execute tool carries typed operator input where a contract declares it, and never a secret.

The adapter's own part is shown here: what it holds a call to before anything
is sent, which exchange each part of the call travels on, in what order, and
what it says back. An operation whose contract requires a secret is the
person's credential act, so the adapter sends nothing for it. The runtime's
answers are supplied by a connection double that keeps every exchange it is
handed, because whether a submission is admitted is the runtime's decision and
is proven against the real runtime where that runtime lives. The contracts are
the real registered ones.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, NoReturn, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from cadrumo.application.modelo.operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    build_modelo_edit_apply_definition,
    build_modelo_edit_apply_registration,
)
from cadrumo.application.operations.frontend_requests import OperationSubmissionReceiptV1
from cadrumo.application.operations.models import new_operation_id
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1, OperationRegistry
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationControl,
    RuntimeOperationFinancialInput,
    RuntimeOperationReply,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.user_profile.operations import (
    USER_PROFILE_OPERATION_DEFINITIONS,
    build_user_profile_operation_registrations,
)
from cadrumo.application.user_profile.profile_operation_contracts import PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID
from cadrumo_harness.mcp.protocol_contract import PERSON_ACT_REMEDY, PERSON_ACT_REQUIRED
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session
from cadrumo_harness.mcp.tests.test_operation_search_tool import _AdmittedClient

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_TYPED = "synthetic-export-text-7f3a"
_WORK_UNIT_ID = "c" * 64
_OPERATOR_INPUT: dict[str, object] = {"input_version": 2, "submission": {"synthetic": "operator input"}}


def _unused_ports(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("no executor or resolver runs behind a transport double")


def _registry() -> OperationRegistry:
    """Compose the real contracts of a plain read, a typed-secret operation and a typed-input operation."""
    auth = build_auth_read_definition(_unused_ports)
    export = next(
        item
        for item in USER_PROFILE_OPERATION_DEFINITIONS
        if item.definition_id == PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID
    )
    edit = build_modelo_edit_apply_definition(
        calculation_action_ports_factory=_unused_ports, receipt_repository_factory=_unused_ports
    )
    return OperationRegistry(
        definitions=(auth, edit, export),
        public_registrations=(
            build_auth_read_registration(auth),
            build_modelo_edit_apply_registration(edit),
            *build_user_profile_operation_registrations((export,)),
        ),
    )


class _AnsweringClient:
    """The admitted lease over a transport that answers, keeping each exchange in the order it was handed."""

    def __init__(self, profile_id: UUID) -> None:
        self._lease = _AdmittedClient(profile_id, _registry())
        self.profile_id, self.registry = profile_id, self._lease.registry
        self.frontend, self.session_id = self._lease.frontend, self._lease.session_id
        self.exchanges: list[object] = []
        self._boot, self._connection = uuid4(), uuid4()

    @property
    def submissions(self) -> list[RuntimeOperationSubmit | RuntimeOperationFinancialInput]:
        return [
            item for item in self.exchanges if isinstance(item, RuntimeOperationSubmit | RuntimeOperationFinancialInput)
        ]

    def status(self) -> SimpleNamespace:
        return self._lease.status()

    def describe(self, definition_id: str, *, deadline: float) -> OperationPublicDefinitionDescriptionV1:
        return self._lease.describe(definition_id, deadline=deadline)

    def close(self) -> None:
        self._lease.close()

    def operation(self, request: object, *, deadline: float) -> RuntimeOperationReply:
        assert deadline > 0
        self.exchanges.append(request)
        if isinstance(request, RuntimeOperationSubmit | RuntimeOperationFinancialInput):
            return RuntimeOperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=self._boot,
                connection_id=self._connection,
                receipt=OperationSubmissionReceiptV1(operation_id=new_operation_id(), secret_requirement=None),
            )
        assert isinstance(request, RuntimeOperationControl), request
        return RuntimeOperationAcknowledged(
            request_id=request.request_id,
            runtime_boot_id=self._boot,
            connection_id=self._connection,
            operation_id=request.operation_id,
        )


async def _call(client: _AnsweringClient, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        return await adapter.call(tool, arguments)
    finally:
        await adapter.close()


def _export(client: _AnsweringClient, **more: object) -> dict[str, Any]:
    """A call of the profile export, an operation whose contract requires a secret."""
    return {
        "definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
        "payload": {"profile_id": str(client.profile_id), "destination": "synthetic.bundle", "purpose": "backup"},
        **more,
    }


@pytest.mark.anyio
async def test_an_operation_that_requires_a_secret_is_the_persons_act_and_nothing_is_sent() -> None:
    client = _AnsweringClient(uuid4())
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            called = await sdk.call_tool("execute", _export(client))
    finally:
        await adapter.close()

    assert called.is_error is True
    assert called.structured_content == {
        "outcome": "refused",
        "code": PERSON_ACT_REQUIRED,
        "remedy": PERSON_ACT_REMEDY,
    }
    assert "Ask the person to do this in Cadrumo" in PERSON_ACT_REMEDY
    assert client.exchanges == []


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["secret", "secret_reference"])
@pytest.mark.parametrize(
    "definition_id", [AUTH_READ_OPERATION_DEFINITION_ID, PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID]
)
async def test_a_call_that_gives_a_secret_or_names_one_is_refused_before_anything_is_sent(
    field: str, definition_id: str
) -> None:
    client = _AnsweringClient(uuid4())
    arguments = {"definition_id": definition_id, "payload": {}, field: _TYPED}

    result = await _call(client, "execute", arguments)

    assert result == {"outcome": "refused", "code": "invalid_request"}
    assert _TYPED not in json.dumps(result)
    assert client.exchanges == []


@pytest.mark.anyio
async def test_no_tool_declares_an_argument_that_takes_or_names_a_secret() -> None:
    client = _AnsweringClient(uuid4())
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            tools = (await sdk.list_tools()).tools
    finally:
        await adapter.close()

    for tool in tools:
        for name, declaration in tool.input_schema["properties"].items():
            assert "secret" not in name and not name.endswith("_reference"), (tool.name, name)
            assert declaration.get("format") != "password" and "writeOnly" not in declaration, (tool.name, name)


@pytest.mark.anyio
async def test_describe_gives_the_typed_operator_input_schema_only_where_the_contract_declares_an_operand() -> None:
    client = _AnsweringClient(uuid4())

    edit = await _call(client, "describe", {"definition_id": MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID})
    read = await _call(client, "describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})

    assert edit["description"]["contract"]["transient_financial_operand"] is not None
    schema = edit["operator_input_json_schema"]
    assert set(schema["properties"]) == {"input_version", "submission"}
    assert read["description"]["contract"]["transient_financial_operand"] is None
    assert "operator_input_json_schema" not in read


@pytest.mark.anyio
async def test_typed_operator_input_travels_on_the_financial_input_exchange_under_the_supplied_subject() -> None:
    client = _AnsweringClient(uuid4())

    result = await _call(
        client,
        "execute",
        {
            "definition_id": MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
            "subject_ref": _WORK_UNIT_ID,
            "payload": _OPERATOR_INPUT,
        },
    )

    assert result["outcome"] == "submitted", result
    assert "secret_delivery" not in result
    (submitted,) = client.submissions
    assert isinstance(submitted, RuntimeOperationFinancialInput)
    assert submitted.subject_ref == _WORK_UNIT_ID
    assert json.loads(submitted.payload_json) == _OPERATOR_INPUT
    assert submitted.idempotency_key is None
    assert result["start"]["kind"] == "operation_acknowledged"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("more", "message"),
    [
        (
            {},
            "subject_ref is required with typed operator input: it is payload field work_unit_id "
            "of the registered request",
        ),
        (
            {"subject_ref": _WORK_UNIT_ID, "idempotency_key": "synthetic-once"},
            "idempotency_key is not accepted with typed operator input",
        ),
    ],
    ids=["no-subject", "idempotency-key"],
)
async def test_typed_operator_input_without_its_subject_or_with_a_replay_key_is_refused_before_submitting(
    more: dict[str, str], message: str
) -> None:
    client = _AnsweringClient(uuid4())

    result = await _call(
        client,
        "execute",
        {"definition_id": MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID, "payload": _OPERATOR_INPUT, **more},
    )

    assert result == {"outcome": "refused", "code": "invalid_request", "message": message}
    assert client.exchanges == []
