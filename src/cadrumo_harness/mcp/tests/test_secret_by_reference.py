"""A tool takes a secret by reference: the person entered it at a terminal, and the call names only the reference.

What is shown here is the adapter's own part. The secret is read from the
credential store into the buffer the typed form uses, travels on the same
exchange, and is in no reply and no log. A reference that names nothing a
person entered is a mistaken argument. The store is the in-memory port the
custody package's own tests use, and the runtime's answers come from the
connection double that keeps every exchange, because whether a secret is
admitted is the runtime's decision and is proven against the real runtime where
that runtime lives.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast, override
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.mcp_surfaces import MCP_SURFACES, McpSurfaceName
from cadrumo.application.operations.secret_submission import OperationSecretRequirement
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.installation_requests import INSTALLATION_ACT_CONTRACTS, InstallationAct
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationFinancialInput,
    RuntimeOperationReply,
    RuntimeOperationSubmit,
)
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp.held_secrets import HELD_SECRET_NAMESPACE, HeldSecretCustody, held_secret_custody
from cadrumo_harness.mcp.installation_acts import prepare_installation_act
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE, validate_tool_arguments
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.session_acts import SECRET_FIELDS
from cadrumo_harness.mcp.tests.held_secret_support import call_secrets
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session
from cadrumo_harness.mcp.tests.test_execute_typed_input_tool import _AnsweringClient, _export

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_ENTERED = "synthetic-entered-text-7f3a"
_ENTERED_BYTES = _ENTERED.encode("utf-8")
_OTHER = "synthetic-other-entered-text-52d0"
_INVALID = {"outcome": "refused", "code": "invalid_request"}


class _Entered:
    """The store of one test and the custody that reads it, bound to the storage root the adapter resolves."""

    def __init__(self, store: MemoryNativePort) -> None:
        self.store = store

    @property
    def custody(self) -> HeldSecretCustody:
        return held_secret_custody(self.store)

    def hold(self, text: str = _ENTERED, *, single_use: bool = False) -> str:
        """Hold one secret as the person's terminal command does, and return its reference as a call names it."""
        held = self.custody.hold_entered(
            label="synthetic label", secret=bytearray(text, "utf-8"), single_use=single_use
        )
        return str(held.reference)

    def held(self) -> set[str]:
        return {account for namespace, account in self.store.items if namespace == HELD_SECRET_NAMESPACE}


@pytest.fixture
def entered(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Entered]:
    store = MemoryNativePort()
    monkeypatch.setattr(mcp_runtime, "installed_automation_secret_store", lambda: store)
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield _Entered(store)


async def _execute(client: _AnsweringClient, arguments: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    """Call execute through the real server; return whether the result is an error, and its document."""
    adapter = RuntimeMcpAdapter(profile_id=client.profile_id, client=cast(RuntimeFrontendClient, client))
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            called = await sdk.call_tool("execute", arguments)
    finally:
        await adapter.close()
    assert called.structured_content is not None
    return called.is_error, called.structured_content


@pytest.mark.anyio
async def test_a_secret_by_reference_travels_as_the_typed_one_does_and_stays_held_for_the_next_call(
    entered: _Entered, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    reference = entered.hold()
    by_reference, typed = _AnsweringClient(uuid4()), _AnsweringClient(uuid4())

    first_error, first = await _execute(by_reference, _export(by_reference, secret_reference=reference))
    again_error, again = await _execute(by_reference, _export(by_reference, secret_reference=reference))
    _typed_error, as_typed = await _execute(typed, _export(typed, secret=_ENTERED))

    for is_error, result in ((first_error, first), (again_error, again)):
        assert is_error is False and result["outcome"] == "submitted", result
        assert result["secret_delivery"] == {"outcome": "delivered"}
        assert result["start"]["kind"] == "operation_acknowledged"
    # The same bytes reach the same exchange in the same order as the typed form's.
    assert [secret for _requirement, secret in by_reference.secrets] == [_ENTERED_BYTES, _ENTERED_BYTES]
    assert [secret for _requirement, secret in typed.secrets] == [_ENTERED_BYTES]
    assert [type(item) for item in by_reference.exchanges[:3]] == [type(item) for item in typed.exchanges]
    assert all(isinstance(requirement, OperationSecretRequirement) for requirement, _secret in by_reference.secrets)
    assert set(first) == set(as_typed)
    # The buffer each call sent is wiped, and the secret is in no reply, no document frame and no log record.
    assert by_reference.secret_buffers == [bytearray(len(_ENTERED_BYTES))] * 2
    logged = "\n".join(f"{record.getMessage()} {record.__dict__!r}" for record in caplog.records)
    assert _ENTERED not in json.dumps([first, again]) and _ENTERED not in logged
    assert all(_ENTERED not in submitted.model_dump_json() for submitted in by_reference.submissions)
    # Nothing consumed it: the person deletes it when they choose.
    assert entered.held() == {reference}


@pytest.mark.anyio
async def test_a_reference_held_for_one_use_is_spent_by_the_first_call_that_presents_it(entered: _Entered) -> None:
    reference = entered.hold(single_use=True)
    client = _AnsweringClient(uuid4())

    _first_error, first = await _execute(client, _export(client, secret_reference=reference))
    second_error, second = await _execute(client, _export(client, secret_reference=reference))

    assert first["secret_delivery"] == {"outcome": "delivered"}
    assert second_error is True and second == _INVALID
    assert [secret for _requirement, secret in client.secrets] == [_ENTERED_BYTES]
    assert len(client.submissions) == 1 and entered.store.items == {}


@pytest.mark.anyio
async def test_a_reference_that_names_nothing_held_is_a_mistaken_argument(entered: _Entered) -> None:
    client = _AnsweringClient(uuid4())

    for reference in (str(uuid4()), "not-a-reference"):
        is_error, result = await _execute(client, _export(client, secret_reference=reference))
        assert is_error is True and result == _INVALID, reference

    assert client.exchanges == [] and client.secrets == []


@pytest.mark.anyio
async def test_a_secret_held_for_the_person_to_read_is_used_by_its_reference_and_stays_held(
    entered: _Entered,
) -> None:
    delivered = entered.custody.hold(origin="recovery_enroll profile_id=synthetic", secret=bytearray(_OTHER, "utf-8"))
    client = _AnsweringClient(uuid4())

    for _use in range(2):
        is_error, result = await _execute(client, _export(client, secret_reference=str(delivered.reference)))
        assert is_error is False and result["secret_delivery"] == {"outcome": "delivered"}, result
        assert _OTHER not in json.dumps(result)

    assert [secret for _requirement, secret in client.secrets] == [_OTHER.encode(), _OTHER.encode()]
    # A call that used it showed it to nobody, so it is still held and listed for the person to read.
    (listed,) = entered.custody.entries()
    assert (listed.reference, listed.entered) == (delivered.reference, False)
    assert entered.custody.read(delivered.reference).secret.get_secret_value() == _OTHER.encode()


@pytest.mark.anyio
async def test_both_forms_together_and_a_reference_where_no_secret_is_declared_are_refused_unread(
    entered: _Entered,
) -> None:
    reference = entered.hold(single_use=True)
    client = _AnsweringClient(uuid4())

    _both_error, both = await _execute(client, _export(client, secret=_OTHER, secret_reference=reference))
    _stray_error, stray = await _execute(
        client,
        {
            "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
            "payload": {"kind": "status"},
            "secret_reference": reference,
        },
    )

    assert both == {
        "outcome": "refused",
        "code": "invalid_request",
        "message": "secret is given as text or by reference, not both",
    }
    assert stray == {
        "outcome": "refused",
        "code": "invalid_request",
        "message": "secret is not accepted: this operation's contract declares no typed secret",
    }
    assert _OTHER not in json.dumps([both, stray])
    # Neither call read the store, so the one use is still the person's to spend.
    assert client.exchanges == [] and entered.held() == {reference}


def test_every_tool_that_takes_a_secret_takes_it_by_reference_too_and_says_which_form_stays_out() -> None:
    takes_a_secret = {}
    for name, description, schema in MCP_TOOL_CATALOGUE:
        typed = [field for field in SECRET_FIELDS if field in schema["properties"]]
        references = [field for field in schema["properties"] if field.endswith("_reference")]
        if name in {"authorization_prepare", "authenticate"}:
            # A credential reference names an enrolled key, which is no secret a person types.
            assert references == ["credential_reference"] and not typed
            continue
        assert references == [f"{field}_reference" for field in typed], name
        if typed:
            takes_a_secret[name] = description
            for field in typed:
                assert schema["properties"][field] == {"type": "string", "format": "password", "writeOnly": True}
                assert schema["properties"][f"{field}_reference"] == {"type": "string", "format": "uuid"}
                assert f"{field}_reference" not in schema["required"]

    assert set(takes_a_secret) == {"execute", "session", "installation"}
    for name, description in takes_a_secret.items():
        assert "keeps the secret out of the conversation" in description, name
        assert "has already passed through this conversation" in description, name
        assert "`cadrumo-mcp --hold-secret`" in description and "--once" in description, name


def test_the_session_tools_secrets_arrive_as_the_same_buffers_in_either_form() -> None:
    current, replacement = uuid4(), uuid4()
    held = {current: _ENTERED, replacement: _OTHER}
    by_reference: dict[str, Any] = {
        "action": "change_password",
        "secret_reference": str(current),
        "new_secret_reference": str(replacement),
        "new_secret_confirmation_reference": str(replacement),
    }
    typed: dict[str, Any] = {
        "action": "change_password",
        "secret": _ENTERED,
        "new_secret": _OTHER,
        "new_secret_confirmation": _OTHER,
    }
    validate_tool_arguments("session", by_reference)
    validate_tool_arguments("session", typed)

    read_secrets, reads = call_secrets(by_reference, held)
    typed_secrets, typed_reads = call_secrets(typed, held)

    assert by_reference == typed == {"action": "change_password"}
    read_secrets.require("change_password", *SECRET_FIELDS)
    typed_secrets.require("change_password", *SECRET_FIELDS)
    read_secrets.check()
    # Checking a call reads nothing; the store is read when the secrets are taken to be sent.
    assert reads.taken == [] and reads.verified == [current, replacement]
    buffers = read_secrets.take(*SECRET_FIELDS)
    assert buffers == typed_secrets.take(*SECRET_FIELDS)
    # A value and its confirmation that name one reference share one read, so a one-use secret fills both.
    assert reads.taken == [current, replacement] and typed_reads.taken == []
    assert buffers[1] is not buffers[2]
    read_secrets.wipe()
    assert [bytes(buffer) for buffer in buffers] == [bytes(len(buffer)) for buffer in buffers]


def test_a_mixed_call_fills_only_what_was_given_by_reference() -> None:
    replacement = uuid4()
    arguments: dict[str, Any] = {
        "action": "reset_password",
        "secret": _ENTERED,
        "new_secret_reference": str(replacement),
        "new_secret_confirmation_reference": str(replacement),
    }

    secrets, reads = call_secrets(arguments, {replacement: _OTHER})

    secrets.require("reset_password", *SECRET_FIELDS)
    assert [bytes(buffer) for buffer in secrets.take(*SECRET_FIELDS)] == [
        _ENTERED_BYTES,
        _OTHER.encode(),
        _OTHER.encode(),
    ]
    assert reads.taken == [replacement]


@pytest.mark.parametrize(
    "arguments",
    [
        {"secret": _ENTERED, "secret_reference": str(uuid4())},
        {"secret_reference": "not-a-reference"},
    ],
    ids=["both-forms", "malformed-reference"],
)
def test_a_field_in_both_forms_or_a_malformed_reference_is_refused_before_the_store_is_read(
    arguments: dict[str, Any],
) -> None:
    secrets, reads = call_secrets(dict(arguments))

    with pytest.raises(ValueError):
        secrets.check()
    with pytest.raises(ValueError):
        secrets.take("secret")
    assert reads.verified == [] and reads.taken == []


def test_a_call_that_gives_a_secret_the_act_does_not_take_or_omits_one_it_does_is_refused_unread() -> None:
    reference = uuid4()
    held = {reference: _ENTERED}

    extra, extra_reads = call_secrets({"secret_reference": str(reference)}, held)
    missing, missing_reads = call_secrets({}, held)
    empty, empty_reads = call_secrets({"secret": ""}, held)

    with pytest.raises(ValueError, match="storage_check takes no secret field"):
        extra.require("storage_check")
    with pytest.raises(ValueError, match="sign_in takes secret"):
        missing.require("sign_in", "secret")
    with pytest.raises(ValueError, match="sign_in takes secret"):
        empty.require("sign_in", "secret")
    # A reference stands in for the secret its field names, and for nothing else.
    extra.require("sign_in", "secret")
    assert extra_reads.taken == missing_reads.taken == empty_reads.taken == []


def test_an_installation_act_takes_its_passphrase_by_reference_as_the_same_buffer() -> None:
    reference = uuid4()
    assert INSTALLATION_ACT_CONTRACTS[InstallationAct.RECOVERY_ENROLL].takes_secret
    arguments: dict[str, Any] = {"action": InstallationAct.RECOVERY_ENROLL.value, "secret_reference": str(reference)}
    validate_tool_arguments("installation", arguments)

    secrets, reads = call_secrets(arguments, {reference: _ENTERED})
    prepared = prepare_installation_act(arguments, secrets, MCP_SURFACES[McpSurfaceName.FULL])

    # Preparing the act reads nothing: the passphrase is read by the call that is about to send it.
    assert reads.taken == [] and "secret_reference" not in arguments
    assert prepared.passphrase is not None
    passphrase = prepared.passphrase()
    assert reads.taken == [reference] and bytes(passphrase) == _ENTERED_BYTES
    assert _ENTERED not in prepared.request.model_dump_json()
    secrets.wipe()
    assert not any(passphrase)


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["session", "installation"])
async def test_a_session_or_installation_call_with_a_reference_that_holds_nothing_is_refused_before_any_connection(
    entered: _Entered, tool: str
) -> None:
    action = "sign_in" if tool == "session" else "recovery_enroll"
    once = entered.hold(single_use=True)
    adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
    try:
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            unknown = await sdk.call_tool(tool, {"action": action, "secret_reference": str(uuid4())})
            both = await sdk.call_tool(tool, {"action": action, "secret": _OTHER, "secret_reference": once})
    finally:
        await adapter.close()

    for refused in (unknown, both):
        assert refused.is_error is True
        assert refused.structured_content is not None
        assert refused.structured_content["outcome"] == "refused"
        assert refused.structured_content["code"] == "invalid_request"
    # The call that gave both forms read nothing, so the one use is still held.
    assert entered.held() == {once} and adapter.client is None


class _InterferedClient(_AnsweringClient):
    """The admitted lease over a transport that fails or is interfered with when the submission is made."""

    def __init__(
        self,
        profile_id: UUID,
        *,
        submission_failure: Exception | None = None,
        on_submission: Callable[[], None] | None = None,
        secret_answer: Exception | None = None,
    ) -> None:
        super().__init__(profile_id, secret_answer=secret_answer)
        self._submission_failure = submission_failure
        self._on_submission = on_submission

    @override
    def operation(self, request: object, *, deadline: float) -> RuntimeOperationReply:
        if isinstance(request, RuntimeOperationSubmit | RuntimeOperationFinancialInput):
            if self._on_submission is not None:
                self._on_submission()
            if self._submission_failure is not None:
                self.exchanges.append(request)
                raise self._submission_failure
        return super().operation(request, deadline=deadline)


@pytest.mark.anyio
async def test_an_execute_call_refused_before_the_secret_is_sent_leaves_a_one_use_reference_held(
    entered: _Entered,
) -> None:
    reference = entered.hold(single_use=True)
    refused_by_runtime = _InterferedClient(uuid4(), submission_failure=RuntimeFrontendRefusedError("profile_mismatch"))
    unreachable = _InterferedClient(
        uuid4(), submission_failure=RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
    )
    unchecked = _AnsweringClient(uuid4())

    _wrong_subject_error, wrong_subject = await _execute(
        unchecked, _export(unchecked, secret_reference=reference, subject_ref="not-the-subject")
    )
    _refused_error, refused = await _execute(
        refused_by_runtime, _export(refused_by_runtime, secret_reference=reference)
    )
    _lost_error, lost = await _execute(unreachable, _export(unreachable, secret_reference=reference))

    assert wrong_subject["code"] == "invalid_request" and unchecked.exchanges == []
    assert refused == {"outcome": "refused", "code": "profile_mismatch"}
    assert lost["outcome"] == "unresolved" and lost["code"] == RuntimeRefusalCode.CONNECTION_CLOSED.value
    assert refused_by_runtime.secrets == [] and unreachable.secrets == []
    # None of the three calls sent the secret, so none spent it.
    assert entered.held() == {reference}

    sent = _AnsweringClient(uuid4())
    _sent_error, delivered = await _execute(sent, _export(sent, secret_reference=reference))
    assert delivered["secret_delivery"] == {"outcome": "delivered"} and entered.store.items == {}


@pytest.mark.anyio
async def test_a_one_use_reference_that_another_call_spent_after_the_check_sends_no_secret(
    entered: _Entered,
) -> None:
    reference = entered.hold(single_use=True)
    spent: list[bytearray] = []
    client = _InterferedClient(uuid4(), on_submission=lambda: spent.append(entered.custody.take(UUID(reference))))

    _error, result = await _execute(client, _export(client, secret_reference=reference))

    assert bytes(spent[0]) == _ENTERED_BYTES
    # The submission is recorded, and says the runtime took no secret and was not asked to start.
    assert result["outcome"] == "submitted"
    assert result["secret_delivery"] == {"outcome": "refused", "code": "invalid_request"}
    assert "start" not in result and client.secrets == []


@pytest.mark.anyio
async def test_a_one_use_secret_is_spent_by_the_call_that_sends_it_even_when_the_send_fails(
    entered: _Entered,
) -> None:
    reference = entered.hold(single_use=True)
    client = _InterferedClient(uuid4(), secret_answer=RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED))

    _error, result = await _execute(client, _export(client, secret_reference=reference))

    assert result["secret_delivery"] == {"outcome": "unresolved", "code": RuntimeRefusalCode.CONNECTION_CLOSED.value}
    assert [secret for _requirement, secret in client.secrets] == [_ENTERED_BYTES]
    assert entered.store.items == {}


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("tool", "action", "fields"),
    [
        pytest.param("session", "sign_in", ("secret_reference",), id="sign-in"),
        pytest.param("session", "resume", ("secret_reference",), id="resume"),
        pytest.param(
            "session",
            "reset_password",
            ("secret_reference", "new_secret_reference", "new_secret_confirmation_reference"),
            id="reset-password",
        ),
        pytest.param("installation", "recovery_enroll", ("secret_reference",), id="recovery-enroll"),
    ],
)
async def test_a_session_or_installation_call_made_with_no_runtime_running_spends_no_one_use_reference(
    entered: _Entered, tool: str, action: str, fields: tuple[str, ...]
) -> None:
    reference = entered.hold(single_use=True)
    adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
    try:
        reply = await adapter.call(tool, {"action": action, **dict.fromkeys(fields, reference)})
    finally:
        await adapter.close()

    # Refused for want of a runtime, not for the arguments, and the reference is still the person's to spend.
    assert reply["outcome"] == "refused" and reply["code"] != "invalid_request", reply
    assert entered.held() == {reference}


@pytest.mark.anyio
async def test_an_installation_call_refused_locally_spends_no_one_use_reference(entered: _Entered) -> None:
    reference = entered.hold(single_use=True)
    adapter = RuntimeMcpAdapter(profile_id=None, client=None, resumes_sign_in=True)
    try:
        # A read that takes no secret, and a secret of an act that was never asked for.
        reply = await adapter.call("installation", {"action": "storage_check", "secret_reference": reference})
    finally:
        await adapter.close()

    assert reply == _INVALID
    assert entered.held() == {reference}
