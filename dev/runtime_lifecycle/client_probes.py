"""Shared actual CLI-adjacent TUI, MCP and native protected-read probes."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import sys
import time
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from uuid import UUID, uuid4

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.local_runtime.automation_decision import AutomationDecisionRunError, run_automation_decision
from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError, frontend_failure_code
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.auth.auth_read_contracts import AuthReadProjection, AuthReadRequest
from cadrumo.application.diagnostics_read_contracts import DiagnosticsReadProjection, DiagnosticsReadRequest
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationPublicTerminalEventV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationContract,
    RuntimeOperationControl,
    RuntimeOperationObserve,
    RuntimeOperationObserved,
    RuntimeOperationProjected,
    RuntimeOperationResult,
    RuntimeOperationSubmit,
    RuntimeOperationSubmitted,
)
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.automation_enrollment import EnrollmentKind, EnrollmentProposal
from cadrumo.application.user_profile.automation_operations import AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.view_operation import ProfileViewPageKind
from cadrumo.core.operations import OperationLifecycle, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo.core.time.clock import now
from dev.packaging.command_execution import run_command

from .harness import Connection, LifecycleHarness, Profile

if TYPE_CHECKING:
    from cadrumo.adapters.local_runtime.windows_native_io import NativeWindowsHandle
    from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess, WindowsProcessScope

    from .installed import InstalledLifecycleHarness

# The package interpreter imports the production TUI adapter without mounting Textual.
_TUI_READ = """
import asyncio, json, sys
from uuid import UUID
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.adapters.persistence.storage.errors import KeyringUnavailableError
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.entrypoints.tui.profile.runtime_overview import read_runtime_profile_overview
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.models import OperationId
from cadrumo.application.runtime.contracts import RuntimeRefusalError
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
async def read():
    client = await open_installed_runtime_client(profile_id=UUID(sys.argv[1]), frontend=OperationFrontendProjection.TUI)
    try:
        await asyncio.to_thread(client.resume_receipt)
        view = await asyncio.to_thread(
            read_runtime_profile_overview, client, profile_label='Lifecycle', output_language=OutputLanguage.EN
        )
        print(json.dumps({'profile_id': str(client.profile_id), 'sections': len(view.sections)}))
    finally:
        await asyncio.to_thread(client.close)
try:
    with composed_profile_persistence_ports():
        asyncio.run(read())
except (RuntimeFrontendRefusedError, RuntimeRefusalError, ProfileReceiptRefusedError) as error:
    reason = error.reason
    print(json.dumps({'refused': getattr(reason, 'value', reason)}))
    sys.exit(2)
except KeyringUnavailableError as error:
    print(json.dumps({'refused': get_registered_error_code(error).code}))
    sys.exit(2)
"""


def _tui(harness: LifecycleHarness, profile: Profile, *, admitted: bool) -> None:
    result = run_command(
        [str(harness.package / "python.exe"), "-I", "-c", _TUI_READ, str(profile.profile_id)],
        cwd=harness.root,
        environment=child_environment(ChildEnvironmentProfile.STRICT, harness.root),
        timeout_seconds=90,
    )
    if admitted:
        if not (result.returncode == 0):
            raise AssertionError("Packaged TUI protected overview failed")
        document = json.loads(result.stdout)
        if not (document["profile_id"] == str(profile.profile_id) and document["sections"] > 0):
            raise AssertionError("Protected application probe failed")
    else:
        stderr = result.stderr.decode("utf-8", errors="replace") if isinstance(result.stderr, bytes) else result.stderr
        errors = stderr.splitlines()
        failure = errors[-1].partition(":")[0] if errors else "no stderr"
        if not (result.returncode == 2):
            raise AssertionError(f"TUI exit {result.returncode}; {failure}")
        document = json.loads(result.stdout)
        if not (set(document) == {"refused"}):
            raise AssertionError("Protected application probe failed")
        if document["refused"] not in {
            "absent",
            "authentication_required",
            "credential_rejected",
            "session_inactive",
            "runtime_unavailable",
            "endpoint_not_ready",
            "unavailable",
            "connection_closed",
            "receipt_unavailable",
            "AUTH_STORAGE_KEYRING_UNAVAILABLE",
        }:
            raise AssertionError("Protected application probe failed")


async def _call(
    client: ClientSession, name: str, arguments: dict[str, Any], *, admitted: bool = True
) -> dict[str, Any]:
    reply = await client.call_tool(name, arguments)
    if not (isinstance(reply.structured_content, dict)):
        raise AssertionError("Protected application probe failed")
    document = reply.structured_content
    if not (reply.is_error is not admitted):
        raise AssertionError(
            f"MCP {name} admission differed: {document.get('outcome', 'unreported')} "
            f"{document.get('code', 'unreported')}"
        )
    if not admitted and not (document["outcome"] == "refused" and isinstance(document["code"], str)):
        raise AssertionError("Protected application probe failed")
    return document


async def _mcp_read(client: ClientSession, profile: Profile) -> None:
    described = await _call(client, "describe", {"definition_id": "auth.local-read"})
    contract = described["description"]["contract"]
    submitted = await _call(
        client,
        "execute",
        {
            "definition_id": "auth.local-read",
            "subject_ref": profile_operation_subject(str(profile.profile_id)),
            "payload": {"profile_id": str(profile.profile_id), "kind": "status"},
        },
    )
    operation_id = submitted["receipt"]["operation_id"]
    deadline = time.monotonic() + 60
    while True:
        observed = await _call(
            client, "observe", {"observation": {"operation_id": operation_id, "after_cursor": 0, "page_limit": 32}}
        )
        observation = OperationObservationSuccessV1.model_validate_json(json.dumps(observed["reply"]["observation"]))
        projection = observation.projection
        if projection.lifecycle.value == "terminal":
            break
        if not (time.monotonic() < deadline):
            raise AssertionError("Protected application probe failed")
        await asyncio.sleep(0.05)
    terminal = projection.terminal_condition
    failure_codes = tuple(
        event.failure_error_code
        for event in observation.event_page.events
        if isinstance(event, OperationPublicTerminalEventV1) and event.failure_error_code is not None
    )
    if not (terminal is not None and terminal.value == "succeeded"):
        raise AssertionError(f"MCP private operation terminal={terminal}; failure_codes={failure_codes}")
    result = await _call(
        client,
        "result",
        {
            "result": {
                "operation_id": operation_id,
                "terminal_revision": projection.revision,
                "definition_contract_digest": contract["definition_contract_digest"],
                "result_schema": contract["result_schema"],
            }
        },
    )
    body = AuthReadProjection.model_validate_json(json.dumps(result["document"]["projection"]))
    if not (body.profile_id == profile.profile_id and body.status is not None):
        raise AssertionError("Protected application probe failed")


def _observe_read(
    connection: Connection, operation_id: OperationId, definition_id: str = "auth.local-read"
) -> OperationObservationSuccessV1:
    reply = connection.client.operation(
        RuntimeOperationObserve(
            request_id=uuid4(),
            profile_id=connection.client.profile_id,
            session_id=connection.client.session_id,
            observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
        ),
        deadline=time.monotonic() + 10,
    )
    if not (isinstance(reply, RuntimeOperationObserved)):
        raise AssertionError("Protected durable-operation probe failed")
    if not (isinstance(reply.observation, OperationObservationSuccessV1)):
        raise AssertionError("Protected durable-operation probe failed")
    if not (reply.observation.projection.definition_id == definition_id):
        raise AssertionError("Protected durable-operation probe failed")
    if not (reply.observation.projection.operation_id == operation_id):
        raise AssertionError("Protected durable-operation probe failed")
    return reply.observation


def _submit_read(connection: Connection, *, diagnostics: bool = False) -> OperationId:
    deadline = time.monotonic() + 60
    client = connection.client
    submitted = client.operation(
        RuntimeOperationSubmit(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            definition_id="diagnostics.read" if diagnostics else "auth.local-read",
            subject_ref=profile_operation_subject(str(client.profile_id)),
            payload_json=(
                DiagnosticsReadRequest(profile_id=client.profile_id, kind="errors")
                if diagnostics
                else AuthReadRequest(profile_id=client.profile_id, kind="status")
            ).model_dump_json(),
        ),
        deadline=deadline,
    )
    if not (isinstance(submitted, RuntimeOperationSubmitted)):
        raise AssertionError("Protected durable-operation probe failed")
    return submitted.receipt.operation_id


def _execute_read(connection: Connection, operation_id: OperationId | None = None) -> OperationId:
    # Abrupt owner loss retains the production ten-minute lease. Fresh authority
    # cannot steal it; only the canonical expired-lease path admits continuation.
    deadline = time.monotonic() + (660 if operation_id is not None else 60)
    client = connection.client
    definition_id = "diagnostics.read" if operation_id is not None else "auth.local-read"
    contract = client.contract(definition_id, deadline=deadline)
    if not (contract.result_schema is not None):
        raise AssertionError("Protected durable-operation probe failed")
    continuing = operation_id is not None
    if operation_id is None:
        operation_id = _submit_read(connection)
    while True:
        try:
            started = client.operation(
                RuntimeOperationControl(
                    action="operation_resume" if continuing else "operation_start",
                    request_id=uuid4(),
                    profile_id=client.profile_id,
                    session_id=client.session_id,
                    operation_id=operation_id,
                ),
                deadline=deadline,
            )
            break
        except RuntimeFrontendRefusedError as refusal:
            if not continuing or refusal.reason != "operation_unavailable" or time.monotonic() >= deadline:
                raise
            if (
                _observe_read(connection, operation_id, definition_id).projection.lifecycle
                is not OperationLifecycle.CREATED
            ):
                raise AssertionError("Protected durable-operation probe failed") from None
            time.sleep(2)
    if not (isinstance(started, RuntimeOperationAcknowledged)):
        raise AssertionError("Protected durable-operation probe failed")
    while True:
        projection = _observe_read(connection, operation_id, definition_id).projection
        if projection.lifecycle is OperationLifecycle.TERMINAL:
            break
        if not (time.monotonic() < deadline):
            raise AssertionError("Protected read did not settle")
        time.sleep(0.05)
    if projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        raise AssertionError("Protected durable-operation probe failed")
    reply = client.operation(
        RuntimeOperationResult(
            request_id=uuid4(),
            profile_id=client.profile_id,
            session_id=client.session_id,
            result=OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=projection.revision,
                definition_contract_digest=contract.definition_contract_digest,
                result_schema=contract.result_schema,
            ),
        ),
        deadline=deadline,
    )
    if not (isinstance(reply, RuntimeOperationProjected)):
        raise AssertionError("Protected durable-operation probe failed")
    if not (reply.operation_id == operation_id and reply.projection_kind == "result"):
        raise AssertionError("Protected durable-operation probe failed")
    result = OperationResultProjectionSuccessV1[AuthReadProjection | DiagnosticsReadProjection].model_validate_json(
        json.dumps(reply.document)
    )
    if not (result.definition_contract_digest == contract.definition_contract_digest):
        raise AssertionError("Protected durable-operation probe failed")
    if not (result.result_schema == contract.result_schema):
        raise AssertionError("Protected durable-operation probe failed")
    if not (result.projection.profile_id == client.profile_id):
        raise AssertionError("Protected durable-operation probe failed")
    if continuing:
        if not (isinstance(result.projection, DiagnosticsReadProjection)):
            raise AssertionError("Protected durable-operation probe failed")
        if not (result.projection.kind == "errors" and result.projection.errors is not None):
            raise AssertionError("Protected durable-operation probe failed")
    else:
        if not (isinstance(result.projection, AuthReadProjection)):
            raise AssertionError("Protected durable-operation probe failed")
        if not (result.projection.kind == "status" and result.projection.status is not None):
            raise AssertionError("Protected durable-operation probe failed")
    return operation_id


def _read(connection: Connection) -> None:
    result = connection.client.read_profile_view((ProfileViewPageKind.STATUS,), timeout=60)
    if not (result.profile_id == connection.client.profile_id):
        raise AssertionError("Protected application probe failed")
    if not (result.record_revision >= 1):
        raise AssertionError("Protected application probe failed")
    if not (result.pages and all(page.outcome == "page" for page in result.pages)):
        raise AssertionError("Protected application probe failed")
    # The actual AEAT local-auth operation is registered under this live session.
    contract = connection.client.contract("auth.local-read", deadline=time.monotonic() + 10)
    if not (contract.definition_id == "auth.local-read"):
        raise AssertionError("Protected application probe failed")


def _private_request(connection: Connection, session_id: UUID, *, profile_id: UUID | None = None) -> object:
    return connection.wire.operation(
        RuntimeOperationContract(
            request_id=uuid4(),
            profile_id=profile_id or connection.client.profile_id,
            session_id=session_id,
            definition_id="auth.local-read",
        ),
        deadline=time.monotonic() + 5,
    )


def _refused(reply: object) -> None:
    # A denial must originate at the server, not a cleared frontend attribute.
    if not (isinstance(reply, RuntimeAccessRefusal)):
        raise AssertionError("Protected application probe failed")
    if reply.code.value not in {
        "authentication_required",
        "connection_mismatch",
        "credential_rejected",
        "custody_changed",
        "profile_mismatch",
        "runtime_changed",
        "session_expired",
        "session_inactive",
    }:
        raise AssertionError(f"Unexpected server refusal: {reply.code.value}")


async def _enroll(harness: LifecycleHarness, client: ClientSession, profile: Profile) -> UUID:
    prepared = await _call(client, "authorization_prepare", {})
    destination = UUID(prepared["destination_id"])
    expires = now() + timedelta(minutes=30)
    scope = AccessScope(
        operations=frozenset({"auth.local-read"}),
        actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.OBSERVE, AccessAction.RESULT}),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=destination,
                    projection_id="auth.local-read.result",
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
                DisclosurePermission(
                    destination_id=destination,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )
    proposal = EnrollmentProposal(
        kind=EnrollmentKind.ENROLL,
        scope=scope,
        expires_at=expires,
        key_expires_at=expires,
        # API-key admission requires an explicitly approved unattended grant.
        unattended=True,
        allow_os_lock=False,
    )
    submitted = await _call(client, "authorization_request", {"proposal": proposal.model_dump(mode="json")})
    human = harness.connect(profile.profile_id)
    human.client.resume_receipt()
    inventory = read_automation_inventory(human.client).projection
    review = next(
        item for item in inventory.requests if str(item.receipt.request_id) == submitted["receipt"]["request_id"]
    )
    approval = asyncio.create_task(
        asyncio.to_thread(
            run_automation_decision,
            human.client,
            review,
            decision="approve",
            password=bytearray(profile.password, "utf-8"),
        )
    )
    diagnostic_deadline = asyncio.get_running_loop().time() + 120
    primary: BaseException | None = None
    try:
        async with asyncio.timeout(120):
            while True:
                polled = await _call(client, "authorization_poll", {})
                reference = polled["receipt"]["credential_reference"]
                if reference is not None:
                    harness.resources.callback(installed_automation_secret_store().delete, CLIENT_NAMESPACE, reference)
                if polled["receipt"]["stage"] == "complete":
                    if reference is None:
                        raise AssertionError("Completed enrollment has no credential reference")
                    if (await approval).effect.value != "updated":
                        raise AssertionError("Enrollment approval did not update native custody")
                    return UUID(reference)
                await asyncio.sleep(0.05)
    except BaseException as error:
        primary = error
        raise
    finally:
        # A native approval may have published; join it before releasing its connection.
        try:
            await approval
        except AutomationDecisionRunError as error:
            facts = {
                "code": error.reason,
                "terminal_condition": "unknown" if error.terminal_condition is None else error.terminal_condition.value,
                "effect": "unknown" if error.effect is None else error.effect.value,
                "observation": "no_remaining_budget",
            }
            if diagnostic_deadline - asyncio.get_running_loop().time() >= 10:
                try:
                    observed = await asyncio.to_thread(
                        _observe_read, human, error.operation_id, AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
                    )
                    state = observed.projection
                    facts.update(
                        observation="observed",
                        lifecycle=state.lifecycle.value,
                        phase_code=state.phase_code or "unknown",
                        failure_error_code=state.failure_error_code or "unknown",
                        terminal_condition="unknown"
                        if state.terminal_condition is None
                        else state.terminal_condition.value,
                        effect=state.effect.value,
                    )
                except Exception as observation_error:
                    facts.update(observation="unavailable", observation_code=frontend_failure_code(observation_error))
            # Emit only bounded public codes; no exception context or private operands.
            codes = {
                "unknown",
                "unreported",
                "decision_unsettled",
                "REFUSED_AUTOMATION_ADMINISTRATION",
                *(code.value for code in RuntimeRefusalCode),
                *(code.value for code in AccessDenialCode),
                *(code.value for code in AutomationCustodyCode),
            }
            for key in ("code", "failure_error_code", "observation_code"):
                if key in facts and facts[key] not in codes:
                    facts[key] = "unreported"
            if "phase_code" in facts and facts["phase_code"] not in {
                "unknown",
                AUTOMATION_APPROVE_OPERATION_DEFINITION_ID + ".execute",
            }:
                facts["phase_code"] = "unreported"
            error.add_note("approval_failure " + json.dumps(facts, sort_keys=True))
            if primary is not None and primary is not error:
                raise BaseExceptionGroup("Enrollment requester and approval failed", [primary, error]) from None
            raise


async def _mcp_refuse_profile(client: ClientSession, profile: Profile) -> None:
    crossed = await _call(
        client,
        "execute",
        {
            "definition_id": "auth.local-read",
            "subject_ref": profile_operation_subject(str(profile.profile_id)),
            "payload": {"profile_id": str(profile.profile_id), "kind": "status"},
        },
        admitted=False,
    )
    if crossed["code"] not in {"profile_mismatch", "operation_denied", "invalid_request"}:
        raise AssertionError("MCP cross-profile probe returned an unexpected refusal")


async def installed_mcp_read(harness: InstalledLifecycleHarness, profile: Profile, *, admitted: bool) -> None:
    """Probe the shipping MCP server with the real shared human receipt."""
    parameters = StdioServerParameters(
        command=str(harness.package / "bin/cadrumo-mcp.exe"),
        args=[],
        cwd=harness.root,
        env=child_environment(ChildEnvironmentProfile.STRICT, harness.root),
    )
    with (harness.root / "installed-mcp.stderr").open("a", encoding="utf-8") as errors:
        async with (
            stdio_client(parameters, errlog=errors) as (reader, writer),
            ClientSession(reader, writer, read_timeout_seconds=90) as client,
        ):
            await client.initialize()
            if admitted:
                await _mcp_read(client, profile)
            else:
                await _call(client, "describe", {"definition_id": "auth.local-read"}, admitted=False)


async def installed_mcp_key_read(harness: InstalledLifecycleHarness, profile: Profile) -> None:
    """Require genuine protected enrollment and a profile-bound shipping MCP key."""
    other = await asyncio.to_thread(harness.create_profile, "Installed scope refusal")
    harness.resources.callback(delete_profile_session, storage_root=harness.root, profile_id=other.profile_id)
    await asyncio.to_thread(
        harness.cli, "login", "Installed acceptance", "--secrets-stdin", secret={"passphrase": profile.password}
    )
    parameters = StdioServerParameters(
        command=str(harness.package / "bin/cadrumo-mcp.exe"),
        args=["--profile-id", str(profile.profile_id)],
        cwd=harness.root,
        env=child_environment(ChildEnvironmentProfile.STRICT, harness.root),
    )
    with (harness.root / "installed-mcp-key.stderr").open("a", encoding="utf-8") as errors:
        async with (
            stdio_client(parameters, errlog=errors) as (reader, writer),
            ClientSession(reader, writer, read_timeout_seconds=90) as client,
        ):
            await client.initialize()
            await _call(client, "describe", {"definition_id": "auth.local-read"}, admitted=False)
            reference = await _enroll(harness, client, profile)
            await _call(client, "authenticate", {"credential_reference": str(reference)})
            await _mcp_read(client, profile)
            await _mcp_refuse_profile(client, other)


def installed_protected_read(harness: InstalledLifecycleHarness, profile: Profile, connection: Connection) -> None:
    """Require native, CLI, production TUI adapter and MCP authenticated reads."""
    _read(connection)
    if not (
        harness.cli("profile", "view", profile_secret=profile.password)["result"]["display_name"]
        == "Installed acceptance"
    ):
        raise AssertionError("Protected application probe failed")
    _tui(harness, profile, admitted=True)
    asyncio.run(installed_mcp_read(harness, profile, admitted=True))


def _desktop_events(root: Path, pid: int) -> list[dict[str, Any]]:
    events = []
    for path in root.rglob("cadrumo-native.jsonl"):
        with path.open("rb") as stream:
            stream.seek(max(0, path.stat().st_size - 65536))
            for line in stream.read(65536).splitlines():
                try:
                    event = json.loads(line)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
                if isinstance(event, dict) and event.get("hostPid") == pid:
                    events.append(event)
    return events


def takeover_confirmed(events: list[dict[str, Any]], runtime_pid: int, after: int) -> bool:
    """Require all post-loss core readiness facts for this verified incarnation."""
    facts = {
        fact.get("event")
        for event in events
        if event.get("stage") == "supervision"
        and type(event.get("sequence")) is int
        and event["sequence"] > after
        and isinstance(fact := event.get("lifecycle"), dict)
        and fact.get("pid") == runtime_pid
    }
    return {"launched", "ready", "boot_record_confirmed"} <= facts


def _settle_takeover(
    scope: WindowsProcessScope,
    desktop: WindowsOwnedProcess | None,
    original: NativeWindowsHandle | None,
    lost: bool,
    deadline: float,
) -> None:
    """Drain the shipping host before forcing its Job and exact adopted survivor."""
    import win32event
    import win32process

    from cadrumo.application.runtime.contracts import RuntimeRefusalCode

    try:
        if desktop is not None:
            try:
                desktop.wait(timeout=max(0, deadline + 35 - time.monotonic()))
            except RuntimeRefusalError as error:
                if error.reason != RuntimeRefusalCode.DEADLINE_EXCEEDED:
                    raise
    finally:
        try:
            scope.terminate(timeout=15)
        finally:
            if original is not None:
                try:
                    if lost:
                        stopped = win32event.WaitForSingleObject(int(original), 0)
                        if stopped == win32event.WAIT_TIMEOUT:
                            win32process.TerminateProcess(int(original), 73)
                            stopped = win32event.WaitForSingleObject(int(original), 10_000)
                        if stopped != win32event.WAIT_OBJECT_0:
                            raise AssertionError("Original adopted runtime did not settle during takeover cleanup")
                except BaseException as error:
                    # Keep the exact incarnation available for failed-owner recovery.
                    error.__dict__["_takeover_runtime_handle"] = original
                    raise
                else:
                    original.Close()


def exercise_cadrumo_takeover(
    harness: InstalledLifecycleHarness, profile: Profile, *, after_boot: UUID | None = None
) -> UUID:
    """Prove shipping Cadrumo takes custody after actual installed-manager loss."""
    import win32api
    import win32con

    from cadrumo.adapters.local_runtime.windows_native_io import owned_windows_handle, windows_image_path
    from cadrumo.adapters.local_runtime.windows_process import WindowsProcessScope
    from cadrumo.application.runtime.contracts import RuntimeRefusalCode

    from .installed import require_interactive_token

    def running(process: WindowsOwnedProcess) -> None:
        try:
            code = process.wait(timeout=0)
        except RuntimeRefusalError as error:
            if error.reason != RuntimeRefusalCode.DEADLINE_EXCEEDED:
                raise
        else:
            raise AssertionError(f"Takeover process exited prematurely: exit={code}")

    old = harness.connect(profile.profile_id) if after_boot is None else None
    environment = {
        key: value
        for key, value in harness.native_environment().items()
        if key.upper() not in {"CADRUMO_AUTHORITY_ROOT", "CADRUMO_DESKTOP_PACKAGE_ROOT"}
    }
    scope = WindowsProcessScope()
    desktop = None
    original = None
    lost = False
    deadline = time.monotonic() + 90
    try:
        desktop = scope.launch(
            executable=harness.package / "cadrumo.exe",
            arguments=("--check-health", "--hold-seconds", "60"),
            directory=harness.package,
            environment=environment,
        )
        while not any(
            event.get("stage") == "manager" and event.get("outcome") == "ready"
            for event in _desktop_events(harness.root, desktop.pid)
        ):
            running(desktop)
            if old is not None:
                running(harness.process)
            if time.monotonic() >= deadline:
                raise TimeoutError("Shipping Cadrumo did not verify the installed supervisor")
            time.sleep(0.05)
        if old is not None:
            running(harness.process)
        after = (
            max((event["sequence"] for event in _desktop_events(harness.root, desktop.pid)), default=0)
            if old is not None
            else 0
        )
        # This is a fixed acceptance bound, not an extension of the GUI hold.
        deadline = time.monotonic() + 60
        if old is not None:
            if type(old.native.peer.process_id) is not int:
                raise AssertionError("Installed runtime lacks a native process identity")
            original = owned_windows_handle(
                win32api.OpenProcess(
                    win32con.PROCESS_TERMINATE | win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE,
                    False,
                    old.native.peer.process_id,
                )
            )
            old.native.verify_peer_process(int(original))
            if not harness.owns_runtime(old, int(original)):
                raise AssertionError("Installed runtime lacks its actual retained manager parent")
            lost = True
            harness.lose_manager()
        live = harness.connect(
            profile.profile_id, after_boot=old.wire.hello.boot_id if old is not None else after_boot, timeout=45
        )
        running(desktop)
        runtime_pid = live.native.peer.process_id
        if type(runtime_pid) is not int:
            raise AssertionError("Recovered runtime lacks a native process identity")
        with_exit = owned_windows_handle(
            win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, desktop.pid)
        )
        try:
            runtime = owned_windows_handle(
                win32api.OpenProcess(
                    win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, runtime_pid
                )
            )
            try:
                live.native.verify_peer_process(int(runtime))
                if (
                    windows_image_path(with_exit) != (harness.package / "cadrumo.exe").resolve()
                    or not scope.contains_process(int(with_exit))
                    or not scope.contains_process(int(runtime))
                    or not harness.owns_runtime(live, int(runtime), parent=desktop, parent_handle=int(with_exit))
                    or require_interactive_token(int(runtime), live.native.peer.os_owner_id)
                    != require_interactive_token(int(with_exit), live.native.peer.os_owner_id)
                ):
                    raise AssertionError("Recovered runtime lacks genuine Cadrumo parent, token and Job custody")
            finally:
                runtime.Close()
        finally:
            with_exit.Close()
        while not takeover_confirmed(_desktop_events(harness.root, desktop.pid), runtime_pid, after):
            running(desktop)
            if time.monotonic() >= deadline:
                raise TimeoutError("Cadrumo takeover did not restore confirmed heartbeat supervision")
            time.sleep(0.05)
        live.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
        installed_protected_read(harness, profile, live)
        running(desktop)
        if time.monotonic() >= deadline:
            raise TimeoutError("Authenticated Cadrumo takeover exceeded its fixed observation window")
        if desktop.wait(timeout=max(0, deadline + 35 - time.monotonic())) != 0:
            raise AssertionError("Cadrumo takeover health or owned shutdown failed")
        if scope.active_process_ids():
            raise AssertionError("Cadrumo takeover left surviving owned processes")
    finally:
        _settle_takeover(scope, desktop, original, lost, deadline)
    if old is None:
        return live.wire.hello.boot_id
    if harness.intent["scope"] == "machine":
        harness.control_service(start=True)
    harness.start_manager()
    restored = harness.connect(profile.profile_id)
    restored.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
    installed_protected_read(harness, profile, restored)
    return restored.wire.hello.boot_id


def exercise_installed_manager(
    installed_harness: InstalledLifecycleHarness,
    *,
    leave_running: bool = False,
    profile: Profile | None = None,
) -> Profile:
    """Real install/repair/recovery/unregister; boot/login and upgrade evidence remain separate."""
    import asyncio

    harness = installed_harness
    profile = profile or harness.create_profile("Installed acceptance")

    live = harness.connect(profile.profile_id)
    _refused(_private_request(live, uuid4()))
    harness.cli("profile", "view", expect_success=False)
    _tui(harness, profile, admitted=False)
    asyncio.run(installed_mcp_read(harness, profile, admitted=False))
    live.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
    installed_protected_read(harness, profile, live)
    asyncio.run(installed_mcp_key_read(harness, profile))
    live = harness.connect(profile.profile_id)
    live.client.resume_receipt()
    old_session = live.client.session_id
    old_boot = live.wire.hello.boot_id
    harness.terminate_runtime(live)
    recovered = harness.connect(profile.profile_id, after_boot=old_boot)
    try:
        _private_request(live, old_session)
    except RuntimeRefusalError:
        pass
    else:
        raise AssertionError("Old native connection retained protected access")
    _refused(_private_request(recovered, old_session))
    recovered.client.resume_receipt()
    installed_protected_read(harness, profile, recovered)
    signed_out_session = recovered.client.session_id
    recovered.client.human_sign_out()
    _refused(_private_request(recovered, signed_out_session))
    harness.cli("profile", "view", expect_success=False)
    _tui(harness, profile, admitted=False)
    asyncio.run(installed_mcp_read(harness, profile, admitted=False))
    if harness.intent["scope"] == "machine":
        last_boot = recovered.wire.hello.boot_id
        harness.control_service(start=False)
        harness.cli("profile", "view", profile_secret=profile.password, expect_success=False)
        _tui(harness, profile, admitted=False)
        asyncio.run(installed_mcp_read(harness, profile, admitted=False))
        harness.control_service(start=True)
        harness.start_manager()
        restarted = harness.connect(profile.profile_id, after_boot=last_boot)
        restarted.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
        installed_protected_read(harness, profile, restarted)
        last_boot = restarted.wire.hello.boot_id
        harness.control_service(start=False)
        repair = harness.maintenance("install")
        if not (repair["outcome"] == "already_published_verified"):
            raise AssertionError("Stopped service was not repaired by its exact existing native owner")
        harness.verify_registration()
        harness.start_manager()
        repaired = harness.connect(profile.profile_id, after_boot=last_boot)
        repaired.client.resume_receipt()
        installed_protected_read(harness, profile, repaired)
    exercise_cadrumo_takeover(harness, profile)
    if leave_running:
        held = harness.connect(profile.profile_id)
        held.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
        installed_protected_read(harness, profile, held)
        return profile
    harness.stop_manager()
    harness.cli("profile", "view", profile_secret=profile.password, expect_success=False)
    _tui(harness, profile, admitted=False)
    asyncio.run(installed_mcp_read(harness, profile, admitted=False))
    return profile


def verify_prelogin_boot(instance: InstalledLifecycleHarness, account_sid: str) -> None:
    """Observe a live machine broker before genuine user logons or workers exist."""
    import win32api
    import win32com.client
    import win32con
    import win32event
    import win32security
    import win32service
    import win32ts

    from cadrumo.adapters.local_runtime.windows_login_native import (
        read_windows_logon,
        windows_desktop_sessions,
        windows_logon_ids,
    )
    from cadrumo.adapters.local_runtime.windows_native_io import owned_windows_handle, windows_image_path

    if instance.intent["scope"] != "machine":
        raise ValueError("Prelogin boot acceptance requires the machine installation")
    sessions, logons = windows_desktop_sessions(), windows_logon_ids()
    for session, _ in sessions:
        username = win32ts.WTSQuerySessionInformation(win32ts.WTS_CURRENT_SERVER_HANDLE, session, win32ts.WTSUserName)
        if not isinstance(username, str) or username:
            raise ValueError("Prelogin boot has a user-associated WTS session")
    for authentication in logons:
        # LsaGetLogonSessionData documents zero data for this exact LocalSystem LUID:
        # https://learn.microsoft.com/windows/win32/api/ntsecapi/nf-ntsecapi-lsagetlogonsessiondata
        if authentication == 0x3E7:
            continue
        logon = read_windows_logon(authentication)
        if logon.owner == account_sid and logon.kind in (2, 10, 11, 12):
            raise ValueError("Prelogin boot already has an interactive account logon")
    wmi = win32com.client.GetObject("winmgmts:")
    for candidate in wmi.ExecQuery(
        "SELECT ProcessId FROM Win32_Process WHERE Name='cadrumo-manager.exe' OR Name='cadrumo-runtime.exe'"
    ):
        handle = owned_windows_handle(
            win32api.OpenProcess(
                win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, candidate.ProcessId
            )
        )
        try:
            if windows_image_path(handle) in (instance.manager.resolve(), instance.runtime_image.resolve()):
                raise ValueError("Prelogin boot already has an installed user worker or runtime")
        finally:
            handle.Close()
    instance.verify_registration()
    for expected in instance.registration["services"]:
        with instance.service(expected) as service:
            status = cast(dict[str, int], win32service.QueryServiceStatusEx(service))
            if status["CurrentState"] != win32service.SERVICE_RUNNING or status["ProcessId"] <= 0:
                raise ValueError("Prelogin broker is not running")
            handle = owned_windows_handle(
                win32api.OpenProcess(
                    win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, status["ProcessId"]
                )
            )
            try:
                token = win32security.OpenProcessToken(int(handle), win32security.TOKEN_QUERY)
                try:
                    sid, _ = win32security.GetTokenInformation(token, win32security.TokenUser)
                    owner = win32security.ConvertSidToStringSid(sid)
                finally:
                    win32api.CloseHandle(token)
                if (
                    owner != "S-1-5-18"
                    or windows_image_path(handle) != (instance.prefix / instance.manager.name).resolve()
                    or win32event.WaitForSingleObject(int(handle), 0) != win32event.WAIT_TIMEOUT
                    or cast(dict[str, int], win32service.QueryServiceStatusEx(service)) != status
                ):
                    raise ValueError("Prelogin broker process differs from the configured native SCM owner")
            finally:
                handle.Close()

    if windows_desktop_sessions() != sessions or windows_logon_ids() != logons:
        raise ValueError("Prelogin native session inventory changed during broker verification")
    for session, _ in sessions:
        if win32ts.WTSQuerySessionInformation(win32ts.WTS_CURRENT_SERVER_HANDLE, session, win32ts.WTSUserName) != "":
            raise ValueError("Prelogin WTS user identity changed during broker verification")


def campaign_binding(plan: Path, runner: Path, vm_id: UUID, account_sid: str, guest_kind: str) -> dict[str, str]:
    """Bind persisted test ownership to immutable artifacts and the selected native identity."""
    intent = json.loads(plan.read_text(encoding="utf-8"))
    return {
        "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(runner.read_bytes()).hexdigest(),
        "vm_id": str(vm_id),
        "account_sid": account_sid,
        "scope": intent["scope"],
        "guest_kind": guest_kind,
    }


def validate_conflicting_plan(original: dict[str, Any], candidate: dict[str, Any]) -> None:
    """Require actual sibling-scope artifacts, never a different cohort or occupied owner."""
    if (
        candidate.get("scope") not in {"machine", "user"}
        or candidate["scope"] == original["scope"]
        or candidate.get("version") != original["version"]
        or candidate.get("manifest_sha256") != original["manifest_sha256"]
        or candidate.get("contract") != original["contract"]
        or Path(candidate["prefix"]).resolve() == Path(original["prefix"]).resolve()
    ):
        raise ValueError(
            "Scope conflict requires distinct prefixes and real opposite-scope artifacts of the same cohort"
        )


def _scope_products(instance: InstalledLifecycleHarness, *, absent: bool) -> None:
    import win32com.client

    installer = win32com.client.Dispatch("WindowsInstaller.Installer")
    for role in ("version_product", "registration_product"):
        # These exact same-account/machine product identities are already bound by the native plan.
        if installer.ProductState(instance.intent[role]["product_code"]) != (-1 if absent else 5):
            raise ValueError("Native MSI role state differs from the campaign's original/candidate ownership")
    instance.verify_registration(absent=absent)
    if absent and instance.prefix.exists() and any(instance.prefix.iterdir()):
        raise ValueError("Scope conflict candidate prefix is occupied")


def _scope_observation(instance: InstalledLifecycleHarness, profile: Profile) -> dict[str, Any]:
    """Retain actual owner identities without substituting an elevated caller's LUID."""
    import win32api
    import win32com.client
    import win32con
    import win32process

    from cadrumo.adapters.local_runtime.windows_native_io import owned_windows_handle, windows_image_path
    from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess

    from .installed import require_interactive_token

    live = instance.connect(profile.profile_id, timeout=1)
    pid = live.native.peer.process_id
    if type(pid) is not int:
        raise ValueError("Scope conflict original runtime has no native process identity")
    runtime = owned_windows_handle(
        win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, pid)
    )
    instance.resources.callback(runtime.Close)
    live.native.verify_peer_process(int(runtime))
    parent_pid = win32com.client.GetObject("winmgmts:").Get('Win32_Process.Handle="' + str(pid) + '"').ParentProcessId
    parent = owned_windows_handle(
        win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE, False, parent_pid)
    )
    instance.resources.callback(parent.Close)
    token = require_interactive_token(int(runtime), live.native.peer.os_owner_id)
    parent_token = require_interactive_token(int(parent), live.native.peer.os_owner_id)
    if (
        token != parent_token
        or windows_image_path(parent) != instance.manager.resolve()
        or not instance.owns_runtime(
            live,
            int(runtime),
            parent=WindowsOwnedProcess(handle=int(parent), pid=parent_pid),
            parent_handle=int(parent),
        )
        or (instance.intent["scope"] == "machine" and not instance.worker_of_broker(parent_pid, int(parent)))
    ):
        raise ValueError("Scope conflict lacks the exact actual installed manager/runtime owner")
    return {
        "boot": str(live.wire.hello.boot_id),
        "runtime_pid": pid,
        "manager_pid": parent_pid,
        "runtime_created": win32process.GetProcessTimes(int(runtime))["CreationTime"].isoformat(),
        "manager_created": win32process.GetProcessTimes(int(parent))["CreationTime"].isoformat(),
        "authentication_id": token.authentication_id,
        "session_id": token.session_id,
    }


def _scope_campaign(
    instance: InstalledLifecycleHarness,
    candidate: InstalledLifecycleHarness,
    profile: Profile,
    state: dict[str, Any],
    candidate_binding: dict[str, str],
    *,
    verify_only: bool,
) -> bool:
    """Observe authentic settled conflict and original protected work under its genuine caller context."""
    _scope_products(instance, absent=False)
    _scope_products(candidate, absent=True)
    before = _scope_observation(instance, profile)
    if verify_only:
        attempted = state.get("scope_attempt")
        if (
            not isinstance(attempted, dict)
            or attempted.get("binding") != candidate_binding
            or attempted.get("owner") != before
        ):
            raise ValueError("Scope verification lacks the same real settled attempt and unchanged native owner")
        validate_scope_refusal(attempted["receipt"], attempted["returncode"])
    else:
        result = run_command(
            [str(candidate.runner), "install", "--plan", str(candidate.plan)],
            cwd=candidate.plan.parent,
            environment=candidate.native_environment(),
            timeout_seconds=900,
        )
        receipt = json.loads(result.stdout)
        validate_scope_refusal(receipt, result.returncode)
        state["scope_attempt"] = {
            "binding": candidate_binding,
            "owner": before,
            "receipt": receipt,
            "returncode": result.returncode,
        }
    _scope_products(candidate, absent=True)
    _scope_products(instance, absent=False)
    if _scope_observation(instance, profile) != before:
        raise ValueError("Opposite-scope refusal changed the exact original manager/runtime incarnation")
    if not verify_only and instance.intent["scope"] == "user":
        return False  # Highest attempted the machine mutation; the genuine standard user must verify protected work.
    instance.start_manager(activate=False)
    live = instance.connect(profile.profile_id)
    live.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
    installed_protected_read(instance, profile, live)
    return True


def validate_scope_refusal(receipt: dict[str, Any], returncode: int) -> None:
    """Require actual settled native preparation denial, never success or cleanup uncertainty."""
    if (
        type(returncode) is not int
        or returncode == 0
        or receipt.get("schema") != 1
        or receipt.get("outcome") != "native_rolled_back"
        or receipt.get("code") != "native_preparation_refused"
        or receipt.get("service_restore")
        or receipt.get("cause")
    ):
        raise ValueError("Opposite-scope native transaction did not produce the actual settled admission refusal")


def validate_campaign_state(state: dict[str, Any], expected: dict[str, str], *, cleanup: bool = False) -> None:
    """Refuse foreign, incomplete or previously cleaned held ownership before mutation."""
    if (
        state.get("schema") != 1
        or state.get("binding") != expected
        or not isinstance(state.get("encrypted_profile"), str)
        or not isinstance(state.get("held_boot"), str)
        or type(state.get("held_authentication_id")) is not int
        or not isinstance(state.get("phases"), dict)
        or (state["phases"].get("hold") != "passed" and not (cleanup and state.get("ownership_committed") is True))
        or state["phases"].get("cleanup") == "passed"
    ):
        raise ValueError("Campaign state does not own this selected guest/account/scope/artifact installation")


def _publish_campaign(path: Path, state: dict[str, Any]) -> None:
    """Atomically publish test state, with no plaintext profile coordinates or secrets."""
    temporary = path.with_name(path.name + "." + str(uuid4()) + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _boot_stamp() -> str:
    import win32com.client

    systems = tuple(
        win32com.client.GetObject("winmgmts:").ExecQuery("SELECT LastBootUpTime FROM Win32_OperatingSystem")
    )
    if len(systems) != 1 or not isinstance(systems[0].LastBootUpTime, str) or not systems[0].LastBootUpTime:
        raise ValueError("Campaign requires the actual native boot identity")
    return systems[0].LastBootUpTime


def _campaign_profile(
    state: dict[str, Any], *, profile: Profile | None = None, continuation: dict[str, str] | None = None
) -> Profile | None:
    """Protect synthetic coordinates once with genuine current-account Windows DPAPI."""
    import win32crypt

    entropy = hashlib.sha256(json.dumps(state["binding"], sort_keys=True).encode("utf-8")).digest()
    if profile is not None:
        body = json.dumps(
            {"profile_id": str(profile.profile_id), "password": profile.password, "continuation": continuation}
        ).encode("utf-8")
        encrypted = win32crypt.CryptProtectData(body, "Cadrumo installed test", entropy, None, None, 1)
        state["encrypted_profile"] = base64.b64encode(encrypted).decode("ascii")
        return None
    body = _campaign_payload(state)
    if not isinstance(body.get("password"), str) or not body["password"]:
        raise ValueError("Campaign synthetic profile custody is invalid")
    return Profile(UUID(body["profile_id"]), body["password"])


def _campaign_payload(state: dict[str, Any]) -> dict[str, Any]:
    """Open the original DPAPI binding, including private upgrade continuation coordinates."""
    import win32crypt

    entropy = hashlib.sha256(json.dumps(state["binding"], sort_keys=True).encode("utf-8")).digest()
    _, decrypted = win32crypt.CryptUnprotectData(
        base64.b64decode(state["encrypted_profile"], validate=True), entropy, None, None, 1
    )
    return json.loads(decrypted)


def validate_successor_plan(original: dict[str, Any], successor: dict[str, Any]) -> None:
    """Require a genuinely newer canonical cohort within the same installation namespace."""
    if (
        original["scope"] != successor["scope"]
        or Path(original["prefix"]).resolve() != Path(successor["prefix"]).resolve()
        or original["contract"] != successor["contract"]
        or tuple(map(int, successor["version"].split("."))) <= tuple(map(int, original["version"].split(".")))
        or original["manifest_sha256"] == successor["manifest_sha256"]
        or original["version_product"]["product_code"] == successor["version_product"]["product_code"]
        or original["registration_product"]["product_code"] == successor["registration_product"]["product_code"]
    ):
        raise ValueError("Upgrade requires two real newer compatible same-scope canonical cohorts")


def _designated_successor(
    original: InstalledLifecycleHarness, successor: InstalledLifecycleHarness
) -> tuple[WindowsOwnedProcess, int]:
    """Retain only the genuine designated direct child of the still-live original manager."""
    import win32api
    import win32com.client
    import win32con
    import win32process

    from cadrumo.adapters.local_runtime.windows_native_io import (
        current_windows_owner_sid,
        owned_windows_handle,
        windows_image_path,
    )
    from cadrumo.adapters.local_runtime.windows_process import WindowsOwnedProcess

    from .installed import require_interactive_token

    parent = original.process
    owner = current_windows_owner_sid()
    token = require_interactive_token(int(original.manager_handle), owner)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        # The retained parent handle prevents PID reuse; death is never a successful rollback attempt.
        try:
            parent.wait(timeout=0)
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                raise
        else:
            raise ValueError("Original manager committed or exited before the designated fault")
        rows = win32com.client.GetObject("winmgmts:").ExecQuery(
            "SELECT ProcessId,ParentProcessId,CommandLine FROM Win32_Process"
        )
        for row in rows:
            if row.ParentProcessId != parent.pid:
                continue
            handle = owned_windows_handle(
                win32api.OpenProcess(
                    win32con.PROCESS_TERMINATE | win32con.PROCESS_QUERY_LIMITED_INFORMATION | win32con.SYNCHRONIZE,
                    False,
                    row.ProcessId,
                )
            )
            try:
                parts = (row.CommandLine or "").rsplit(" ", 2)
                designation = parts[-1].split(":")
                if windows_image_path(handle) != successor.manager.resolve():
                    continue
                if (
                    len(parts) != 3
                    or parts[-2] != "--cutover"
                    or len(designation) != 3
                    or designation[0] != str(parent.pid)
                    or designation[1] != original.intent["version"]
                    or len(designation[2]) != 32
                    or any(c not in "0123456789abcdef" for c in designation[2])
                    or require_interactive_token(int(handle), owner) != token
                    or win32process.GetProcessTimes(int(handle))["CreationTime"]
                    < win32process.GetProcessTimes(int(original.manager_handle))["CreationTime"]
                ):
                    raise ValueError("Successor is not the native designated same-logon direct child")
                original.resources.callback(handle.Close)
                held_handle = int(handle)
                held = WindowsOwnedProcess(handle=held_handle, pid=row.ProcessId)
                handle = None
                return held, int(held_handle)
            finally:
                if handle is not None:
                    handle.Close()
        time.sleep(0.02)
    raise TimeoutError("No genuine designated successor appeared")


def _upgrade_campaign(
    original: InstalledLifecycleHarness,
    successor: InstalledLifecycleHarness,
    profile: Profile,
    state: dict[str, Any],
    state_path: Path,
    *,
    machine: bool,
) -> None:
    """Exercise the real native upgrade, user rollback/retry, and immutable P2 interpreter continuation."""
    from threading import Event

    import win32process

    from cadrumo.adapters.persistence.storage.custody.filesystem import read_optional_profile_custody_local_record

    original.start_manager(activate=False)
    old = original.connect(profile.profile_id, lifecycle_notices="v1")
    old.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
    operation = _execute_read(old)
    before = _observe_read(old, operation).projection
    _campaign_profile(
        state,
        profile=profile,
        continuation={
            "session": str(old.client.session_id),
            "boot": str(old.wire.hello.boot_id),
            "operation": str(operation),
            "revision": str(before.revision),
        },
    )
    _publish_campaign(state_path, state)
    pending = Event()
    unsubscribe = old.client.subscribe_lifecycle_notices(
        lambda event: pending.set() if event.runtime_boot_id == old.wire.hello.boot_id else None
    )
    try:
        successor.maintenance("install")
        successor.verify_registration()
        state["successor_registered"] = True
        _publish_campaign(state_path, state)
        if machine:
            if original.process.wait(timeout=90) != 0:
                raise ValueError("Machine broker upgrade did not gracefully settle its original worker")
        else:
            child, child_handle = _designated_successor(original, successor)
            win32process.TerminateProcess(child_handle, 73)
            if child.wait(timeout=10) != 73 or not pending.is_set():
                raise ValueError("Designated successor failure or genuine upgrade notice was not confirmed")
            marker = original.root / ".runtime/manager-failed-versions.json"
            deadline = time.monotonic() + 90
            while True:
                record = read_optional_profile_custody_local_record(marker, maximum_bytes=4096)
                if record is not None and json.loads(record) == {
                    "schema": 1,
                    "versions": [{"version": successor.intent["version"], "previous": original.intent["version"]}],
                }:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError("Genuine rollback marker was not published")
                time.sleep(0.05)
            restored = original.connect(profile.profile_id, after_boot=old.wire.hello.boot_id)
            restored.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
            projection = _observe_read(restored, operation).projection
            if (
                projection.revision != before.revision
                or projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            ):
                raise ValueError("Rollback lost the same durable settled protected operation")
            installed_protected_read(original, profile, restored)
            result = run_command(
                [str(original.prefix / "cadrumo-manager.exe"), "--retry"],
                cwd=original.prefix,
                environment=original.native_environment(),
                timeout_seconds=90,
            )
            if result.returncode:
                raise ValueError("The genuine manager Retry command failed")
            _designated_successor(original, successor)
            if original.process.wait(timeout=300) != 0:
                raise ValueError("Successful cutover did not retire the original manager")
        state["upgrade_commit_observed"] = True
        _publish_campaign(state_path, state)
    finally:
        unsubscribe()
    source = Path(__file__).resolve().parents[2]
    result = run_command(
        [
            str(successor.package / "python.exe"),
            "-I",
            "-c",
            "import sys;sys.path.insert(0,sys.argv.pop(1));from dev.runtime_lifecycle.installed import main;main()",
            str(source),
            "--phase",
            "upgrade-verify",
            "--campaign-state",
            str(state_path),
            "--plan",
            str(original.plan),
            "--runner",
            str(original.runner),
            "--successor-plan",
            str(successor.plan),
            "--successor-runner",
            str(successor.runner),
            "--installed-vm-id",
            state["binding"]["vm_id"],
            "--installed-account-sid",
            state["binding"]["account_sid"],
            "--installed-guest-kind",
            state["binding"]["guest_kind"],
        ],
        cwd=source,
        environment=original.native_environment(),
        timeout_seconds=600,
    )
    if result.returncode or json.loads(result.stdout).get("result") != "passed":
        raise ValueError("P2 bundled interpreter did not confirm authenticated upgrade continuation")
    state.update(json.loads(state_path.read_text(encoding="utf-8")))


def validate_gui_phase(
    state: dict[str, Any], scope: str, phase: str, boot: str, authentication_id: int, linked_id: int, session_id: int
) -> None:
    """Fence the ordinary-user proof to this original held machine/logon owner."""
    phases = state["phases"]
    if (
        scope != "machine"
        or phases.get("login") != "passed"
        or phases.get("scope_conflict_refusal") != "passed"
        or state.get("successor") is not None
        or phase not in {"gui-stop", "gui-user", "gui-restore"}
        or (phase == "gui-stop" and any(name in phases for name in ("gui-stop", "gui-user", "gui-restore")))
        or (
            phase != "gui-stop"
            and (
                state.get("gui_boot") != boot
                or state.get("gui_session_id") != session_id
                or state.get("gui_user_authentication_id" if phase == "gui-user" else "gui_authentication_id")
                != authentication_id
                or state.get("gui_authentication_id" if phase == "gui-user" else "gui_user_authentication_id")
                != linked_id
            )
        )
        or (phase == "gui-user" and (phases.get("gui-stop") != "passed" or "gui-user" in phases))
        or (phase == "gui-restore" and (phases.get("gui-user") != "passed" or "gui-restore" in phases))
    ):
        raise ValueError("Ordinary GUI proof requires ordered original machine ownership on the same genuine logon")


def _gui_campaign(instance: InstalledLifecycleHarness, profile: Profile, state: dict[str, Any], phase: str) -> None:
    """Privileged controls surround the existing genuine least-privilege GUI proof."""
    if phase == "gui-stop":
        instance.verify_registration()
        instance.start_manager(activate=False)
        live = instance.connect(profile.profile_id)
        live.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
        operation = _execute_read(live)
        projected = _observe_read(live, operation).projection
        _scope_observation(instance, profile)
        _campaign_profile(
            state,
            profile=profile,
            continuation={
                "boot": str(live.wire.hello.boot_id),
                "operation": operation,
                "revision": str(projected.revision),
            },
        )
        runtime = instance.retain_cleanup_runtime()
        if runtime is None:
            raise AssertionError("Machine stop lacks the retained verified runtime")
        instance.control_service(start=False)
        runtime.wait(timeout=35)
        instance.verify_stopped_service()
    elif phase == "gui-user":
        instance.verify_stopped_service()
        if instance.retain_cleanup_runtime() is not None:
            raise AssertionError("Stopped machine broker left a runtime before ordinary GUI launch")
        previous = UUID(_campaign_payload(state)["continuation"]["boot"])
        state["gui_runtime_boot"] = str(exercise_cadrumo_takeover(instance, profile, after_boot=previous))
        instance.verify_stopped_service()
    else:
        instance.verify_stopped_service()
        instance.control_service(start=True)
        instance.verify_registration()
        instance.start_manager(activate=False)
        _scope_observation(instance, profile)
        live = instance.connect(profile.profile_id, after_boot=UUID(state["gui_runtime_boot"]))
        live.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
        payload = _campaign_payload(state)["continuation"]
        projected = _observe_read(live, payload["operation"]).projection
        if (
            projected.revision != int(payload["revision"])
            or projected.terminal_condition is not OperationTerminalCondition.SUCCEEDED
        ):
            raise AssertionError("Restored installed manager lost the original protected operation")
        installed_protected_read(instance, profile, live)


def installed_campaign(
    phase: str,
    state_path: Path,
    plan: Path,
    runner: Path,
    vm_id: UUID,
    account_sid: str,
    *,
    guest_kind: Literal["hyperv", "qemu"] = "hyperv",
    conflicting_plan: Path | None = None,
    successor_plan: Path | None = None,
    successor_runner: Path | None = None,
) -> dict[str, Any]:
    """Run held installation, read-only prelogin boot, genuine login or owner cleanup."""
    import win32api

    from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
    from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
    from cadrumo.core.storage_environment import STORAGE_ROOT

    from .installed import (
        InstalledLifecycleHarness,
        require_installation_guest,
        require_interactive_token,
        require_linked_interactive_token,
    )

    if phase not in {
        "hold",
        "boot",
        "login",
        "scope-conflict",
        "scope-verify",
        "gui-stop",
        "gui-user",
        "gui-restore",
        "upgrade-rollback",
        "machine-upgrade",
        "upgrade-verify",
        "cleanup",
    }:
        raise ValueError("Unknown installed campaign phase")
    plan, runner = plan.resolve(strict=True), runner.resolve(strict=True)
    state_path.parent.resolve(strict=True)
    if state_path.is_dir():
        raise ValueError("Campaign state must be a dedicated test file")
    binding = campaign_binding(plan, runner, vm_id, account_sid, guest_kind)
    scope_phase = phase in {"scope-conflict", "scope-verify"}
    if scope_phase and conflicting_plan is None:
        raise ValueError("Scope campaign requires the actual opposite-scope --conflicting-plan")
    if phase == "hold":
        if state_path.exists():
            raise ValueError("Hold refuses an existing campaign state")
        state: dict[str, Any] = {"schema": 1, "binding": binding, "phases": {}}
    else:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        validate_campaign_state(state, binding, cleanup=phase == "cleanup")
    root = require_installation_guest(
        vm_id,
        account_sid,
        "machine" if phase == "scope-conflict" else cast(Literal["user", "machine"], binding["scope"]),
        guest_kind=guest_kind,
        fresh=phase == "hold",
        interactive=phase != "boot",
        caller_elevation=False if phase == "gui-user" else None,
    )
    instance = InstalledLifecycleHarness(plan, runner, root)
    if phase in {"gui-stop", "gui-user", "gui-restore"}:
        actual = require_interactive_token(int(win32api.GetCurrentProcess()), account_sid)
        linked = require_linked_interactive_token(int(win32api.GetCurrentProcess()), account_sid)
        boot = _boot_stamp()
        validate_gui_phase(
            state, binding["scope"], phase, boot, actual.authentication_id, linked.authentication_id, actual.session_id
        )
        if phase == "gui-stop":
            state["gui_boot"], state["gui_authentication_id"] = boot, actual.authentication_id
            state["gui_user_authentication_id"], state["gui_session_id"] = linked.authentication_id, actual.session_id
    successor = None
    upgrade_phase = phase in {"upgrade-rollback", "machine-upgrade", "upgrade-verify"}
    if upgrade_phase or (phase == "cleanup" and state.get("successor")):
        if successor_plan is None or successor_runner is None:
            raise ValueError("Upgraded ownership requires the real --successor-plan and --successor-runner")
        successor_plan, successor_runner = successor_plan.resolve(strict=True), successor_runner.resolve(strict=True)
        successor = InstalledLifecycleHarness(successor_plan, successor_runner, root)
        validate_successor_plan(instance.intent, successor.intent)
        successor_binding = campaign_binding(successor_plan, successor_runner, vm_id, account_sid, guest_kind)
        if state.get("successor") not in (None, successor_binding):
            raise ValueError("Successor artifacts differ from the campaign's immutable attempted owner")
        if phase == "upgrade-rollback" and binding["scope"] != "user":
            raise ValueError("Live cutover rollback requires the user installation; machine upgrades stop the broker")
        if phase == "machine-upgrade" and binding["scope"] != "machine":
            raise ValueError("Machine service upgrade requires the machine installation")
        if phase == "machine-upgrade" and state["phases"].get("gui-restore") != "passed":
            raise ValueError("Machine upgrade requires the completed ordinary-user GUI proof")
        if phase == "upgrade-verify" and not state.get("upgrade_commit_observed"):
            raise ValueError("P2 continuation requires the actual preceding native upgrade commitment")
        state["successor"] = successor_binding
    state_path = state_path.resolve()
    if state_path.is_relative_to(root.resolve()) or state_path.is_relative_to(instance.prefix.resolve()):
        raise ValueError("Campaign state must be outside installation and taxpayer storage")
    instance.retain_profile_receipts = True
    os.environ[STORAGE_ROOT.variable] = str(root)
    os.environ[STORAGE_ROOT.development_variable] = str(root)
    os.environ["CADRUMO_AUTHORITY_ROOT"] = str(instance.package / "data/authority")
    profile: Profile | None = None
    primary_failure: BaseException | None = None
    try:
        if phase == "hold":
            with instance:
                profile = instance.create_profile("Installed acceptance")
                exercise_installed_manager(instance, leave_running=True, profile=profile)
                state["held_boot"] = _boot_stamp()
                state["held_authentication_id"] = require_interactive_token(
                    int(win32api.GetCurrentProcess()), account_sid
                ).authentication_id
                _campaign_profile(state, profile=profile)
                state["ownership_committed"] = True
                state["phases"]["hold"] = "passed"
                _publish_campaign(state_path, state)
                instance._held = True
        elif phase == "boot":
            if binding["scope"] != "machine" or _boot_stamp() == state["held_boot"]:
                raise ValueError("Boot phase requires a real machine reboot after the held installation")
            verify_prelogin_boot(instance, account_sid)
            state["boot_observed"] = _boot_stamp()
            state["phases"]["boot"] = "passed"
            _publish_campaign(state_path, state)
        else:
            profile = _campaign_profile(state)
            if profile is None:
                raise ValueError("Campaign has no owned synthetic profile")
            instance._preflight_admitted = True
            instance._installation_attempted = True
            if phase in {"gui-stop", "gui-user", "gui-restore"}:
                instance.endpoint = WindowsRuntimeEndpoint(storage_root=root)
                instance.resources.callback(instance.endpoint.close)
                _gui_campaign(instance, profile, state, phase)
                state["phases"][phase] = "passed"
            elif upgrade_phase:
                if successor is None:
                    raise ValueError("Missing immutable successor owner")
                instance.endpoint = WindowsRuntimeEndpoint(storage_root=root)
                instance.resources.callback(instance.endpoint.close)
                if phase != "upgrade-verify":
                    _upgrade_campaign(
                        instance, successor, profile, state, state_path, machine=phase == "machine-upgrade"
                    )
                else:
                    successor.verify_registration()
                    successor.endpoint = WindowsRuntimeEndpoint(storage_root=root)
                    successor.resources.callback(successor.endpoint.close)
                    os.environ["CADRUMO_AUTHORITY_ROOT"] = str(successor.package / "data/authority")
                    successor.start_manager(activate=False)
                    _scope_observation(successor, profile)
                    payload = _campaign_payload(state)["continuation"]
                    live = successor.connect(profile.profile_id, after_boot=UUID(payload["boot"]))
                    _refused(_private_request(live, UUID(payload["session"])))
                    live.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
                    projected = _observe_read(live, payload["operation"]).projection
                    if (
                        projected.revision != int(payload["revision"])
                        or projected.terminal_condition is not OperationTerminalCondition.SUCCEEDED
                    ):
                        raise ValueError("P2 lost the original settled protected operation")
                    installed_protected_read(successor, profile, live)
                    state["phases"][
                        "machine_service_upgrade" if binding["scope"] == "machine" else "upgrade_cutover_rollback"
                    ] = "passed"
                _publish_campaign(state_path, state)
            elif scope_phase:
                candidate_plan = cast(Path, conflicting_plan).resolve(strict=True)
                candidate = InstalledLifecycleHarness(candidate_plan, runner, root)
                validate_conflicting_plan(instance.intent, candidate.intent)
                instance.endpoint = WindowsRuntimeEndpoint(storage_root=root)
                instance.resources.callback(instance.endpoint.close)
                candidate_binding = campaign_binding(candidate_plan, runner, vm_id, account_sid, guest_kind)
                complete = _scope_campaign(
                    instance, candidate, profile, state, candidate_binding, verify_only=phase == "scope-verify"
                )
                state["phases"]["scope_conflict_refusal"] = "passed" if complete else "attempted"
            elif phase == "login":
                actual = require_interactive_token(int(win32api.GetCurrentProcess()), account_sid)
                boot = _boot_stamp()
                if boot == state["held_boot"] and actual.authentication_id == state["held_authentication_id"]:
                    raise ValueError("Login phase requires a new genuine login or boot")
                if binding["scope"] == "machine" and (
                    state["phases"].get("boot") != "passed" or state.get("boot_observed") != boot
                ):
                    raise ValueError("Machine login requires the actual prelogin broker proof for this boot")
                instance.verify_registration()
                instance.endpoint = WindowsRuntimeEndpoint(storage_root=root)
                instance.resources.callback(instance.endpoint.close)
                instance.start_manager(activate=False)
                live = instance.connect(profile.profile_id)
                live.client.login_password(bytearray(profile.password, "utf-8"), persist_receipt=True)
                installed_protected_read(instance, profile, live)
                state["phases"]["login"] = "passed"
            else:
                cleanup_owner = instance
                if successor is not None:
                    import win32com.client

                    product = successor.intent["registration_product"]["product_code"]
                    if win32com.client.Dispatch("WindowsInstaller.Installer").ProductState(product) == 5:
                        cleanup_owner = successor
                    cleanup_owner._preflight_admitted = True
                cleanup_owner.cleanup_after_outer_exit()
                if binding["scope"] == "user":
                    if cleanup_owner.metrics.get("cleanup_popup_observed") != 1.0:
                        raise AssertionError("User cleanup did not exercise the retained manager's native menu")
                    state["cleanup_popup_observed"] = True
                instance.cli("profile", "view", profile_secret=profile.password, expect_success=False)
                _tui(instance, profile, admitted=False)
                asyncio.run(installed_mcp_read(instance, profile, admitted=False))
                delete_profile_session(storage_root=root, profile_id=profile.profile_id)
                state["phases"]["cleanup"] = "passed"
                del state["encrypted_profile"]
            _publish_campaign(state_path, state)
    except BaseException as error:
        primary_failure = error
        if phase == "hold" and profile is not None and not instance._held:
            try:
                delete_profile_session(storage_root=root, profile_id=profile.profile_id)
            except BaseException as cleanup:
                error.add_note(f"Campaign credential cleanup failed: {type(cleanup).__name__}")
        state["phases"][phase] = "failed"
        try:
            _publish_campaign(state_path, state)
        except BaseException as publication:
            error.add_note(f"Campaign failure publication failed: {type(publication).__name__}")
        raise
    finally:
        for owner in (instance, successor):
            if owner is None:
                continue
            try:
                owner.resources.close()
            except BaseException as cleanup:
                if primary_failure is None:
                    primary_failure = cleanup
                else:
                    primary_failure.add_note(f"Campaign resource cleanup failed: {type(cleanup).__name__}")
        if primary_failure is not None and primary_failure is not sys.exception():
            raise primary_failure
    pending = [
        *(
            ["ordinary_user_gui"]
            if binding["scope"] == "machine" and state["phases"].get("gui-restore") != "passed"
            else []
        ),
        *(["machine_boot"] if binding["scope"] == "machine" and state["phases"].get("boot") != "passed" else []),
        *(["user_login"] if state["phases"].get("login") != "passed" else []),
        *(["scope_conflict_refusal"] if state["phases"].get("scope_conflict_refusal") != "passed" else []),
        *(
            ["machine_service_upgrade" if binding["scope"] == "machine" else "upgrade_cutover_rollback"]
            if state["phases"].get(
                "machine_service_upgrade" if binding["scope"] == "machine" else "upgrade_cutover_rollback"
            )
            != "passed"
            else []
        ),
        *(["cleanup"] if state["phases"].get("cleanup") != "passed" else []),
    ]
    return {
        "schema": 1,
        "phase": phase,
        "result": "attempted" if phase == "scope-conflict" and binding["scope"] == "user" else "passed",
        "scope": binding["scope"],
        "full_installation_acceptance": "passed" if phase == "cleanup" and not pending else "incomplete",
        "cleanup_popup_observed": state.get("cleanup_popup_observed", False),
        "pending": pending,
    }
