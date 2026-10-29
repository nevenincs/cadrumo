"""Shared actual CLI-adjacent TUI, MCP and native protected-read probes."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.auth.auth_read_contracts import AuthReadProjection, AuthReadRequest
from cadrumo.application.diagnostics_read_contracts import DiagnosticsReadProjection, DiagnosticsReadRequest
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.automation_enrollment import AutomationReviewProjection
from cadrumo.application.user_profile.automation_operations import AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
from cadrumo.application.user_profile.view_operation import (
    ProfileViewPageKind,
)
from cadrumo.core.operations import OperationLifecycle, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.storage_environment import ChildEnvironmentProfile, child_environment
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import DisclosureCategory
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode
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

from . import agent_key_proposal
from .harness import Connection, LifecycleHarness, Profile

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
from cadrumo_runtime.host.frontend.tui.profile.overview_client import read_profile_overview
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo.application.operations.models import OperationId
from cadrumo_client.contracts.contracts import RefusalError
from cadrumo_client.contracts.sign_in_outcomes import ProfileReceiptRefusedError
async def read():
    client = await open_installed_client(profile_id=UUID(sys.argv[1]), frontend=OperationFrontendProjection.TUI)
    try:
        await asyncio.to_thread(client.resume_receipt)
        view = await asyncio.to_thread(
            read_profile_overview, client, profile_label='Lifecycle', output_language=OutputLanguage.EN
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

# The packaged interpreter loads the probe-owned proposal builder by path.
_KEY_REQUEST = """
import asyncio, importlib.util, json, sys
from pathlib import Path
from uuid import UUID
from cadrumo.adapters.persistence.storage.custody.automation_store_composition import installed_automation_secret_store
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo_client.contracts.enrollment_proposal import EnrollmentProposal
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.operation_composition import build_manifest_operation_registry
from cadrumo_client.transport.automation_requester import AutomationRequesterJourney
from cadrumo_client.transport.installed_client import open_installed_client
spec = importlib.util.spec_from_file_location('lifecycle_agent_key_proposal', sys.argv[3])
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
async def request():
    client = await open_installed_client(profile_id=UUID(sys.argv[1]), frontend=OperationFrontendProjection.CLI)
    try:
        enrollment = client.prepare_enrollment(installed_automation_secret_store())
        contracts = build_manifest_operation_registry().public_contract_set
        proposal: EnrollmentProposal = builder.agent_key_proposal(
            contracts, destination_id=enrollment.prepared.destination_id, now=now()
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
    _start_protected_read(connection, operation_id, definition_id, deadline, continuing=continuing)
    projection = _wait_protected_read(connection, operation_id, definition_id, deadline).projection
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
    reply = _require_result_reply(reply, operation_id)
    result = OperationResultProjectionSuccessV1[AuthReadProjection | DiagnosticsReadProjection].model_validate_json(
        json.dumps(reply.document)
    )
    if not (result.definition_contract_digest == contract.definition_contract_digest):
        raise AssertionError("Protected durable-operation probe failed")
    if not (result.result_schema == contract.result_schema):
        raise AssertionError("Protected durable-operation probe failed")
    if not (result.projection.profile_id == client.profile_id):
        raise AssertionError("Protected durable-operation probe failed")
    _validate_read_projection(result.projection, continuing=continuing)
    return operation_id


def _require_result_reply(reply: object, operation_id: OperationId) -> OperationProjected:
    """Check the result projection belongs to the submitted operation."""
    if not isinstance(reply, OperationProjected):
        raise AssertionError("Protected durable-operation probe failed")
    if not (reply.operation_id == operation_id and reply.projection_kind == "result"):
        raise AssertionError("Protected durable-operation probe failed")
    return reply


def _wait_protected_read(
    connection: Connection, operation_id: OperationId, definition_id: str, deadline: float
) -> OperationObservationSuccessV1:
    """Observe the operation to its successful terminal state within the original deadline."""
    while True:
        observation = _observe_read(connection, operation_id, definition_id)
        if observation.projection.lifecycle is OperationLifecycle.TERMINAL:
            break
        if not (time.monotonic() < deadline):
            raise AssertionError("Protected read did not settle")
        time.sleep(0.05)
    if observation.projection.terminal_condition is not OperationTerminalCondition.SUCCEEDED:
        raise AssertionError("Protected durable-operation probe failed")
    return observation


def _validate_read_projection(projection: AuthReadProjection | DiagnosticsReadProjection, *, continuing: bool) -> None:
    """Verify the operation-specific protected result shape."""
    if continuing:
        if not (isinstance(projection, DiagnosticsReadProjection)):
            raise AssertionError("Protected durable-operation probe failed")
        if not (projection.kind == "errors" and projection.errors is not None):
            raise AssertionError("Protected durable-operation probe failed")
    else:
        if not (isinstance(projection, AuthReadProjection)):
            raise AssertionError("Protected durable-operation probe failed")
        if not (projection.kind == "status" and projection.status is not None):
            raise AssertionError("Protected durable-operation probe failed")


def _start_protected_read(
    connection: Connection, operation_id: OperationId, definition_id: str, deadline: float, *, continuing: bool
) -> None:
    """Start or resume the operation within the retained lease deadline."""
    client = connection.client
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
                str(Path(agent_key_proposal.__file__).resolve(strict=True)),
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
        review = _wait_enrollment_review(human, receipt, creating.done, deadline)
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
    _require_delivery_receipt(created, receipt)
    request_control.unlink(missing_ok=True)
    reference = _delivered_credential(created)
    harness.resources.callback(installed_automation_secret_store().delete, CLIENT_NAMESPACE, str(reference))
    if decided.effect.value != "updated":
        raise AssertionError("Enrollment approval did not update native custody")
    return reference


def _require_delivery_receipt(created: Mapping[str, object], receipt: Mapping[str, object]) -> None:
    """Verify protected delivery names the exact reviewed request."""
    if created["submitted"] != receipt or any(
        cast(dict[str, object], created["terminal"])[member] != receipt[member]
        for member in ("profile_id", "request_id", "review_digest", "grant_id")
    ):
        raise AssertionError("Protected delivery differs from the reviewed SDK request")


def _delivered_credential(created: Mapping[str, object]) -> UUID:
    """Verify the returned credential reference agrees with terminal delivery."""
    reference = UUID(cast(str, created["credential_reference"]))
    terminal = cast(dict[str, object], created["terminal"])
    if str(reference) != terminal["credential_reference"]:
        raise AssertionError("Credential reference differs from protected terminal delivery")
    return reference


def _wait_enrollment_review(
    human: Connection, receipt: Mapping[str, object], requester_done: Callable[[], bool], deadline: float
) -> AutomationReviewProjection:
    """Wait for exactly the submitted request and digest, without extending the budget."""
    while True:
        requests = read_automation_inventory(human.client).projection.requests
        matching = [
            item
            for item in requests
            if str(item.receipt.request_id) == receipt["request_id"]
            and str(item.receipt.review_digest) == receipt["review_digest"]
        ]
        if len(matching) == 1:
            return matching[0]
        if matching or requester_done() or time.monotonic() >= deadline:
            raise AssertionError("The exact SDK key request was not available for review")
        time.sleep(0.5)


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
    return _sanitize_approval_facts(facts)


def _sanitize_approval_facts(facts: dict[str, str]) -> dict[str, str]:
    """Retain only public allowlisted codes in approval diagnostics."""
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
