"""Shared actual CLI-adjacent TUI, MCP and native protected-read probes."""

from __future__ import annotations

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from uuid import UUID, uuid4

from mcp import ClientSession

from cadrumo.adapters.local_runtime.automation_decision import AutomationDecisionRunError, run_automation_decision
from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError, frontend_failure_code
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
from cadrumo.application.runtime.contracts import RuntimeRefusalCode
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
from dev.packaging.command_execution import run_command

from .harness import Connection, LifecycleHarness, Profile

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


def issue_key(harness: LifecycleHarness, profile: Profile) -> UUID:
    """Issue one profile's key as the person does, returning the reference an agent is launched with.

    The person runs ``config profile automation create --use agent`` for the
    selected profile and approves the request from a signed-in connection. The
    agent never takes part: it is started with the reference.
    """
    deadline = time.monotonic() + 120
    with ThreadPoolExecutor(max_workers=1) as pool:
        creating = pool.submit(
            harness.cli, "profile", "automation", "create", "--use", "agent", profile_secret=profile.password
        )
        human = harness.connect(profile.profile_id)
        human.client.resume_receipt()
        while not (requests := read_automation_inventory(human.client).projection.requests):
            if creating.done():
                creating.result()
                raise AssertionError("The key request ended before it reached the person")
            if time.monotonic() >= deadline:
                raise AssertionError("The key request never reached the person")
            time.sleep(0.5)
        (review,) = requests
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
    reference = UUID(created["result"]["credential_reference"])
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
