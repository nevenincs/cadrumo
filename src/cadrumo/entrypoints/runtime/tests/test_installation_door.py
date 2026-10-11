"""The installation door admits by native evidence alone and settles every act with one typed reply.

The door, its registry and the runtime's framing are the real ones. The byte
channel is a buffer, so each admission branch is reached without a native
endpoint; the exchange over the native transport is proved beside this file.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from cadrumo.adapters.local_runtime.installation_frame_io import read_installation_reply
from cadrumo.adapters.local_runtime.runtime_frame_io import read_document, write_secret
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimePeer, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.installation_requests import (
    INSTALLATION_LOG_TAIL_MAX_LINES,
    InstallationAct,
    RuntimeArchiveImportReply,
    RuntimeArchiveImportRequest,
    RuntimeInstallationActRequest,
    RuntimeInstallationCompleted,
    RuntimeInstallationFailed,
    RuntimeInstallationPassphrase,
    RuntimeInstallationRefused,
    RuntimeInstallationReplyTransfer,
    RuntimeRecoveryEnrollRequest,
    RuntimeRepairLogsReply,
    RuntimeRepairLogsRequest,
    RuntimeStorageCheckReply,
    RuntimeStorageCheckRequest,
    RuntimeStorageInitReply,
    RuntimeStorageInitRequest,
    RuntimeStorageInventoryRequest,
    RuntimeStorageReclaimReply,
    RuntimeStorageReclaimRequest,
)
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeReply, RuntimeSecretReady
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.storage_management.errors import StorageReclaimUnconfirmedError
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, OsLockState
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.storage_taxonomy import StorageArea

from ..installation_composition import InstallationActRegistry, production_installation_acts
from ..installation_door import InstallationActExchange
from ..profile_connections import RuntimeProfileConnections
from .installation_runtime import InstallationLogin

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_OWNER = "synthetic-installation-owner"
_PROFILE = "6f1f6a0e-6f3c-4a55-9d1e-3b0a7c1d2e4f"
_PROOF = "synthetic-installation-passphrase"
_FAULT_TEXT = "synthetic-fault-text-that-must-stay-private"


class _BufferChannel:
    """A byte channel over two buffers: what the peer already sent, and what the door wrote."""

    def __init__(self, peer: RuntimePeer, inbound: bytes = b"") -> None:
        self.peer = peer
        self._inbound = bytearray(inbound)
        self.written = bytearray()
        self.closed = False

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        del deadline
        if self.closed or len(self._inbound) < count:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        taken = bytes(self._inbound[:count])
        del self._inbound[:count]
        return taken

    def read_ready(self) -> bool:
        return bool(self._inbound)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        del deadline
        if self.closed:
            raise RuntimeRefusalError(RuntimeRefusalCode.CONNECTION_CLOSED)
        self.written.extend(payload)

    def close(self) -> None:
        self.closed = True


def _login(
    *, owner: str = _OWNER, lock_state: OsLockState = OsLockState.UNLOCKED, active: bool = True
) -> InstallationLogin:
    return InstallationLogin(owner=owner, lock_state=lock_state, active=active)


def _door(
    tmp_path: Path, registry: InstallationActRegistry | None, login: InstallationLogin | None = None
) -> RuntimeProfileConnections:
    observed = login or _login()
    return RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="ab" * 32,
        runtime_boot_id=uuid4(),
        stop=Event(),
        capture_login=lambda _channel: observed,
        installation_acts=registry,
    )


def _peer() -> RuntimePeer:
    return RuntimePeer(os_owner_id=_OWNER, process_id=4242)


def _serve(
    door: RuntimeProfileConnections,
    request: RuntimeInstallationActRequest,
    *,
    context: RuntimeConnectionContext | None = None,
    inbound: bytes = b"",
) -> tuple[list[BaseModel], _BufferChannel]:
    """Hand one request to the door and decode every document it wrote, in order."""
    channel = _BufferChannel(_peer(), inbound)
    door.installation(context or RuntimeConnectionContext(uuid4(), door.boot, channel.peer), channel, request)
    reader = _BufferChannel(channel.peer, bytes(channel.written))
    documents: list[BaseModel] = []
    while reader.read_ready():
        received = read_document(reader, RuntimeReply, deadline=time.monotonic() + 5).root
        if isinstance(received, RuntimeInstallationReplyTransfer):
            received = read_installation_reply(reader, received, deadline=time.monotonic() + 5).root
        documents.append(received)
    return documents, channel


def _settled(door: RuntimeProfileConnections, request: RuntimeInstallationActRequest) -> BaseModel:
    documents, _channel = _serve(door, request)
    assert len(documents) == 1
    return documents[0]


def _check_request(
    frontend: OperationFrontendProjection = OperationFrontendProjection.CLI,
) -> RuntimeStorageCheckRequest:
    return RuntimeStorageCheckRequest(request_id=uuid4(), frontend=frontend)


def _check(request: RuntimeStorageCheckRequest, exchange: InstallationActExchange) -> RuntimeStorageCheckReply:
    del request
    return exchange.reply(
        RuntimeStorageCheckReply,
        storage_root=str(exchange.storage_root),
        healthy=True,
        root_mode_enforced=False,
        checked_areas=4,
    )


def _checking_registry() -> InstallationActRegistry:
    registry = InstallationActRegistry()
    registry.register(RuntimeStorageCheckRequest, _check)
    return registry


def test_a_registered_act_settles_with_its_handlers_reply_on_the_requests_coordinates(tmp_path: Path) -> None:
    door = _door(tmp_path, _checking_registry())
    request = _check_request()
    channel = _BufferChannel(_peer())
    context = RuntimeConnectionContext(uuid4(), door.boot, channel.peer)

    door.installation(context, channel, request)

    reply = read_document(
        _BufferChannel(channel.peer, bytes(channel.written)), RuntimeReply, deadline=time.monotonic() + 5
    ).root
    assert isinstance(reply, RuntimeStorageCheckReply)
    assert (reply.request_id, reply.runtime_boot_id, reply.connection_id) == (
        request.request_id,
        door.boot,
        context.connection_id,
    )
    assert reply.storage_root == str(tmp_path)
    assert reply.checked_areas == 4


@pytest.mark.parametrize("fault", ["other-peer", "other-boot"])
def test_a_request_from_an_unverified_peer_or_another_boot_never_reaches_a_handler(tmp_path: Path, fault: str) -> None:
    reached: list[InstallationAct] = []

    def handler(request: RuntimeStorageCheckRequest, exchange: InstallationActExchange) -> RuntimeStorageCheckReply:
        reached.append(exchange.act)
        return _check(request, exchange)

    registry = InstallationActRegistry()
    registry.register(RuntimeStorageCheckRequest, handler)
    door = _door(tmp_path, registry)
    context = RuntimeConnectionContext(
        uuid4(),
        door.boot if fault == "other-peer" else uuid4(),
        RuntimePeer(os_owner_id="another-owner", process_id=7) if fault == "other-peer" else _peer(),
    )

    documents, _channel = _serve(door, _check_request(), context=context)

    assert [type(document) for document in documents] == [RuntimeAccessRefusal]
    refusal = documents[0]
    assert isinstance(refusal, RuntimeAccessRefusal)
    assert refusal.code is RuntimeRefusalCode.PEER_UNTRUSTED
    assert reached == []


@pytest.mark.parametrize(
    "login",
    [
        pytest.param(_login(lock_state=OsLockState.LOCKED), id="locked"),
        pytest.param(_login(active=False), id="logged-out"),
        pytest.param(_login(owner="another-owner"), id="another-account"),
    ],
)
def test_a_login_that_is_locked_ended_or_anothers_needs_the_person(tmp_path: Path, login: InstallationLogin) -> None:
    door = _door(tmp_path, _checking_registry(), login)

    refusal = _settled(door, _check_request())

    assert isinstance(refusal, RuntimeAccessRefusal)
    assert refusal.code is AutomationCustodyCode.NEEDS_USER


def test_a_verified_login_with_no_lock_surface_is_admitted(tmp_path: Path) -> None:
    door = _door(tmp_path, _checking_registry(), _login(lock_state=OsLockState.NOT_APPLICABLE))

    assert isinstance(_settled(door, _check_request()), RuntimeStorageCheckReply)


def test_a_draining_runtime_refuses_an_act_whether_or_not_it_changes_records(tmp_path: Path) -> None:
    registry = _checking_registry()
    registry.register(RuntimeStorageInitRequest, _unreachable_init)
    door = _door(tmp_path, registry)
    door.stop.set()

    for request in (
        _check_request(),
        RuntimeStorageInitRequest(request_id=uuid4(), frontend=OperationFrontendProjection.CLI),
    ):
        refusal = _settled(door, request)
        assert isinstance(refusal, RuntimeAccessRefusal)
        assert refusal.code is RuntimeRefusalCode.DRAINING


def _unreachable_init(request: RuntimeStorageInitRequest, exchange: InstallationActExchange) -> RuntimeStorageInitReply:
    raise AssertionError("a refused act must not reach its handler")


def test_an_act_that_changes_records_runs_under_the_lifecycle_exclusion_and_a_read_does_not(tmp_path: Path) -> None:
    roles: dict[InstallationAct, str | None] = {}

    def init(request: RuntimeStorageInitRequest, exchange: InstallationActExchange) -> RuntimeStorageInitReply:
        del request
        roles[exchange.act] = door._drain_guard._owner_role
        return exchange.reply(RuntimeStorageInitReply, storage_root=str(exchange.storage_root))

    def check(request: RuntimeStorageCheckRequest, exchange: InstallationActExchange) -> RuntimeStorageCheckReply:
        roles[exchange.act] = door._drain_guard._owner_role
        return _check(request, exchange)

    def reclaim(request: RuntimeStorageReclaimRequest, exchange: InstallationActExchange) -> RuntimeStorageReclaimReply:
        roles[exchange.act] = door._drain_guard._owner_role
        if not request.confirmed:
            raise StorageReclaimUnconfirmedError(request.area, entry_count=3)
        return exchange.reply(
            RuntimeStorageReclaimReply,
            area=request.area,
            target_count=1,
            removed_entries=3,
        )

    registry = InstallationActRegistry()
    registry.register(RuntimeStorageInitRequest, init)
    registry.register(RuntimeStorageCheckRequest, check)
    registry.register(RuntimeStorageReclaimRequest, reclaim)
    door = _door(tmp_path, registry)
    cli = OperationFrontendProjection.CLI

    assert isinstance(
        _settled(door, RuntimeStorageInitRequest(request_id=uuid4(), frontend=cli)), RuntimeStorageInitReply
    )
    assert isinstance(_settled(door, _check_request()), RuntimeStorageCheckReply)
    assert roles == {InstallationAct.STORAGE_INIT: "delete", InstallationAct.STORAGE_CHECK: None}

    unconfirmed = _settled(door, RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=cli, area=StorageArea.CACHE))
    assert isinstance(unconfirmed, RuntimeInstallationRefused)
    assert roles[InstallationAct.STORAGE_RECLAIM] is None
    confirmed = _settled(
        door, RuntimeStorageReclaimRequest(request_id=uuid4(), frontend=cli, area=StorageArea.CACHE, confirmed=True)
    )
    assert isinstance(confirmed, RuntimeStorageReclaimReply)
    assert roles[InstallationAct.STORAGE_RECLAIM] == "delete"
    assert door._drain_guard._owner is None


def test_shutdown_holding_the_lifecycle_exclusion_refuses_a_change_and_still_serves_a_read(tmp_path: Path) -> None:
    registry = _checking_registry()
    registry.register(RuntimeStorageInitRequest, _unreachable_init)
    door = _door(tmp_path, registry)
    release = Event()

    def hold_exclusively() -> None:
        assert door._drain_guard.acquire(blocking=False)
        try:
            held.set()
            release.wait()
        finally:
            door._drain_guard.release()

    held = Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        holding = pool.submit(hold_exclusively)
        try:
            assert held.wait(5)
            refused = _settled(
                door, RuntimeStorageInitRequest(request_id=uuid4(), frontend=OperationFrontendProjection.MCP)
            )
            served = _settled(door, _check_request())
        finally:
            release.set()
            holding.result(timeout=5)

    assert isinstance(refused, RuntimeAccessRefusal)
    assert refused.code is AutomationCustodyCode.CONFLICT
    assert isinstance(served, RuntimeStorageCheckReply)


def test_an_act_with_no_handler_is_unavailable(tmp_path: Path) -> None:
    door = _door(tmp_path, _checking_registry())

    refusal = _settled(
        door, RuntimeStorageInventoryRequest(request_id=uuid4(), frontend=OperationFrontendProjection.TUI)
    )

    assert isinstance(refusal, RuntimeAccessRefusal)
    assert refusal.code is AccessDenialCode.OPERATION_UNAVAILABLE


def test_a_door_given_no_registry_serves_the_installed_composition(tmp_path: Path) -> None:
    door = _door(tmp_path, None)

    composed = door._installation_registry()

    assert composed.served_acts == production_installation_acts().served_acts
    assert door._installation_registry() is composed


def test_a_registered_error_reaches_the_caller_as_that_error_with_its_public_context(tmp_path: Path) -> None:
    def reclaim(request: RuntimeStorageReclaimRequest, exchange: InstallationActExchange) -> RuntimeStorageReclaimReply:
        del exchange
        raise StorageReclaimUnconfirmedError(request.area, entry_count=3)

    registry = InstallationActRegistry()
    registry.register(RuntimeStorageReclaimRequest, reclaim)
    door = _door(tmp_path, registry)

    refused = _settled(
        door,
        RuntimeStorageReclaimRequest(
            request_id=uuid4(), frontend=OperationFrontendProjection.MCP, area=StorageArea.LOGS
        ),
    )

    assert isinstance(refused, RuntimeInstallationRefused)
    assert refused.act is InstallationAct.STORAGE_RECLAIM
    assert refused.detail.error_code is not None
    context = refused.detail.context_mapping()
    assert context["area"] == "logs"
    assert context["entry_count"] == "3"


def test_an_unexpected_fault_fails_one_act_privately_and_the_door_keeps_serving(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(request: RuntimeStorageCheckRequest, exchange: InstallationActExchange) -> RuntimeStorageCheckReply:
        raise ValueError(_FAULT_TEXT)

    registry = InstallationActRegistry()
    registry.register(RuntimeStorageCheckRequest, broken)
    registry.register(RuntimeStorageInitRequest, _init)
    door = _door(tmp_path, registry)
    caplog.set_level(logging.DEBUG)

    documents, channel = _serve(door, _check_request())

    assert [type(document) for document in documents] == [RuntimeInstallationFailed]
    assert _FAULT_TEXT.encode() not in bytes(channel.written)
    assert _FAULT_TEXT not in caplog.text
    assert all(_FAULT_TEXT not in repr(record.__dict__) for record in caplog.records)
    failures = [record for record in caplog.records if record.getMessage() == "installation act failed"]
    assert len(failures) == 1
    assert failures[0].__dict__["act"] == "storage_check"
    assert failures[0].__dict__["error_type"] == "ValueError"
    assert isinstance(
        _settled(door, RuntimeStorageInitRequest(request_id=uuid4(), frontend=OperationFrontendProjection.CLI)),
        RuntimeStorageInitReply,
    )


def _init(request: RuntimeStorageInitRequest, exchange: InstallationActExchange) -> RuntimeStorageInitReply:
    del request
    return exchange.reply(RuntimeStorageInitReply, storage_root=str(exchange.storage_root))


def test_a_handler_that_answers_with_another_acts_reply_fails_its_act(tmp_path: Path) -> None:
    def confused(
        request: RuntimeStorageCheckRequest, exchange: InstallationActExchange
    ) -> RuntimeInstallationCompleted:
        del request
        return exchange.reply(RuntimeStorageInitReply, storage_root=str(exchange.storage_root))

    registry = InstallationActRegistry()
    registry.register(RuntimeStorageCheckRequest, confused)
    door = _door(tmp_path, registry)

    assert isinstance(_settled(door, _check_request()), RuntimeInstallationFailed)


@pytest.mark.parametrize(
    "login",
    [pytest.param(_login(), id="admitted"), pytest.param(_login(lock_state=OsLockState.LOCKED), id="locked")],
)
def test_the_same_act_is_admitted_and_answered_identically_whatever_frontend_sends_it(
    tmp_path: Path, login: InstallationLogin
) -> None:
    door = _door(tmp_path, _checking_registry(), login)
    members = {"request_id", "connection_id"}

    answers = {
        frontend: _settled(door, _check_request(frontend)).model_dump(mode="json", exclude=members)
        for frontend in OperationFrontendProjection
    }

    assert set(answers) == {
        OperationFrontendProjection.CLI,
        OperationFrontendProjection.TUI,
        OperationFrontendProjection.MCP,
    }
    assert answers[OperationFrontendProjection.CLI] == answers[OperationFrontendProjection.TUI]
    assert answers[OperationFrontendProjection.CLI] == answers[OperationFrontendProjection.MCP]


def test_an_inbound_secret_arrives_in_one_secret_frame_and_nowhere_else(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    received: list[str] = []

    def restore(request: RuntimeArchiveImportRequest, exchange: InstallationActExchange) -> RuntimeArchiveImportReply:
        secrets = exchange.receive_secret(RuntimeInstallationPassphrase)
        received.append(secrets.passphrase.get_secret_value())
        return exchange.reply(
            RuntimeArchiveImportReply,
            profile_id=_PROFILE,
            label=request.label,
            authority="password",
            recovery_enrolled=False,
        )

    registry = InstallationActRegistry()
    registry.register(RuntimeArchiveImportRequest, restore)
    door = _door(tmp_path, registry)
    framed = _BufferChannel(_peer())
    write_secret(framed, bytearray(canonical_json_bytes({"passphrase": _PROOF})), deadline=time.monotonic() + 5)
    caplog.set_level(logging.DEBUG)
    request = RuntimeArchiveImportRequest(
        request_id=uuid4(),
        frontend=OperationFrontendProjection.MCP,
        label="Synthetic profile",
        path=str(tmp_path.resolve() / "synthetic.cadrumo"),
        source_digest="cd" * 32,
    )

    documents, channel = _serve(door, request, inbound=bytes(framed.written))

    assert received == [_PROOF]
    assert [type(document) for document in documents] == [RuntimeSecretReady, RuntimeArchiveImportReply]
    assert _PROOF.encode() not in bytes(channel.written)
    assert _PROOF not in caplog.text
    assert all(_PROOF not in repr(record.__dict__) for record in caplog.records)


def test_a_secret_frame_that_is_not_the_declared_document_is_an_invalid_frame_without_its_bytes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def restore(request: RuntimeArchiveImportRequest, exchange: InstallationActExchange) -> RuntimeArchiveImportReply:
        exchange.receive_secret(RuntimeInstallationPassphrase)
        raise AssertionError("a malformed secret must not be handed to the handler")

    registry = InstallationActRegistry()
    registry.register(RuntimeArchiveImportRequest, restore)
    door = _door(tmp_path, registry)
    framed = _BufferChannel(_peer())
    write_secret(
        framed,
        bytearray(canonical_json_bytes({"passphrase": _PROOF, "unexpected": _FAULT_TEXT})),
        deadline=time.monotonic() + 5,
    )
    caplog.set_level(logging.DEBUG)
    request = RuntimeArchiveImportRequest(
        request_id=uuid4(),
        frontend=OperationFrontendProjection.CLI,
        label="Synthetic profile",
        path=str(tmp_path.resolve() / "synthetic.cadrumo"),
        source_digest="cd" * 32,
    )

    documents, channel = _serve(door, request, inbound=bytes(framed.written))

    refusal = documents[-1]
    assert isinstance(refusal, RuntimeAccessRefusal)
    assert refusal.code is RuntimeRefusalCode.INVALID_FRAME
    for private in (_PROOF, _FAULT_TEXT):
        assert private.encode() not in bytes(channel.written)
        assert private not in caplog.text


def test_a_handler_cannot_take_a_secret_its_act_does_not_declare(tmp_path: Path) -> None:
    def greedy(request: RuntimeStorageCheckRequest, exchange: InstallationActExchange) -> RuntimeStorageCheckReply:
        exchange.receive_secret(RuntimeInstallationPassphrase)
        return _check(request, exchange)

    registry = InstallationActRegistry()
    registry.register(RuntimeStorageCheckRequest, greedy)
    door = _door(tmp_path, registry)

    documents, _channel = _serve(door, _check_request())

    assert [type(document) for document in documents] == [RuntimeInstallationFailed]


@pytest.mark.parametrize(("line_bytes", "settles"), [(200, RuntimeRepairLogsReply), (1_000, RuntimeInstallationFailed)])
def test_a_reply_beyond_one_frame_travels_whole_and_one_beyond_the_bound_fails(
    tmp_path: Path, line_bytes: int, settles: type[BaseModel]
) -> None:
    lines = tuple(f"{index:06d} " + "x" * line_bytes for index in range(INSTALLATION_LOG_TAIL_MAX_LINES))

    def tail(request: RuntimeRepairLogsRequest, exchange: InstallationActExchange) -> RuntimeRepairLogsReply:
        return exchange.reply(RuntimeRepairLogsReply, path=str(exchange.storage_root / "cadrumo.log"), lines=lines)

    registry = InstallationActRegistry()
    registry.register(RuntimeRepairLogsRequest, tail)
    door = _door(tmp_path, registry)
    channel = _BufferChannel(_peer())
    request = RuntimeRepairLogsRequest(
        request_id=uuid4(), frontend=OperationFrontendProjection.TUI, lines=INSTALLATION_LOG_TAIL_MAX_LINES
    )

    door.installation(RuntimeConnectionContext(uuid4(), door.boot, channel.peer), channel, request)

    reader = _BufferChannel(channel.peer, bytes(channel.written))
    first = read_document(reader, RuntimeReply, deadline=time.monotonic() + 5).root
    if settles is RuntimeInstallationFailed:
        assert isinstance(first, RuntimeInstallationFailed)
        assert not reader.read_ready()
        return
    assert isinstance(first, RuntimeInstallationReplyTransfer)
    assert first.request_id == request.request_id
    reply = read_installation_reply(reader, first, deadline=time.monotonic() + 5).root
    assert isinstance(reply, RuntimeRepairLogsReply)
    assert reply.lines == lines
    assert not reader.read_ready()


def test_a_reserved_profile_refuses_a_second_custody_change_and_is_released_when_the_act_ends(tmp_path: Path) -> None:
    profile_id = UUID(_PROFILE)
    seen: list[frozenset[UUID]] = []

    def init(request: RuntimeStorageInitRequest, exchange: InstallationActExchange) -> RuntimeStorageInitReply:
        with exchange.reserve_profiles((profile_id,)) as reservation:
            seen.append(reservation.profile_ids)
            reservation.retire_hosted()
            assert exchange.hosted_profile_ids() == ()
            with exchange.reserve_profiles((profile_id,)):
                raise AssertionError("a profile under one custody change cannot be reserved again")
        return _init(request, exchange)

    registry = InstallationActRegistry()
    registry.register(RuntimeStorageInitRequest, init)
    door = _door(tmp_path, registry)

    refusal = _settled(door, RuntimeStorageInitRequest(request_id=uuid4(), frontend=OperationFrontendProjection.CLI))

    assert seen == [frozenset({profile_id})]
    assert isinstance(refusal, RuntimeAccessRefusal)
    assert refusal.code is AutomationCustodyCode.CONFLICT
    assert door._custody_mutations == set()
    assert door._drain_guard._owner is None


def test_a_handler_is_registered_once_and_only_for_the_request_of_an_act() -> None:
    registry = InstallationActRegistry()
    registry.register(RuntimeStorageCheckRequest, _check)

    assert registry.served_acts == {InstallationAct.STORAGE_CHECK}
    with pytest.raises(InternalInvariantError):
        registry.register(RuntimeStorageCheckRequest, _check)
    with pytest.raises(InternalInvariantError):
        registry.register(RuntimeInstallationPassphrase, _check_anything)
    assert registry.handler_for(_check_request()) is not None
    assert (
        registry.handler_for(
            RuntimeRecoveryEnrollRequest(
                request_id=uuid4(), frontend=OperationFrontendProjection.CLI, profile_id=UUID(_PROFILE)
            )
        )
        is None
    )


def _check_anything(request: BaseModel, exchange: InstallationActExchange) -> RuntimeStorageCheckReply:
    raise AssertionError("an unregistered handler is never called")
