"""Shared actual CLI-adjacent TUI, MCP and native protected-read probes."""

from __future__ import annotations

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from typing import Any
from uuid import UUID, uuid4

from mcp import ClientSession

from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.auth.auth_read_contracts import AuthReadProjection, AuthReadRequest
from cadrumo.application.diagnostics_read_contracts import DiagnosticsReadProjection, DiagnosticsReadRequest
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationPublicTerminalEventV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    DisclosureCategory,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.automation_operations import AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.profile_operation_contracts import (
    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
    ProfileMutationOperationProjection,
)
from cadrumo.application.user_profile.view_operation import (
    PROFILE_VIEW_OPERATION_DEFINITION_ID,
    ProfileViewFactItem,
    ProfileViewOperationProjection,
    ProfileViewPageKind,
)
from cadrumo.core.operations import OperationLifecycle, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo_client.contracts.contracts import RefusalCode
from cadrumo_client.contracts.operation_access import (
    OperationAcknowledged,
    OperationContract,
    OperationControl,
    OperationObserve,
    OperationObserved,
    OperationProjected,
    OperationResult,
    OperationSubmit,
    OperationSubmitted,
)
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.transport.automation_decision import AutomationDecisionRunError, run_automation_decision
from cadrumo_client.transport.automation_inventory import read_automation_inventory
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError, frontend_failure_code
from dev.packaging.command_execution import run_command

from .harness import Connection, LifecycleHarness, Profile
from .proof_support import ProcessIdentity, verified_relay
from .session_holder import RuntimeSessionHolder

# The package interpreter imports the production TUI adapter without mounting Textual.
_TUI_READ = """
import asyncio, json, sys
from uuid import UUID
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.adapters.persistence.storage.errors import KeyringUnavailableError
from cadrumo.core.errors.error_codes import get_registered_error_code
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.entrypoints.tui.profile.runtime_overview import read_runtime_profile_overview
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo.application.operations.models import OperationId
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
async def read():
    client = await open_installed_client(profile_id=UUID(sys.argv[1]), frontend=OperationFrontendProjection.TUI)
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
except (FrontendRefusedError, RefusalError, ProfileReceiptRefusedError) as error:
    reason = error.reason
    print(json.dumps({'refused': getattr(reason, 'value', reason)}))
    sys.exit(2)
except KeyringUnavailableError as error:
    print(json.dumps({'refused': get_registered_error_code(error).code}))
    sys.exit(2)
"""

_KEY_REQUEST = """
import asyncio, json, sys
from pathlib import Path
from uuid import UUID
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.automation_enrollment import EnrollmentProposal, EnrollmentStage
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.operation_composition import build_manifest_operation_registry
from cadrumo_client.transport.automation_requester import AutomationRequesterJourney
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_harness.access.automation_key import agent_key_proposal, agent_key_scope
async def request():
    client = await open_installed_client(profile_id=UUID(sys.argv[1]), frontend=OperationFrontendProjection.CLI)
    try:
        enrollment = client.prepare_enrollment(installed_automation_secret_store())
        contracts = build_manifest_operation_registry().public_contract_set
        proposal: EnrollmentProposal = agent_key_proposal(
            agent_key_scope(contracts), destination_id=enrollment.prepared.destination_id, now=now()
        )
        journey = AutomationRequesterJourney(enrollment, timeout=120)
        submitted = journey.submit(proposal)
        control = Path(sys.argv[2])
        partial = control.with_suffix('.partial')
        partial.write_text(
            json.dumps({'profile_id': str(client.profile_id), 'receipt': submitted.model_dump(mode='json')}),
            encoding='utf-8',
        )
        partial.replace(control)
        completion = journey.wait_for_terminal()
        if completion.terminal.stage is not EnrollmentStage.COMPLETE or completion.credential is None:
            raise RuntimeError('protected enrollment did not complete')
        print(
            json.dumps(
                {
                    'credential_reference': str(completion.credential.credential_reference),
                    'submitted': submitted.model_dump(mode='json'),
                    'terminal': completion.terminal.model_dump(mode='json'),
                }
            )
        )
    finally:
        client.close()
asyncio.run(request())
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


async def _mcp_settle(
    client: ClientSession,
    profile: Profile,
    definition_id: str,
    payload: dict[str, Any],
    *,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Run one operation over MCP to a successful terminal and return its released projection."""
    described = await _call(client, "describe", {"definition_id": definition_id})
    contract = described["description"]["contract"]
    request: dict[str, Any] = {
        "definition_id": definition_id,
        "subject_ref": profile_operation_subject(str(profile.profile_id)),
        "payload": payload,
    }
    if idempotency_key is not None:
        request["idempotency_key"] = idempotency_key
    submitted = await _call(client, "execute", request)
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
        raise AssertionError(f"MCP {definition_id} terminal={terminal}; failure_codes={failure_codes}")
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
    return result["document"]["projection"]


async def attend_mcp(
    holder: RuntimeSessionHolder, client: ClientSession, *, harness: LifecycleHarness, invocation: ProcessIdentity
) -> None:
    """Review only this retained packaged relay's ask through the held person session."""
    asking = asyncio.create_task(_call(client, "describe", {"definition_id": "auth.local-read"}))
    deadline = time.monotonic() + 90
    try:
        while True:
            inventory = await asyncio.to_thread(holder.command, "attendance_inventory")
            candidates = inventory.get("candidates")
            if not isinstance(candidates, list):
                raise AssertionError("Held runtime returned no attendance inventory")
            matching = [
                item
                for item in candidates
                if isinstance(item, dict)
                and verified_relay(item.get("process_id"), harness.package / "bin/cadrumo-mcp.exe", invocation)
            ]
            if len(matching) > 1:
                raise AssertionError("Multiple asks came from the owned relay")
            if matching:
                attendance_id = matching[0].get("attendance_id")
                if not isinstance(attendance_id, str):
                    raise AssertionError("Owned relay ask has no identity")
                decided = await asyncio.to_thread(
                    holder.command, "attendance_decision", attendance_id=attendance_id, approve=True
                )
                if decided.get("kind") != "attendance_decided" or decided.get("approved") is not True:
                    raise AssertionError("Runtime did not approve the reviewed relay")
                await asking
                return
            if asking.done():
                await asking
                raise AssertionError("Relay answered without the person's attendance review")
            if time.monotonic() >= deadline:
                raise AssertionError("Runtime recorded no ask from the owned relay")
            await asyncio.sleep(0.05)
    finally:
        if not asking.done():
            asking.cancel()
            with suppress(asyncio.CancelledError):
                await asking


async def _mcp_read(client: ClientSession, profile: Profile) -> None:
    document = await _mcp_settle(
        client, profile, "auth.local-read", {"profile_id": str(profile.profile_id), "kind": "status"}
    )
    body = AuthReadProjection.model_validate_json(json.dumps(document))
    if not (body.profile_id == profile.profile_id and body.status is not None):
        raise AssertionError("Protected application probe failed")


async def _mcp_profile_facts(client: ClientSession, profile: Profile) -> ProfileViewOperationProjection:
    """Read every stored fact of the profile over MCP, pinned to one revision."""
    payload: dict[str, Any] = {"profile_id": str(profile.profile_id), "page_kind": ProfileViewPageKind.FACTS.value}
    first = ProfileViewOperationProjection.model_validate_json(
        json.dumps(await _mcp_settle(client, profile, PROFILE_VIEW_OPERATION_DEFINITION_ID, payload))
    )
    if not (first.profile_id == profile.profile_id and first.outcome == "page"):
        raise AssertionError("MCP profile view was not released")
    items = list(first.items)
    cursor = first.next_cursor
    while cursor is not None:
        page = ProfileViewOperationProjection.model_validate_json(
            json.dumps(
                await _mcp_settle(
                    client,
                    profile,
                    PROFILE_VIEW_OPERATION_DEFINITION_ID,
                    payload
                    | {
                        "cursor": cursor,
                        "expected_revision": first.record_revision,
                        "expected_content_digest": str(first.content_digest),
                    },
                )
            )
        )
        if not (page.outcome == "page" and page.record_revision == first.record_revision):
            raise AssertionError("MCP profile view changed revision while paging")
        items.extend(page.items)
        cursor = page.next_cursor
    return first.model_copy(update={"items": tuple(items), "next_cursor": None})


def _fact(view: ProfileViewOperationProjection, path: str) -> str | None:
    return next(
        (item.value for item in view.items if isinstance(item, ProfileViewFactItem) and item.path == path), None
    )


async def mcp_edit_profile(
    client: ClientSession, profile: Profile, *, path: str, previous: str | None, value: str
) -> None:
    """Read the profile, change one fact and read it back, all as the agent."""
    before = await _mcp_profile_facts(client, profile)
    if _fact(before, path) != previous:
        raise AssertionError("The agent did not read the profile value it expected before editing")
    mutation = ProfileMutationOperationProjection.model_validate_json(
        json.dumps(
            await _mcp_settle(
                client,
                profile,
                PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
                {
                    "profile_id": str(profile.profile_id),
                    "expected_revision": before.record_revision,
                    "expected_content_digest": str(before.content_digest),
                    "path": path,
                    "value": value,
                },
                idempotency_key=str(uuid4()),
            )
        )
    )
    after = await _mcp_profile_facts(client, profile)
    if not (after.record_revision > before.record_revision and after.record_revision == mutation.record_revision):
        raise AssertionError("The agent's profile edit did not publish a new revision")
    if _fact(after, path) != value:
        raise AssertionError("The agent did not read back the profile value it wrote")


def _observe_read(
    connection: Connection, operation_id: OperationId, definition_id: str = "auth.local-read"
) -> OperationObservationSuccessV1:
    reply = connection.client.operation(
        OperationObserve(
            request_id=uuid4(),
            profile_id=connection.client.profile_id,
            session_id=connection.client.session_id,
            observation=OperationObservationRequestV1(operation_id=operation_id, after_cursor=0, page_limit=32),
        ),
        deadline=time.monotonic() + 10,
    )
    if not (isinstance(reply, OperationObserved)):
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
        OperationSubmit(
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
    if not (isinstance(submitted, OperationSubmitted)):
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
                OperationControl(
                    action="operation_resume" if continuing else "operation_start",
                    request_id=uuid4(),
                    profile_id=client.profile_id,
                    session_id=client.session_id,
                    operation_id=operation_id,
                ),
                deadline=deadline,
            )
            break
        except FrontendRefusedError as refusal:
            if not continuing or refusal.reason != "operation_unavailable" or time.monotonic() >= deadline:
                raise
            if (
                _observe_read(connection, operation_id, definition_id).projection.lifecycle
                is not OperationLifecycle.CREATED
            ):
                raise AssertionError("Protected durable-operation probe failed") from None
            time.sleep(2)
    if not (isinstance(started, OperationAcknowledged)):
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
        OperationResult(
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
    if not (isinstance(reply, OperationProjected)):
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
        OperationContract(
            request_id=uuid4(),
            profile_id=profile_id or connection.client.profile_id,
            session_id=session_id,
            definition_id="auth.local-read",
        ),
        deadline=time.monotonic() + 5,
    )


def _refused(reply: object) -> None:
    # A denial must originate at the server, not a cleared frontend attribute.
    if not (isinstance(reply, AccessRefusal)):
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


def issue_key(harness: LifecycleHarness, profile: Profile) -> UUID:
    """Issue one profile's key as the person does, returning the reference an agent is launched with.

    The package SDK submits a finite contract-derived proposal with its
    runtime-minted destination. A separate signed-in person connection approves
    that exact request with protected password proof. Only the verified native
    credential reference is returned to the agent's launch configuration.
    """
    deadline = time.monotonic() + 120
    request_control = harness.root / f"key-request-{uuid4()}.json"
    harness.resources.callback(request_control.unlink, missing_ok=True)
    harness.resources.callback(request_control.with_suffix(".partial").unlink, missing_ok=True)

    def request() -> dict[str, Any]:
        result = run_command(
            [
                str(harness.package / "python.exe"),
                "-I",
                "-c",
                _KEY_REQUEST,
                str(profile.profile_id),
                str(request_control),
            ],
            cwd=harness.root,
            environment=child_environment(ChildEnvironmentProfile.STRICT, harness.root),
            timeout_seconds=125,
        )
        if result.returncode != 0:
            raise AssertionError("Packaged protected enrollment requester failed")
        return json.loads(result.stdout)

    with ThreadPoolExecutor(max_workers=1) as pool:
        creating = pool.submit(request)
        human = harness.connect(profile.profile_id)
        human.client.resume_receipt()
        while not request_control.is_file():
            if creating.done():
                creating.result()
                raise AssertionError("The key request ended before publishing its review identity")
            if time.monotonic() >= deadline:
                raise AssertionError("The key requester never published its review identity")
            time.sleep(0.5)
        selected = json.loads(request_control.read_text(encoding="utf-8"))
        if selected["profile_id"] != str(profile.profile_id):
            raise AssertionError("The key requester selected another profile")
        receipt = selected["receipt"]
        while True:
            requests = read_automation_inventory(human.client).projection.requests
            matching = [
                item
                for item in requests
                if str(item.receipt.request_id) == receipt["request_id"]
                and str(item.receipt.review_digest) == receipt["review_digest"]
            ]
            if len(matching) == 1:
                review = matching[0]
                break
            if matching or creating.done() or time.monotonic() >= deadline:
                raise AssertionError("The exact SDK key request was not available for review")
            time.sleep(0.5)
        # An agent key always grants the profile's values and its own operations' metadata.
        if {item.category for item in review.proposal.scope.disclosure_categories} != {
            DisclosureCategory.PROFILE_VALUES,
            DisclosureCategory.OPERATION_METADATA,
        }:
            raise AssertionError("The agent key request did not grant exactly its data categories")
        try:
            decided = run_automation_decision(
                human.client, review, decision="approve", password=bytearray(profile.password, "utf-8")
            )
        except AutomationDecisionRunError as error:
            error.add_note("approval_failure " + json.dumps(_approval_facts(human, error, deadline)))
            raise
        created = creating.result(timeout=120)
    if created["submitted"] != receipt or any(
        created["terminal"][member] != receipt[member]
        for member in ("profile_id", "request_id", "review_digest", "grant_id")
    ):
        raise AssertionError("Protected delivery differs from the reviewed SDK request")
    request_control.unlink(missing_ok=True)
    reference = UUID(created["credential_reference"])
    if str(reference) != created["terminal"]["credential_reference"]:
        raise AssertionError("Credential reference differs from protected terminal delivery")
    harness.resources.callback(installed_automation_secret_store().delete, CLIENT_NAMESPACE, str(reference))
    if decided.effect.value != "updated":
        raise AssertionError("Enrollment approval did not update native custody")
    return reference


def _approval_facts(human: Connection, error: AutomationDecisionRunError, deadline: float) -> dict[str, str]:
    """Describe a failed approval with bounded public codes only; no exception context or private operands."""
    facts = {
        "code": error.reason,
        "terminal_condition": "unknown" if error.terminal_condition is None else error.terminal_condition.value,
        "effect": "unknown" if error.effect is None else error.effect.value,
        "observation": "no_remaining_budget",
    }
    if deadline - time.monotonic() >= 10:
        try:
            state = _observe_read(human, error.operation_id, AUTOMATION_APPROVE_OPERATION_DEFINITION_ID).projection
            facts.update(
                observation="observed",
                lifecycle=state.lifecycle.value,
                phase_code=state.phase_code or "unknown",
                failure_error_code=state.failure_error_code or "unknown",
                terminal_condition="unknown" if state.terminal_condition is None else state.terminal_condition.value,
                effect=state.effect.value,
            )
        except Exception as observation_error:
            facts.update(observation="unavailable", observation_code=frontend_failure_code(observation_error))
    codes = {
        "unknown",
        "unreported",
        "decision_unsettled",
        "REFUSED_AUTOMATION_ADMINISTRATION",
        *(code.value for code in RefusalCode),
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
    return dict(sorted(facts.items()))


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
