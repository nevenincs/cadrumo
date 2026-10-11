"""The MCP ``installation`` tool against the real runtime: every kind of act, with no profile session.

The adapter, the installed installation client it opens, the native transport,
the runtime's installation door and its framing are real, and recovery
enrolment runs the real custody service on a real encrypted profile. The
native login the runtime observes and the credential stores are ports held by
the test, and the other handlers are the test's own, registered through the
runtime's test composition. The MCP SDK uses its memory transport.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT, administration_subject
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.mcp_surfaces import MCP_SURFACES, McpSurface, McpSurfaceName
from cadrumo.application.runtime.installation_requests import (
    INSTALLATION_LOG_TAIL_MAX_LINES,
    RuntimeArchiveImportReply,
    RuntimeArchiveImportRequest,
    RuntimeInstallationPassphrase,
    RuntimeRecoveryEnrollReply,
    RuntimeRecoveryEnrollRequest,
    RuntimeRepairLogsReply,
    RuntimeRepairLogsRequest,
    RuntimeStorageCheckReply,
    RuntimeStorageCheckRequest,
    RuntimeStorageInitRequest,
    RuntimeStorageReclaimReply,
    RuntimeStorageReclaimRequest,
)
from cadrumo.application.storage_management.errors import StorageReclaimUnconfirmedError
from cadrumo.application.user_profile.access_contracts import OsLockState
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.application.user_profile.custody_ports import (
    load_profile_custody_recovery_material,
    unlock_profile_custody_recovery,
)
from cadrumo.application.user_profile.recovery_custody import profile_recovery_status
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp.held_secrets import HELD_SECRET_NAMESPACE, held_secret_custody
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

from ..installation_composition import InstallationActRegistry
from ..installation_door import InstallationActExchange
from ..profile_connections import RuntimeProfileConnections
from .installation_runtime import (
    FAULT_TEXT,
    LOG_LINES,
    InstallationLogin,
    serve_check,
    serve_enroll,
    serve_fault,
    serve_tail,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real Windows protected pipes"),
    pytest.mark.usefixtures("authority_operation"),
]

_FULL = MCP_SURFACES[McpSurfaceName.FULL]
_READ_ONLY_LOCAL = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
_ARCHIVE_INPUT = "synthetic-archive-password"
_UNCONFIRMED = get_registered_error_code(StorageReclaimUnconfirmedError).code


@dataclass
class _Served:
    """What the test's own handlers were asked to do, as nonsecret facts."""

    reclaims: list[tuple[str, bool]] = field(default_factory=list)
    imports: list[tuple[str, bool]] = field(default_factory=list)


def _acts(served: _Served) -> InstallationActRegistry:
    """Register one handler for each kind of act: reads, a confirmable change, a fault and both secret exchanges."""

    def serve_reclaim(
        request: RuntimeStorageReclaimRequest, exchange: InstallationActExchange
    ) -> RuntimeStorageReclaimReply:
        served.reclaims.append((request.area.value, request.confirmed))
        if not request.confirmed:
            raise StorageReclaimUnconfirmedError(request.area, entry_count=3)
        return exchange.reply(
            RuntimeStorageReclaimReply,
            area=request.area,
            target_count=1,
            removed_entries=3,
        )

    def serve_import(
        request: RuntimeArchiveImportRequest, exchange: InstallationActExchange
    ) -> RuntimeArchiveImportReply:
        secrets = exchange.receive_secret(RuntimeInstallationPassphrase)
        served.imports.append((request.label, secrets.passphrase.get_secret_value() == _ARCHIVE_INPUT))
        return exchange.reply(
            RuntimeArchiveImportReply,
            profile_id=str(uuid4()),
            label=request.label,
            authority="password",
            recovery_enrolled=False,
        )

    registry = InstallationActRegistry()
    registry.register(RuntimeStorageCheckRequest, serve_check)
    registry.register(RuntimeRepairLogsRequest, serve_tail)
    registry.register(RuntimeStorageInitRequest, serve_fault)
    registry.register(RuntimeRecoveryEnrollRequest, serve_enroll)
    registry.register(RuntimeStorageReclaimRequest, serve_reclaim)
    registry.register(RuntimeArchiveImportRequest, serve_import)
    return registry


@contextmanager
def _serving(
    endpoint: WindowsRuntimeEndpoint,
    root: Path,
    served: _Served,
    login: InstallationLogin,
    *,
    secret_store: AutomationSecretStore | None = None,
) -> Iterator[None]:
    """Serve ``root`` as the installed cohort, so the adapter's own opener finds the runtime."""
    runtime_store = MemoryNativePort() if secret_store is None else secret_store
    stop, boot = Event(), uuid4()
    profiles = RuntimeProfileConnections(
        storage_root=root,
        storage_identity=endpoint.storage_identity,
        runtime_boot_id=boot,
        stop=stop,
        capture_login=lambda _channel: login,
        secret_store=lambda: runtime_store,
        installation_acts=_acts(served),
    )
    server = RetainedRuntimeTransportServer(
        endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        running = pool.submit(server.serve)
        try:
            if not server.ready.wait(3):
                raise TimeoutError("the installation test runtime did not become ready")
            yield
        finally:
            stop.set()
            running.result(timeout=25)


@contextmanager
def _installed_runtime(tmp_path: Path, served: _Served, login: InstallationLogin | None = None) -> Iterator[Path]:
    """Serve a storage root that holds no profile."""
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        with _serving(endpoint, root, served, InstallationLogin(owner=owner_id()) if login is None else login):
            yield root


@contextmanager
def _installed_runtime_with_profile(tmp_path: Path, served: _Served) -> Iterator[tuple[Path, UUID]]:
    """Serve a storage root that holds one real encrypted profile, yielding the root and the profile."""
    root = tmp_path / "cadrumo-storage"
    root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=root)
    installation = runtime_installation(
        storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        close_active_bucket_session()
        with _serving(endpoint, root, served, InstallationLogin(owner=owner_id()), secret_store=subject.native):
            yield root, subject.store.binding.profile_id


def _adapter(surface: McpSurface = _FULL) -> RuntimeMcpAdapter:
    """An adapter that holds no session and names no profile."""
    return RuntimeMcpAdapter(profile_id=None, client=None, surface=surface, resumes_sign_in=True)


def _held_items(store: MemoryNativePort) -> list[str]:
    return [account for namespace, account in store.items if namespace == HELD_SECRET_NAMESPACE]


def _private_in(private: str, reply: dict[str, Any], caplog: pytest.LogCaptureFixture) -> list[str]:
    """Name every place a private text reached: the reply, the log text or a log record's fields."""
    found = [] if private not in json.dumps(reply) else ["reply"]
    if private in caplog.text:
        found.append("log text")
    if any(private in repr(record.__dict__) for record in caplog.records):
        found.append("log record")
    return found


@pytest.mark.anyio
async def test_reads_complete_with_the_acts_typed_reply_and_no_session_is_held(tmp_path: Path) -> None:
    served = _Served()
    with _installed_runtime(tmp_path, served) as root:
        adapter = _adapter()
        try:
            checked = await adapter.call("installation", {"action": "storage_check"})
            tailed = await adapter.call(
                "installation", {"action": "repair_logs", "lines": INSTALLATION_LOG_TAIL_MAX_LINES}
            )
            status = await adapter.call("status", {})
        finally:
            await adapter.close()

    assert checked["outcome"] == "completed" and checked["act"] == "storage_check", checked
    reply = RuntimeStorageCheckReply.model_validate_json(json.dumps(checked["reply"]))
    assert reply.storage_root == str(root) and reply.healthy
    # A reply larger than one frame arrives whole.
    assert tailed["outcome"] == "completed"
    assert RuntimeRepairLogsReply.model_validate_json(json.dumps(tailed["reply"])).lines == LOG_LINES
    # The acts asked for no profile session, and none is held afterwards.
    assert status["session"] == "none" and status["authenticated"] is False
    assert adapter.client is None


@pytest.mark.anyio
async def test_a_changing_act_reports_until_it_is_confirmed_and_then_acts(tmp_path: Path) -> None:
    served = _Served()
    with _installed_runtime(tmp_path, served):
        adapter = _adapter()
        try:
            unconfirmed = await adapter.call("installation", {"action": "storage_reclaim", "area": "cache"})
            declined = await adapter.call(
                "installation", {"action": "storage_reclaim", "area": "cache", "confirm": False}
            )
            confirmed = await adapter.call(
                "installation", {"action": "storage_reclaim", "area": "cache", "confirm": True}
            )
        finally:
            await adapter.close()

    # Without confirm the runtime's own service refuses and says what a confirmed act would remove.
    assert unconfirmed["outcome"] == "refused" and unconfirmed["act"] == "storage_reclaim"
    assert unconfirmed["code"] == _UNCONFIRMED
    context = {entry["key"]: entry["value"] for entry in unconfirmed["error_detail"]["context"]}
    assert context["entry_count"] == "3" and context["area"] == "cache"
    assert declined == unconfirmed
    assert confirmed["outcome"] == "completed"
    reclaimed = RuntimeStorageReclaimReply.model_validate_json(json.dumps(confirmed["reply"]))
    assert (reclaimed.area.value, reclaimed.removed_entries) == ("cache", 3)
    assert served.reclaims == [("cache", False), ("cache", False), ("cache", True)]


@pytest.mark.anyio
async def test_an_inbound_secret_reaches_the_runtime_on_its_secret_frame_and_nowhere_else(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    served = _Served()
    caplog.set_level(logging.DEBUG)
    arguments = {
        "action": "archive_import",
        "label": "Restored",
        "path": str(tmp_path / "synthetic.cadrumo-archive"),
        "source_digest": "ab" * 32,
        "secret": _ARCHIVE_INPUT,
    }
    with _installed_runtime(tmp_path, served):
        adapter = _adapter()
        try:
            imported = await adapter.call("installation", dict(arguments))
            without = await adapter.call(
                "installation", {name: value for name, value in arguments.items() if name != "secret"}
            )
            unasked = await adapter.call("installation", {"action": "storage_check", "secret": _ARCHIVE_INPUT})
        finally:
            await adapter.close()

    assert imported["outcome"] == "completed", imported
    assert RuntimeArchiveImportReply.model_validate_json(json.dumps(imported["reply"])).label == "Restored"
    # The handler received exactly the passphrase the call carried, once.
    assert served.imports == [("Restored", True)]
    # An act that takes a secret is not sent without one, and no other act accepts one.
    assert without == {"outcome": "refused", "code": "invalid_request"}
    assert unasked == {"outcome": "refused", "code": "invalid_request"}
    for reply in (imported, without, unasked):
        assert _private_in(_ARCHIVE_INPUT, reply, caplog) == []


@pytest.mark.anyio
@pytest.mark.parametrize("tool", ["installation", "session"])
async def test_recovery_enrolment_holds_the_code_for_the_person_and_returns_only_its_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tool: str
) -> None:
    served, client_store = _Served(), MemoryNativePort()
    monkeypatch.setattr(mcp_runtime, "installed_automation_secret_store", lambda: client_store)
    caplog.set_level(logging.DEBUG)

    with _installed_runtime_with_profile(tmp_path, served) as (root, profile):
        arguments: dict[str, Any] = (
            {"action": "recovery_enroll", "profile_id": str(profile), "secret": PROFILE_INPUT}
            if tool == "installation"
            else {"action": "enable_recovery", "profile": str(profile), "secret": PROFILE_INPUT}
        )
        adapter = _adapter()
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                called = await sdk.call_tool(tool, arguments)
        finally:
            await adapter.close()
        enrolled = profile_recovery_status(profile_id=profile, root=root).enrolled
        reply = called.structured_content
        assert reply is not None and called.is_error is False, reply
        reference = UUID(reply["secret_reference"])
        custody = held_secret_custody(client_store)
        held = custody.read(reference)
        listed = [(entry.reference, entry.origin) for entry in custody.entries()]
        code = held.secret.get_secret_value().decode("utf-8")
        # The copy the person will read is the one the runtime enrolled: it opens the installed wrapper.
        unlock_profile_custody_recovery(
            load_profile_custody_recovery_material(profile, root=root), recovery_secret=code
        )

    assert reply["outcome"] == "completed" and reply["act"] == "recovery_enroll"
    outcome = RuntimeRecoveryEnrollReply.model_validate_json(json.dumps(reply["reply"]))
    assert (outcome.profile_id, outcome.enrolled, outcome.changed) == (str(profile), True, True)
    assert enrolled
    assert _held_items(client_store) == [str(reference)]
    assert held.origin == f"recovery_enroll profile_id={profile}"
    # The person can find it without knowing the reference: it is listed for this storage root.
    assert listed == [(reference, held.origin)]
    # The reply tells the agent where the code is and how the person reads it, and carries neither secret.
    assert f"cadrumo-mcp --show-held-secret {reference}" in reply["secret_retrieval"]
    assert set(reply) == {"outcome", "act", "reply", "secret_reference", "secret_retrieval"} | (
        {"session"} if tool == "session" else set()
    )
    for private in (code, PROFILE_INPUT):
        assert _private_in(private, reply, caplog) == []
        assert private not in called.model_dump_json()


@pytest.mark.anyio
async def test_a_refused_enrolment_holds_nothing_and_repeats_no_secret(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    served, client_store = _Served(), MemoryNativePort()
    monkeypatch.setattr(mcp_runtime, "installed_automation_secret_store", lambda: client_store)
    caplog.set_level(logging.DEBUG)
    wrong = "not-the-profile-password"

    with _installed_runtime_with_profile(tmp_path, served) as (root, profile):
        adapter = _adapter()
        try:
            refused = await adapter.call(
                "installation", {"action": "recovery_enroll", "profile_id": str(profile), "secret": wrong}
            )
        finally:
            await adapter.close()
        enrolled = profile_recovery_status(profile_id=profile, root=root).enrolled

    assert refused["outcome"] == "refused" and refused["act"] == "recovery_enroll", refused
    assert refused["code"] == refused["error_detail"]["error_code"]
    assert "secret_reference" not in refused
    assert not enrolled
    assert _held_items(client_store) == []
    assert _private_in(wrong, refused, caplog) == []


@pytest.mark.anyio
async def test_an_enrolment_whose_code_cannot_be_held_is_refused_and_installs_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    served, client_store = _Served(), MemoryNativePort()
    client_store.unavailable = True
    monkeypatch.setattr(mcp_runtime, "installed_automation_secret_store", lambda: client_store)

    with _installed_runtime_with_profile(tmp_path, served) as (root, profile):
        adapter = _adapter()
        try:
            refused = await adapter.call(
                "installation", {"action": "recovery_enroll", "profile_id": str(profile), "secret": PROFILE_INPUT}
            )
        finally:
            await adapter.close()
        enrolled = profile_recovery_status(profile_id=profile, root=root).enrolled

    # The runtime commits nothing under a code that nobody holds.
    assert refused == {"outcome": "refused", "code": "unavailable"}
    assert not enrolled


@pytest.mark.anyio
async def test_a_fault_an_unserved_act_and_a_locked_login_each_answer_with_the_runtimes_code(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    served, login = _Served(), InstallationLogin(owner=owner_id())
    caplog.set_level(logging.DEBUG)
    with _installed_runtime(tmp_path, served, login):
        adapter = _adapter()
        try:
            failed = await adapter.call("installation", {"action": "storage_init"})
            unserved = await adapter.call("installation", {"action": "storage_inventory"})
            login.lock_state = OsLockState.LOCKED
            locked = await adapter.call("installation", {"action": "storage_check"})
            login.lock_state = OsLockState.UNLOCKED
            # One act's refusal or fault leaves the next act served.
            again = await adapter.call("installation", {"action": "storage_check"})
        finally:
            await adapter.close()

    # A fault in an act that changes records may have changed some, so its effect is not claimed.
    assert failed == {"outcome": "unresolved", "code": "installation_failed", "act": "storage_init"}
    assert _private_in(FAULT_TEXT, failed, caplog) == []
    assert unserved == {"outcome": "refused", "code": "operation_unavailable"}
    assert locked == {"outcome": "refused", "code": "needs_user"}
    assert again["outcome"] == "completed"


@pytest.mark.anyio
async def test_the_narrowed_surface_serves_reads_and_reports_and_refuses_what_changes_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    served, client_store = _Served(), MemoryNativePort()
    monkeypatch.setattr(mcp_runtime, "installed_automation_secret_store", lambda: client_store)
    caplog.set_level(logging.DEBUG)
    denied = {"outcome": "refused", "code": "frontend_denied"}

    with _installed_runtime(tmp_path, served):
        adapter = _adapter(_READ_ONLY_LOCAL)
        try:
            read = await adapter.call("installation", {"action": "storage_check"})
            report = await adapter.call("installation", {"action": "storage_reclaim", "area": "logs"})
            change = await adapter.call("installation", {"action": "storage_reclaim", "area": "logs", "confirm": True})
            init = await adapter.call("installation", {"action": "storage_init"})
            imported = await adapter.call(
                "installation",
                {
                    "action": "archive_import",
                    "label": "Restored",
                    "path": str(tmp_path / "synthetic.cadrumo-archive"),
                    "source_digest": "ab" * 32,
                    "secret": _ARCHIVE_INPUT,
                },
            )
            enrol = await adapter.call(
                "installation", {"action": "recovery_enroll", "profile_id": str(uuid4()), "secret": PROFILE_INPUT}
            )
        finally:
            await adapter.close()

    assert read["outcome"] == "completed"
    assert report["outcome"] == "refused" and report["code"] == _UNCONFIRMED
    assert (change, init, imported, enrol) == (denied, denied, denied, denied)
    # Only the read and the unconfirmed report reached the runtime: the fault handler behind
    # storage_init never ran, no passphrase was taken, and nothing was held.
    assert served.reclaims == [("logs", False)] and served.imports == []
    assert "installation act failed" not in caplog.text
    assert _held_items(client_store) == []
    for private in (_ARCHIVE_INPUT, PROFILE_INPUT):
        assert all(_private_in(private, reply, caplog) == [] for reply in (imported, enrol))


@pytest.mark.anyio
async def test_the_narrowed_surface_refuses_recovery_through_the_session_tool_as_well(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    served, client_store = _Served(), MemoryNativePort()
    monkeypatch.setattr(mcp_runtime, "installed_automation_secret_store", lambda: client_store)

    with _installed_runtime_with_profile(tmp_path, served) as (root, profile):
        adapter = _adapter(_READ_ONLY_LOCAL)
        try:
            refused = await adapter.call(
                "session", {"action": "enable_recovery", "profile": str(profile), "secret": PROFILE_INPUT}
            )
        finally:
            await adapter.close()
        enrolled = profile_recovery_status(profile_id=profile, root=root).enrolled

    assert refused == {"outcome": "refused", "code": "frontend_denied"}
    assert not enrolled
    assert _held_items(client_store) == []


@pytest.mark.anyio
async def test_the_installed_tool_list_is_the_catalogue_and_a_refusal_is_an_error_result(tmp_path: Path) -> None:
    served = _Served()
    with _installed_runtime(tmp_path, served), override_settings(cadrumo_output_language="en"):
        adapter = _adapter()
        try:
            async with connected_server_and_client_session(build_server(adapter)) as sdk:
                tools = (await sdk.list_tools()).tools
                completed = await sdk.call_tool("installation", {"action": "storage_check"})
                refused = await sdk.call_tool("installation", {"action": "storage_reclaim", "area": "cache"})
                failed = await sdk.call_tool("installation", {"action": "storage_init"})
        finally:
            await adapter.close()

    assert [(tool.name, tool.description, tool.input_schema) for tool in tools] == [
        (name, description, schema) for name, description, schema in MCP_TOOL_CATALOGUE
    ]
    assert completed.is_error is False
    assert refused.is_error is True
    # A fault in an act that changes records leaves its effect unknown: no error, and told not to be repeated.
    assert failed.is_error is False and failed.structured_content is not None
    assert failed.structured_content["outcome"] == "unresolved"
    assert "Do not repeat this call" in failed.structured_content["unknown_outcome"]
