"""Shared actual CLI-adjacent TUI, MCP and native protected-read probes."""

from __future__ import annotations

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

from mcp import ClientSession

from cadrumo.adapters.local_runtime.automation_decision import AutomationDecisionRunError, run_automation_decision
from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.automation_requester import AutomationRequesterJourney
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError, frontend_failure_code
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


def issue_key(harness: LifecycleHarness, profile: Profile) -> UUID:
    """Issue one profile's key as the person does, returning the reference an agent is launched with.

    The person requests the key from a fresh connection, as
    ``config profile automation create`` does, and approves it from a signed-in
    one. The agent never takes part: it is started with the reference.
    """
    requester = harness.connect(profile.profile_id)
    enrollment = requester.client.prepare_enrollment(installed_automation_secret_store())
    destination = enrollment.prepared.destination_id
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
    journey = AutomationRequesterJourney(enrollment, timeout=120)
    submitted = journey.submit(proposal)
    human = harness.connect(profile.profile_id)
    human.client.resume_receipt()
    inventory = read_automation_inventory(human.client).projection
    review = next(item for item in inventory.requests if item.receipt.request_id == submitted.request_id)
    diagnostic_deadline = time.monotonic() + 120
    with ThreadPoolExecutor(max_workers=1) as pool:
        approval = pool.submit(
            run_automation_decision,
            human.client,
            review,
            decision="approve",
            password=bytearray(profile.password, "utf-8"),
        )
        primary: BaseException | None = None
        try:
            completed = journey.wait_for_terminal()
        except BaseException as error:
            primary = error
            raise
        finally:
            # A native approval may have published; join it before releasing its connection.
            try:
                decided = approval.result()
            except AutomationDecisionRunError as error:
                error.add_note("approval_failure " + json.dumps(_approval_facts(human, error, diagnostic_deadline)))
                if primary is not None:
                    raise BaseExceptionGroup("Enrollment requester and approval failed", [primary, error]) from None
                raise
    credential = completed.credential
    if credential is None:
        raise AssertionError("Completed enrollment has no credential reference")
    reference = credential.credential_reference
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
