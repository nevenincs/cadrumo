"""A key the person issues for an agent releases its data categories to the MCP client presenting it.

The person runs ``config profile automation create --use agent`` and approves
the request with the profile password from a separate signed-in connection.
The agent's MCP server then presents the delivered key by reference only,
reads a profile value back, patches the profile, mutates a field and adds,
updates and removes a row, reading each change back, is refused a value
outside the key's categories, and is refused everything once the person
revokes the key. Ten such keys fit the person's inventory, each counted and
paged there, and each revocable.

The command line, the runtime, the native transport, the session authority,
the profile worker, the profile's custody and the MCP server are real. The
native credential store on both sides, the native login the runtime observes
and the MCP SDK's transport (memory) are ports held by the test, so this runs
on a logon session whose credential store refuses; the installed processes and
the real store are exercised by ``test_runtime_automation_agent_key_native``.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import Callable, Generator
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import copy_context
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import cast
from uuid import UUID, uuid4

import pytest
from click.testing import Result

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.local_runtime.automation_decision import AutomationDecisionRunError, run_automation_decision
from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.automation_requester import AutomationRequesterJourney
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import PROFILE_INPUT, owner_id, worker_profiles
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_profile import current_automation_profile_binding
from cadrumo.adapters.persistence.storage.custody.automation_store import AutomationControlStore
from cadrumo.adapters.persistence.storage.custody.kdf_supervision import (
    PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS,
    profile_kdf_lease,
)
from cadrumo.adapters.persistence.storage.custody.tests.automation_support import MemoryNativePort
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeClientHello
from cadrumo.application.user_profile.access_contracts import (
    AuthorityState,
    Availability,
    DisclosureCategory,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_agent_key import agent_key_proposal, agent_key_scope
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind
from cadrumo.application.user_profile.history_operation import PROFILE_HISTORY_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.profile_operation_contracts import ProfilePatchOperationRequest, ProfilePatchValue
from cadrumo.application.user_profile.view_operation import ProfileViewFactItem, ProfileViewPageKind
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.cli.config import runtime_automation_request
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.agent_key_reads import edit_profile_and_read_back, settled_result, tool_document
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

from .....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer
from .._runtime_profile_mutation import execute_profile_mutation, read_mutation_baseline

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_KEYS = 10
"""More agent keys than an inventory of listed scopes could hold."""

_CONNECT_SECONDS = 30
"""The test's own allowance for a new connection's handshake on a loaded host."""

_FENCE_HELD_SECONDS = 13
"""Longer than the ten seconds a requester's single exchange was once allowed, plus its five-second long poll."""


class _LoginObservation:
    login_id = "cli-automation-agent-key-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


@dataclass(frozen=True)
class _Runtime:
    root: Path
    endpoint: WindowsRuntimeEndpoint
    profile_id: UUID
    store: AutomationControlStore
    pool: ThreadPoolExecutor
    profiles: RuntimeProfileConnections


@dataclass(frozen=True)
class _IssuedKey:
    reference: UUID
    key_id: UUID
    grant_id: UUID


def _human(endpoint: WindowsRuntimeEndpoint, profile_id: UUID) -> RuntimeFrontendClient:
    """The person's own signed-in connection, separate from the requesting command."""
    raw = VerifiedRuntimeConnection(
        endpoint.connect(timeout=_CONNECT_SECONDS),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + _CONNECT_SECONDS,
    )
    human = RuntimeFrontendClient(raw, profile_id=profile_id, frontend=OperationFrontendProjection.CLI)
    human.login_password(bytearray(PROFILE_INPUT.encode()), timeout=90)
    return human


@contextmanager
def _running_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[_Runtime]:
    """Serve one synthetic profile from a real runtime, both native stores held by the test."""
    with worker_profiles(tmp_path) as (root, targets):
        profile_id = targets[-1][0].binding.profile_id
        delete_profile_session(storage_root=root, profile_id=profile_id)
        endpoint = WindowsRuntimeEndpoint(storage_root=root)
        installation = runtime_installation(
            storage_root=root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
        )
        binding = current_automation_profile_binding(
            profile_id=profile_id,
            installation_id=installation.installation_id,
            os_owner_id=installation.os_owner_id,
            root=root,
        )
        server_native, client_native = MemoryNativePort(), MemoryNativePort()
        monkeypatch.setattr(runtime_automation_request, "installed_automation_secret_store", lambda: client_native)
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: client_native)
        store = AutomationControlStore(root=root, binding=binding, secrets_store=server_native)
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: server_native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                yield _Runtime(root, endpoint, profile_id, store, pool, profiles)
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    running.result(timeout=20)
                except Exception:
                    if primary is None:
                        raise
                finally:
                    endpoint.close()


def _issue_agent_key(runtime: _Runtime, *, check_review: bool = False, hold_fence: float = 0) -> _IssuedKey:
    """Run the real create command for an agent key and approve it from a separate signed-in connection.

    ``hold_fence`` holds the profile's publication fence that long once the
    request is pending, as a slow commit on a loaded host does.
    """

    def invoke_create() -> Result:
        with override_settings(
            cadrumo_local_storage_root=runtime.root,
            cadrumo_output_language="en",
            cadrumo_cli_reveal_identifiers=True,
        ):
            return invoke_cached_cli(
                (
                    "--format",
                    "json",
                    "--profile",
                    str(runtime.profile_id),
                    "config",
                    "profile",
                    "automation",
                    "create",
                    "--use",
                    "agent",
                )
            )

    def pending() -> int:
        return sum(item.stage is EnrollmentStage.REQUESTED for item in runtime.store.enrollment_state().requests)

    creating = runtime.pool.submit(copy_context().run, invoke_create)
    deadline = time.monotonic() + 60
    while not pending() and time.monotonic() < deadline:
        if creating.done():
            pytest.fail(f"requester exited before a review existed: {creating.result()!r}")
        time.sleep(0.05)
    if hold_fence:
        # The requester's next inspect or poll waits here for its reply.
        with runtime.profiles._profiles[runtime.profile_id].guard:
            time.sleep(hold_fence)
        assert not creating.done(), cast(Result, creating.result()).output
    human = _human(runtime.endpoint, runtime.profile_id)
    try:
        (review,) = (
            item
            for item in read_automation_inventory(human).projection.requests
            if item.receipt.stage is EnrollmentStage.REQUESTED
        )
        if check_review:
            # The person reviews exactly what the agent's key will release, and to whom.
            scope = review.proposal.scope
            assert scope.operations == () and scope.all_agent_operations
            assert scope.disclosure_count == 0
            assert {item.category for item in scope.disclosure_categories} == {
                DisclosureCategory.PROFILE_VALUES,
                DisclosureCategory.OPERATION_METADATA,
            }
            assert {item.destination_id for item in scope.disclosure_categories} == {review.destination_id}
            assert review.destination_id == review.client_id
            assert review.proposal.unattended and not review.proposal.allow_os_lock
        approved = run_automation_decision(
            human, review, decision="approve", password=bytearray(PROFILE_INPUT.encode())
        )
        assert approved.receipt.stage is EnrollmentStage.COMPLETE
    finally:
        human.close()
    created = cast(Result, creating.result(timeout=60))
    assert created.exit_code == 0, created.output
    result = json.loads(created.stdout)["result"]
    assert result["terminal"]["stage"] == "complete"
    return _IssuedKey(
        reference=UUID(result["credential_reference"]),
        key_id=UUID(result["terminal"]["key_id"]),
        grant_id=UUID(result["terminal"]["grant_id"]),
    )


async def _agent_reads(profile_id: UUID, reference: UUID, revoke: Callable[[], object]) -> None:
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        await adapter.bootstrap_reference(reference)
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            status = tool_document(await sdk.call_tool("status", {}))
            assert status["session"] == "key", status

            inside = tool_document(
                await settled_result(
                    sdk,
                    profile_id,
                    AUTH_READ_OPERATION_DEFINITION_ID,
                    {"profile_id": str(profile_id), "kind": "status"},
                )
            )
            assert inside["document"]["projection"]["profile_id"] == str(profile_id)
            await edit_profile_and_read_back(sdk, profile_id)

            # The profile history discloses profile and tax values together; tax values were not chosen.
            outside = await settled_result(
                sdk, profile_id, PROFILE_HISTORY_OPERATION_DEFINITION_ID, {"profile_id": str(profile_id)}
            )
            assert outside.is_error is True
            assert isinstance(outside.structured_content, dict)
            assert outside.structured_content["outcome"] == "refused", outside.structured_content

            await asyncio.to_thread(revoke)
            revoked = await sdk.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
            assert revoked.is_error is True
            assert isinstance(revoked.structured_content, dict)
            assert revoked.structured_content["outcome"] == "refused", revoked.structured_content
    finally:
        await adapter.close()


async def _refused_reference(profile_id: UUID, reference: UUID) -> None:
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        await adapter.bootstrap_reference(reference)
        async with connected_server_and_client_session(build_server(adapter)) as sdk:
            refused = await sdk.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
            assert refused.is_error is True, refused.structured_content
    finally:
        await adapter.close()


def test_a_key_issued_for_an_agent_on_the_command_line_reads_its_category_back_over_mcp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with _running_runtime(tmp_path, monkeypatch) as runtime:
        issued = _issue_agent_key(runtime, check_review=True)

        def revoke() -> None:
            person = _human(runtime.endpoint, runtime.profile_id)
            try:
                person.deny_automation(AutomationDenialKind.KEY, target_id=issued.key_id)
            finally:
                person.close()

        with override_settings(cadrumo_local_storage_root=runtime.root):
            asyncio.run(_agent_reads(runtime.profile_id, issued.reference, revoke))


def test_the_person_lists_inspects_and_revokes_ten_agent_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ten agent keys fit the inventory, each counted and paged there, and each revocable."""
    with _running_runtime(tmp_path, monkeypatch) as runtime:
        issued = [_issue_agent_key(runtime) for _ in range(_KEYS)]
        person = _human(runtime.endpoint, runtime.profile_id)
        try:
            inventory = read_automation_inventory(person).projection
            grants = {item.grant_id: item for item in inventory.grants}
            assert {item.grant_id for item in issued} <= grants.keys()
            assert {item.key_id for item in issued} <= {key.key_id for key in inventory.keys}
            for key in issued:
                scope = grants[key.grant_id].scope
                assert scope.all_agent_operations and scope.operations == () and scope.disclosure_count == 0
                page = read_automation_inventory(person, disclosures_of=key.grant_id).projection.disclosure_page
                assert page is not None and page.total == 0 and page.next_offset is None
                assert page.disclosure_digest == scope.disclosure_digest
            for key in issued:
                assert person.deny_automation(AutomationDenialKind.KEY, target_id=key.key_id).access_denied
            states = {key.key_id: key.state for key in read_automation_inventory(person).projection.keys}
            assert all(states[key.key_id] is AuthorityState.REVOKED for key in issued), states
        finally:
            person.close()
        with override_settings(cadrumo_local_storage_root=runtime.root):
            asyncio.run(_refused_reference(runtime.profile_id, issued[-1].reference))


def test_a_slow_runtime_keeps_the_requester_waiting_through_the_persons_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reply held behind the profile's publication fence is late, not lost, and the approval completes."""
    with _running_runtime(tmp_path, monkeypatch) as runtime:
        issued = _issue_agent_key(runtime, hold_fence=_FENCE_HELD_SECONDS)
        person = _human(runtime.endpoint, runtime.profile_id)
        try:
            keys = {key.key_id: key.state for key in read_automation_inventory(person).projection.keys}
        finally:
            person.close()
        assert keys[issued.key_id] is AuthorityState.ACTIVE


def test_an_approval_after_the_requester_left_names_the_departed_requester(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The key cannot reach a requester that disconnected, and the person is told so by name."""
    with _running_runtime(tmp_path, monkeypatch) as runtime:
        requester = RuntimeFrontendClient(
            VerifiedRuntimeConnection(
                runtime.endpoint.connect(timeout=_CONNECT_SECONDS),
                expected=RuntimeClientHello(
                    product_version=version("cadrumo"), storage_identity=runtime.endpoint.storage_identity
                ),
                deadline=time.monotonic() + _CONNECT_SECONDS,
            ),
            profile_id=runtime.profile_id,
            frontend=OperationFrontendProjection.CLI,
        )
        try:
            enrollment = requester.prepare_enrollment(MemoryNativePort())
            proposal = agent_key_proposal(
                agent_key_scope(), destination_id=enrollment.prepared.destination_id, now=datetime.now(UTC)
            )
            submitted = AutomationRequesterJourney(enrollment, timeout=60).submit(proposal)
        finally:
            requester.close()
        person = _human(runtime.endpoint, runtime.profile_id)
        try:
            (review,) = (
                item
                for item in read_automation_inventory(person).projection.requests
                if item.receipt.request_id == submitted.request_id
            )
            with pytest.raises(AutomationDecisionRunError) as refused:
                run_automation_decision(person, review, decision="approve", password=bytearray(PROFILE_INPUT.encode()))
        finally:
            person.close()
        assert refused.value.reason == "REFUSED_AUTOMATION_REQUESTER_DISCONNECTED"
        (record,) = (
            item for item in runtime.store.enrollment_state().requests if item.request_id == submitted.request_id
        )
        assert record.stage is not EnrollmentStage.COMPLETE


_KDF_PERMIT_HELD_SECONDS = PROFILE_CUSTODY_KDF_OPERATION_DEADLINE_SECONDS + 10
"""Longer than one password derivation may take, permit wait included, so the sign-in cannot derive."""

_STATUS_FENCE_HELD_SECONDS = 8
"""Longer than the five seconds a session status read was once allowed."""


def test_a_persons_sign_in_is_refused_as_unavailable_while_another_derivation_holds_the_kdf_permit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The permit wait is inside the derivation's one bound; past it the sign-in is refused, typed, and may retry."""
    with _running_runtime(tmp_path, monkeypatch) as runtime:
        held, release = Event(), Event()

        def hold_permit() -> None:
            with (
                override_settings(cadrumo_local_storage_root=runtime.root),
                profile_kdf_lease(deadline=time.monotonic() + 30),
            ):
                held.set()
                release.wait(_KDF_PERMIT_HELD_SECONDS)

        holding = runtime.pool.submit(copy_context().run, hold_permit)
        try:
            assert held.wait(30)
            with pytest.raises(RuntimeFrontendRefusedError) as refused:
                _human(runtime.endpoint, runtime.profile_id).close()
        finally:
            release.set()
            holding.result(timeout=30)
        assert refused.value.reason == "unavailable"
        # The worker served on, so the same password signs in once the permit is free.
        person = _human(runtime.endpoint, runtime.profile_id)
        try:
            assert person.status().status.connected
        finally:
            person.close()


def _hold_fence(runtime: _Runtime, seconds: float) -> Future[None]:
    """Hold the profile's publication fence for ``seconds``, as a person's commit on a loaded host does."""
    held = Event()

    def hold() -> None:
        with runtime.profiles._profiles[runtime.profile_id].guard:
            held.set()
            time.sleep(seconds)

    holding = runtime.pool.submit(hold)
    assert held.wait(30)
    return holding


def test_a_status_read_waits_out_the_profile_fence_and_keeps_its_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read held behind the profile's fence, as a person's commit holds it, answers late on the same connection."""
    with _running_runtime(tmp_path, monkeypatch) as runtime:
        person = _human(runtime.endpoint, runtime.profile_id)
        try:
            holding = _hold_fence(runtime, _STATUS_FENCE_HELD_SECONDS)
            started = time.monotonic()
            status = person.status()
            waited = time.monotonic() - started
            holding.result(timeout=30)
            assert status.status.connected and status.status.session_id == person.session_id
            assert waited >= _STATUS_FENCE_HELD_SECONDS - 2
            assert person.sessions()
        finally:
            person.close()


_COMMAND_SECONDS_LEFT = 3
"""What a command has left when it submits its change, after a slow baseline read spent the rest."""

_CHANGE_FENCE_HELD_SECONDS = 8
"""How long the change then waits behind the fence: longer than its command had left."""


def test_a_change_submitted_late_in_its_command_keeps_a_full_operation_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A slow baseline read cannot starve the change into an unknown outcome.

    On a loaded host the read that precedes a profile change can spend most of
    the command's budget. The change waits behind the fence for longer than the
    command had left, commits, and the command reads the committed revision back.
    """
    with _running_runtime(tmp_path, monkeypatch) as runtime:
        person = _human(runtime.endpoint, runtime.profile_id)
        try:
            baseline = read_mutation_baseline(person, deadline=time.monotonic() + 120)
            holding = _hold_fence(runtime, _CHANGE_FENCE_HELD_SECONDS)
            completed, current = execute_profile_mutation(
                person,
                ProfilePatchOperationRequest(
                    profile_id=runtime.profile_id,
                    expected_revision=baseline.record_revision,
                    expected_content_digest=baseline.content_digest,
                    values=(ProfilePatchValue(question_id="name", value="Persona"),),
                ),
                deadline=time.monotonic() + _COMMAND_SECONDS_LEFT,
            )
            holding.result(timeout=60)
        finally:
            person.close()
        assert current.record_revision == completed.projection.record_revision > baseline.record_revision
        facts = [
            item.value for item in current.items(ProfileViewPageKind.FACTS) if isinstance(item, ProfileViewFactItem)
        ]
        assert "Persona" in facts
