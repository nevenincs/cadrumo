"""The execute tool carries what an operation's contract declares: a typed secret or typed operator input.

The adapter's own part is shown here: what it holds a call to before anything
is sent, which exchange each part of the call travels on, in what order, and
what it says back. The runtime's answers are supplied by a connection double
that keeps every exchange it is handed, because whether a submission or a
secret is admitted is the runtime's decision and is proven against the real
runtime where that runtime lives. The contracts are the real registered ones.
"""

from __future__ import annotations

import json
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, NoReturn, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.auth.read_operation import build_auth_read_definition, build_auth_read_registration
from cadrumo.application.modelo.operation_definitions import (
    MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID,
    build_modelo_edit_apply_definition,
    build_modelo_edit_apply_registration,
)
from cadrumo.application.operations.frontend_requests import OperationSubmissionReceiptV1
from cadrumo.application.operations.models import OperationIdentity, new_operation_id
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1, OperationRegistry
from cadrumo.application.operations.secret_submission import OperationSecretRequirement
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
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session
from cadrumo_harness.mcp.tests.test_operation_search_tool import _AdmittedClient

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_TYPED = "synthetic-export-text-7f3a"
_TYPED_BYTES = _TYPED.encode("utf-8")
_KIND = "synthetic.typed-input"
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

    def __init__(self, profile_id: UUID, *, secret_answer: Exception | None = None) -> None:
        self._lease = _AdmittedClient(profile_id, _registry())
        self.profile_id, self.registry = profile_id, self._lease.registry
        self.frontend, self.session_id = self._lease.frontend, self._lease.session_id
        self.exchanges: list[object] = []
        self.secret_buffers: list[bytearray] = []
        self.secrets: list[tuple[OperationSecretRequirement, bytes]] = []
        self._secret_answer = secret_answer
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
            operation_id = new_operation_id()
            contract = self.registry.lookup_public_contract(request.definition_id)
            requirement = (
                OperationSecretRequirement(
                    identity=OperationIdentity(
                        operation_id=operation_id,
                        definition_id=request.definition_id,
                        subject_ref=request.subject_ref,
                    ),
                    interaction_id="f" * 64,
                    revision=1,
                    secret_kind=_KIND,
                    expires_at=now() + timedelta(minutes=5),
                )
                if contract.ephemeral_secret_required
                else None
            )
            return RuntimeOperationSubmitted(
                request_id=request.request_id,
                runtime_boot_id=self._boot,
                connection_id=self._connection,
                receipt=OperationSubmissionReceiptV1(operation_id=operation_id, secret_requirement=requirement),
            )
        assert isinstance(request, RuntimeOperationControl), request
        return RuntimeOperationAcknowledged(
            request_id=request.request_id,
            runtime_boot_id=self._boot,
            connection_id=self._connection,
            operation_id=request.operation_id,
        )

    def submit_secret(
        self, requirement: OperationSecretRequirement, secret: bytearray, *, timeout: float
    ) -> RuntimeOperationAcknowledged:
        """Stand in for the protected secret frame; the buffer is left as handed over."""
        assert 0 < timeout <= 20
        self.exchanges.append(requirement)
        self.secret_buffers.append(secret)
        self.secrets.append((requirement, bytes(secret)))
        if self._secret_answer is not None:
            raise self._secret_answer
        return RuntimeOperationAcknowledged(
            request_id=uuid4(),
            runtime_boot_id=self._boot,
            connection_id=self._connection,
            operation_id=requirement.identity.operation_id,
        )


async def _call(client: _AnsweringClient, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        return await adapter.call(tool, arguments)
    finally:
        await adapter.close()


def _export(client: _AnsweringClient, **more: object) -> dict[str, Any]:
    return {
        "definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
        "payload": {"profile_id": str(client.profile_id), "destination": "synthetic.bundle", "purpose": "backup"},
        **more,
    }


@pytest.mark.anyio
async def test_the_secret_travels_apart_from_the_payload_between_the_submission_and_the_start() -> None:
    client = _AnsweringClient(uuid4())
    arguments = _export(client, secret=_TYPED)

    result = await _call(client, "execute", arguments)

    assert result["outcome"] == "submitted", result
    assert result["secret_delivery"] == {"outcome": "delivered"}
    assert result["start"]["kind"] == "operation_acknowledged"
    submitted, requirement, started = client.exchanges
    assert isinstance(submitted, RuntimeOperationSubmit)
    assert isinstance(requirement, OperationSecretRequirement)
    assert isinstance(started, RuntimeOperationControl) and started.action == "operation_start"
    # The requirement answered is the one the runtime opened for this exact submission.
    assert requirement.identity == OperationIdentity(
        operation_id=result["receipt"]["operation_id"],
        definition_id=PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{client.profile_id}",
    )
    assert started.operation_id == requirement.identity.operation_id
    assert client.secrets == [(requirement, _TYPED_BYTES)]
    # The text is in no document frame and no reply, and neither the call nor its buffer still holds it.
    assert _TYPED not in submitted.model_dump_json()
    assert _TYPED not in submitted.payload_json
    assert _TYPED not in json.dumps(result)
    assert "secret" not in arguments
    assert client.secret_buffers == [bytearray(len(_TYPED_BYTES))]


@pytest.mark.anyio
async def test_a_submission_asked_not_to_start_still_delivers_its_secret() -> None:
    client = _AnsweringClient(uuid4())

    result = await _call(client, "execute", _export(client, secret=_TYPED, start=False))

    assert result["secret_delivery"] == {"outcome": "delivered"}
    assert "start" not in result
    assert [type(item) for item in client.exchanges] == [RuntimeOperationSubmit, OperationSecretRequirement]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("answer", "delivery"),
    [
        (RuntimeFrontendRefusedError("operation_denied"), {"outcome": "refused", "code": "operation_denied"}),
        (TimeoutError("synthetic lost reply"), {"outcome": "unresolved", "code": "runtime_unavailable"}),
    ],
    ids=["runtime-refused", "reply-lost"],
)
async def test_a_secret_the_runtime_did_not_acknowledge_keeps_the_receipt_and_starts_nothing(
    answer: Exception, delivery: dict[str, str]
) -> None:
    client = _AnsweringClient(uuid4(), secret_answer=answer)
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            called = await sdk.call_tool("execute", _export(client, secret=_TYPED))
    finally:
        await adapter.close()

    assert called.is_error is True
    result = called.structured_content
    assert result is not None
    assert result["outcome"] == "submitted" and result["receipt"]["operation_id"]
    assert result["secret_delivery"] == delivery
    assert "start" not in result
    assert not any(isinstance(item, RuntimeOperationControl) for item in client.exchanges)
    assert _TYPED not in json.dumps(result)
    assert client.secret_buffers == [bytearray(len(_TYPED_BYTES))]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID, "payload": {"kind": "status"}, "secret": _TYPED},
            "secret is not accepted: this operation's contract declares no typed secret",
        ),
        (
            {"definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID, "payload": {}},
            "secret is required: this operation's contract says ephemeral_secret_required",
        ),
        (
            {"definition_id": PROFILE_BUNDLE_EXPORT_OPERATION_DEFINITION_ID, "payload": {}, "secret": ""},
            "secret is required: this operation's contract says ephemeral_secret_required",
        ),
    ],
    ids=["given-where-none-is-declared", "omitted-where-one-is-required", "empty-where-one-is-required"],
)
async def test_a_call_that_does_not_fit_the_declared_secret_is_refused_before_anything_is_sent(
    arguments: dict[str, Any], message: str
) -> None:
    client = _AnsweringClient(uuid4())

    result = await _call(client, "execute", dict(arguments))

    assert result == {"outcome": "refused", "code": "invalid_request", "message": message}
    assert _TYPED not in json.dumps(result)
    assert client.exchanges == [] and client.secrets == []


@pytest.mark.anyio
async def test_the_tool_list_declares_the_secret_field_as_write_only_text() -> None:
    client = _AnsweringClient(uuid4())
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            tools = {tool.name: tool for tool in (await sdk.list_tools()).tools}
    finally:
        await adapter.close()

    execute = tools["execute"]
    assert execute.input_schema["properties"]["secret"] == {"type": "string", "format": "password", "writeOnly": True}
    assert "secret" not in execute.input_schema["required"]
    assert "ephemeral_secret_required" in (execute.description or "")


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
