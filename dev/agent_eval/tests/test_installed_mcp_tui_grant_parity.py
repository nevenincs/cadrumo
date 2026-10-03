"""Installed MCP reconnects a TUI-reviewed rotation from real native custody.

Initial enrollment and OS-login observations reuse synthetic fixture controls.
Server wraps, rotated client delivery, installed stdio admission and profile
workers are real. Windows requires the selected protected Credential Manager
facility with a normal interactive token; Linux uses its protected native
collection. This does not prove a native desktop login or expiry event.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Literal, cast
from uuid import UUID

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from textual.pilot import Pilot
from textual.widgets import Button, DataTable, Input, Static

from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.automation_requester import (
    AutomationRequesterCompletion,
    AutomationRequesterJourney,
)
from cadrumo.adapters.local_runtime.enrollment_client import NativeEnrollmentClient
from cadrumo.adapters.local_runtime.framing import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import (
    ClientCredentialMetadata,
    NativeClientCredentialStore,
)
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import native_automation_secret_store
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.adapters.persistence.storage.custody.tests.test_windows_automation_secret_store_native import (
    require_selected_normal_desktop,
)
from cadrumo.application.auth.read_operation import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
    OperationSubmissionReceiptV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicDefinitionContractV1
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import (
    KEY_ROTATION_MAXIMUM_OVERLAP,
    AccessDenialCode,
    AuthorityState,
    ProfileAccessStatus,
)
from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_custody_port import (
    AutomationCustodyCode,
    AutomationCustodyError,
)
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentStage,
)
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
    profile_operation_subject,
)
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path
from cadrumo.entrypoints.cli.tests.native_api_cli_support import native_api_cli_session
from cadrumo.entrypoints.runtime.profile_host import RuntimeProfileHost
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.profile.automation_inventory import RuntimeAutomationInventoryScreen
from cadrumo.entrypoints.tui.secret.automation_decision import RuntimeAutomationDecisionScreen

from .test_installed_authenticated_stdio import (
    _installed_mcp_executable,
    _native_backend_for_current_platform,
    _scope_for_auth_read,
    _unused_reference,
)

if TYPE_CHECKING:
    from pydantic import SecretBytes

    from cadrumo.application.operations.models import OperationId
    from cadrumo.application.runtime.enrollment_access import EnrollmentCredentialBinding, RuntimeEnrollmentDelivery
    from cadrumo.application.runtime.worker_authorization import WorkerAuthorizationRequest
    from cadrumo.application.runtime.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest
    from cadrumo.application.user_profile.automation_enrollment import EnrollmentTransition

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.skipif(
        sys.platform not in {"linux", "win32"},
        reason="requires installed MCP and a supported protected native secret store",
    ),
]

_FENCED = frozenset({"session_inactive", "connection_mismatch", "key_inactive", "grant_inactive"})
_REVOKED = frozenset({"key_inactive", "grant_inactive"})

type _ProgressStage = Literal[
    "fixture_enter",
    "fixture_exited",
    "initial_store_enter",
    "initial_store_exit",
    "first_sdk_initialize_enter",
    "first_sdk_initialized",
    "first_sdk_read_enter",
    "first_sdk_read_exit",
    "first_sdk_closed",
    "requester_prepared",
    "requester_submitted",
    "approve_enter",
    "approve_exit",
    "delivery_wait_enter",
    "delivery_wait_exit",
    "review_cleanup_enter",
    "review_cleanup_exit",
    "rotated_sdk_initialize_enter",
    "rotated_sdk_initialized",
    "rotated_sdk_read_enter",
    "rotated_sdk_read_exit",
    "cli_deny_enter",
    "cli_deny_exit",
    "revoked_sdk_initialize_enter",
    "revoked_sdk_initialized",
    "cleanup_enter",
    "cleanup_exit",
    "preflight_enter",
    "preflight_exit",
    "host_phase_enter",
    "host_phase_exit",
    "publication_enter",
    "publication_exit",
    "store_enter",
    "store_exit",
    "possession_enter",
    "possession_exit",
    "poll_enter",
    "poll_exit",
    "reconcile_enter",
    "reconcile_exit",
]


def _record(value: object) -> dict[str, object]:
    assert isinstance(value, dict)
    return cast("dict[str, object]", value)


def _status(value: object, profile_id: UUID) -> ProfileAccessStatus:
    document = _record(value)
    assert document["outcome"] == "status"
    status = ProfileAccessStatus.model_validate_json(canonical_json_bytes(document["status"]))
    assert status.profile_id == profile_id
    assert status.connected and status.credential_authenticated and status.profile_bound
    assert status.grant_valid and status.denial is None and status.session_id is not None
    return status


async def _private_read(client: ClientSession, profile_id: UUID) -> OperationResultProjectionRequestV1:
    described = await client.call_tool("describe", {"definition_id": AUTH_READ_OPERATION_DEFINITION_ID})
    assert not described.is_error
    description = _record(_record(described.structured_content)["description"])
    contract = OperationPublicDefinitionContractV1.model_validate_json(canonical_json_bytes(description["contract"]))
    assert contract.definition_id == AUTH_READ_OPERATION_DEFINITION_ID and contract.result_schema is not None
    request = AuthReadRequest(profile_id=profile_id, kind="status")
    submitted = await client.call_tool(
        "execute",
        {
            "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
            "subject_ref": profile_operation_subject(str(profile_id)),
            "payload": request.model_dump(mode="json"),
        },
    )
    assert not submitted.is_error
    document = _record(submitted.structured_content)
    assert document["outcome"] == "submitted"
    receipt = OperationSubmissionReceiptV1.model_validate_json(canonical_json_bytes(document["receipt"]))
    observation = OperationObservationRequestV1(operation_id=receipt.operation_id, after_cursor=0, page_limit=32)
    terminal: OperationObservationSuccessV1 | None = None
    async with asyncio.timeout(60):
        while terminal is None:
            observed = await client.call_tool("observe", {"observation": observation.model_dump(mode="json")})
            assert not observed.is_error
            reply = _record(_record(observed.structured_content)["reply"])
            current = OperationObservationSuccessV1.model_validate_json(canonical_json_bytes(reply["observation"]))
            if current.projection.lifecycle is OperationLifecycle.TERMINAL:
                terminal = current
            else:
                await asyncio.sleep(0.05)
    assert terminal.projection.operation_id == receipt.operation_id
    assert terminal.projection.definition_id == AUTH_READ_OPERATION_DEFINITION_ID
    assert terminal.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.projection.effect is OperationEffect.NONE
    result_request = OperationResultProjectionRequestV1(
        operation_id=receipt.operation_id,
        terminal_revision=terminal.projection.revision,
        definition_contract_digest=contract.definition_contract_digest,
        result_schema=contract.result_schema,
    )
    released = await client.call_tool("result", {"result": result_request.model_dump(mode="json")})
    assert not released.is_error
    result = OperationResultProjectionSuccessV1[AuthReadProjection].model_validate_json(
        canonical_json_bytes(_record(_record(released.structured_content)["document"]))
    )
    assert result.definition_contract_digest == contract.definition_contract_digest
    assert result.result_schema == contract.result_schema
    assert result.projection.profile_id == profile_id and result.projection.kind == "status"
    assert result.projection.status is not None
    return result_request


class _NativeReferenceCleanup:
    """Retain exact native items, including a candidate after uncertain delivery."""

    def __init__(self, store: NativeClientCredentialStore, initial: ClientCredentialMetadata) -> None:
        self.store = store
        self.owned = [initial]
        self.pending: NativeEnrollmentClient | None = None

    async def close(self) -> None:
        errors: list[BaseException] = []
        pending = self.pending
        if pending is not None:
            try:
                metadata = await asyncio.to_thread(pending.delivered_credential_metadata)
                if metadata not in self.owned:
                    self.owned.append(metadata)
                self.pending = None
            except BaseException as error:
                errors.append(error)
        for metadata in tuple(self.owned):
            try:
                await asyncio.to_thread(
                    self.store.delete,
                    credential_reference=metadata.credential_reference,
                    grant_id=metadata.grant_id,
                    key_id=metadata.key_id,
                    review_digest=metadata.review_digest,
                )
            except BaseException as error:
                errors.append(error)
            else:
                self.owned.remove(metadata)
        if errors:
            raise BaseExceptionGroup("exact native credential cleanup requires retry", errors)


async def _until(pilot: Pilot[object], predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(90):
        while not predicate():
            await pilot.pause(0.05)


async def _settle_delivery(delivery: asyncio.Task[AutomationRequesterCompletion] | None) -> None:
    """Observe the retained task, including failure before one was created."""
    if delivery is not None:
        await await_cancellation_complete(delivery, task_name="tui-sdk-delivery-settle")


@pytest.mark.anyio
async def test_installed_sdk_reconnects_tui_rotated_native_reference_and_cli_revokes_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TUI reviews exact consent; SDK private release and denial use real custody."""
    if sys.platform == "win32":
        require_selected_normal_desktop()
    refusals: list[
        tuple[
            Literal["preflight", "phase", "publication"],
            Literal[
                "prepare",
                "inspect_recipient",
                "deliver_and_verify",
                "close",
                "commit_review",
                "publish_candidate",
                "activate",
                "decline",
            ],
            OperationId,
            AutomationCustodyCode | AccessDenialCode,
        ]
    ] = []
    client_delivery: list[
        tuple[
            Literal["store", "possession", "poll"],
            float,
            AutomationCustodyCode | AccessDenialCode | RuntimeRefusalCode | None,
        ]
    ] = []
    original_preflight = RuntimeProfileHost.approval_preflight
    original_phase = RuntimeProfileHost.approval_phase
    original_publication = RuntimeProfileHost.approval_publication
    original_store = NativeEnrollmentClient._store_candidate
    original_possession = NativeEnrollmentClient._possession
    original_poll = NativeEnrollmentClient.poll
    progress_guard = Lock()
    progress_path = tmp_path / "installed-mcp-tui-grant-progress.json"

    def traced_preflight(host: RuntimeProfileHost, request: WorkerApprovalRequest) -> None:
        progress("preflight_enter")
        try:
            original_preflight(host, request)
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            refusals.append(("preflight", request.phase, request.binding.operation_id, error.reason))
            raise
        finally:
            progress("preflight_exit")

    def traced_phase(
        host: RuntimeProfileHost, request: WorkerApprovalRequest, password: SecretBytes | None
    ) -> bool | None:
        progress("host_phase_enter")
        try:
            return original_phase(host, request, password)
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            refusals.append(("phase", request.phase, request.binding.operation_id, error.reason))
            raise
        finally:
            progress("host_phase_exit")

    def traced_publication(
        host: RuntimeProfileHost, authority: WorkerAuthorizationRequest, command: WorkerApprovalPublication
    ) -> EnrollmentTransition | None:
        progress("publication_enter")
        try:
            return original_publication(host, authority, command)
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            refusals.append(("publication", command.phase, command.binding.operation_id, error.reason))
            raise
        finally:
            progress("publication_exit")

    def traced_store(client: NativeEnrollmentClient, offer: EnrollmentCredentialBinding, secret: SecretBytes) -> None:
        started = time.monotonic()
        progress("store_enter")
        try:
            original_store(client, offer, secret)
        except (AutomationCustodyError, ProfileAccessRefusedError, RuntimeRefusalError) as error:
            client_delivery.append(("store", time.monotonic() - started, error.reason))
            raise
        else:
            client_delivery.append(("store", time.monotonic() - started, None))
        finally:
            progress("store_exit")

    def traced_possession(client: NativeEnrollmentClient, offer: EnrollmentCredentialBinding) -> SecretBytes | None:
        started = time.monotonic()
        progress("possession_enter")
        try:
            result = original_possession(client, offer)
        except (AutomationCustodyError, ProfileAccessRefusedError, RuntimeRefusalError) as error:
            client_delivery.append(("possession", time.monotonic() - started, error.reason))
            raise
        else:
            client_delivery.append(("possession", time.monotonic() - started, None))
            return result
        finally:
            progress("possession_exit")

    def traced_poll(client: NativeEnrollmentClient, *, timeout: float = 10.0) -> RuntimeEnrollmentDelivery | None:
        started = time.monotonic()
        progress("poll_enter")
        try:
            result = original_poll(client, timeout=timeout)
        except (AutomationCustodyError, ProfileAccessRefusedError, RuntimeRefusalError) as error:
            client_delivery.append(("poll", time.monotonic() - started, error.reason))
            raise
        else:
            client_delivery.append(("poll", time.monotonic() - started, None))
            return result
        finally:
            progress("poll_exit")

    def trace_document() -> dict[str, object]:
        return {
            "approval_refusals": [
                {"boundary": boundary, "phase": phase, "operation_id": operation_id, "reason": reason.value}
                for boundary, phase, operation_id, reason in tuple(refusals)
            ],
            "client_delivery": [
                {"phase": phase, "elapsed_seconds": round(elapsed, 3), "refusal": code.value if code else None}
                for phase, elapsed, code in tuple(client_delivery)
            ],
        }

    def safe_trace() -> str:
        return "canonical approval trace=" + json.dumps(trace_document())

    def progress(stage: _ProgressStage) -> None:
        with progress_guard:
            pending_path = progress_path.with_suffix(".pending")
            pending_path.write_text(json.dumps({"stage": stage, "trace": trace_document()}) + "\n", encoding="utf-8")
            pending_path.replace(progress_path)

    monkeypatch.setattr(RuntimeProfileHost, "approval_preflight", traced_preflight)
    monkeypatch.setattr(RuntimeProfileHost, "approval_phase", traced_phase)
    monkeypatch.setattr(RuntimeProfileHost, "approval_publication", traced_publication)
    backend = _native_backend_for_current_platform()
    native_store = native_automation_secret_store(backend)
    assert native_store.backend is backend
    executable = _installed_mcp_executable()
    assert executable.is_file(), "the installed cadrumo-mcp executable is required"
    progress("fixture_enter")
    with (
        override_settings(cadrumo_output_language="en", cadrumo_profile_kdf_measure_calibration=False),
        native_api_cli_session(
            tmp_path,
            scope_for_destination=_scope_for_auth_read,
            prepare_profile=lambda _profile_id, _root: None,
            server_native_store=native_store,
        ) as profile,
    ):
        source = NativeClientCredentialStore.resolve_reference(
            credential_reference=profile.credential_reference,
            binding=profile.binding,
            secrets_store=profile._client_native,
        )
        original = source.metadata
        protected = NativeClientCredentialStore(
            secrets_store=native_store,
            binding=profile.binding,
            client_id=original.client_id,
            destination_id=original.destination_id,
        )
        reference = _unused_reference(protected)
        initial = ClientCredentialMetadata(
            credential_reference=reference,
            profile_id=profile.profile_id,
            client_id=original.client_id,
            destination_id=original.destination_id,
            grant_id=original.grant_id,
            key_id=original.key_id,
            review_digest=original.review_digest,
        )
        cleanup = _NativeReferenceCleanup(protected, initial)
        primary: BaseException | None = None

        def parameters(selected: UUID) -> StdioServerParameters:
            return StdioServerParameters(
                command=str(executable),
                args=["--profile-id", str(profile.profile_id), "--credential-reference", str(selected)],
                cwd=tmp_path,
                env={
                    "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
                    "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
                    "PYDANTIC_DISABLE_PLUGINS": "__all__",
                },
            )

        try:
            progress("initial_store_enter")
            assert (
                protected.replace(
                    credential_reference=reference,
                    grant_id=initial.grant_id,
                    key_id=initial.key_id,
                    review_digest=initial.review_digest,
                    credential=source.read(),
                )
                == initial
            )
            progress("initial_store_exit")
            del source
            assert protected.inspect(credential_reference=reference) == initial
            with (tmp_path / "tui-grant-first.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters(reference), errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as sdk,
                ):
                    progress("first_sdk_initialize_enter")
                    await sdk.initialize()
                    progress("first_sdk_initialized")
                    status = await sdk.call_tool("status", {})
                    assert not status.is_error
                    first = _status(status.structured_content, profile.profile_id)
                    assert first.session_id is not None
                    progress("first_sdk_read_enter")
                    await _private_read(sdk, profile.profile_id)
                    progress("first_sdk_read_exit")
                    worker = await asyncio.to_thread(profile.worker_health, first.session_id)
                    assert worker.identity.binding == profile.binding and worker.exact_session_admitted
                    assert worker.alive
                    if sys.platform == "linux":
                        assert worker.linux_scope_owns_worker and worker.kernel_control_groups_match
                    else:
                        assert worker.windows_job_owns_worker
                    custody = await asyncio.to_thread(profile.server_custody_health)
                    assert custody.backend is backend and custody.runtime_uses_same_store
                    assert custody.binding == profile.binding and custody.wrapping_keys_valid
                    assert custody.grant_ids == (initial.grant_id,)
            progress("first_sdk_closed")
            assert profile.registered_sessions() == ()

            requester = await open_installed_credential_client(
                profile_id=profile.profile_id,
                credential_reference=reference,
                frontend=OperationFrontendProjection.TUI,
                secrets_store=native_store,
            )
            requester_owner = RuntimeTransportCleanup(requester)
            human = None
            human_owner = None
            review_primary: BaseException | None = None
            delivery: asyncio.Task[AutomationRequesterCompletion] | None = None
            rotated: ClientCredentialMetadata | None = None
            try:
                human = await open_installed_runtime_client(
                    profile_id=profile.profile_id, frontend=OperationFrontendProjection.TUI
                )
                human_owner = RuntimeTransportCleanup(human)
                password = bytearray(PROFILE_INPUT, "utf-8")
                human_status = await asyncio.to_thread(human.login_password, password)
                assert not any(password) and human_status.status.credential_authenticated
                before = (await asyncio.to_thread(read_automation_inventory, human)).projection
                grant = next(item for item in before.grants if item.grant_id == initial.grant_id)
                assert grant.state is AuthorityState.ACTIVE and grant.unattended
                assert grant.client_id == initial.client_id and grant.profile_id == profile.profile_id
                enrollment = await asyncio.to_thread(requester.prepare_grant_change, native_store)
                cleanup.pending = enrollment
                assert enrollment.prepared.client_id == initial.client_id
                assert enrollment.prepared.destination_id == initial.destination_id
                progress("requester_prepared")
                monkeypatch.setattr(NativeEnrollmentClient, "_store_candidate", traced_store)
                monkeypatch.setattr(NativeEnrollmentClient, "_possession", traced_possession)
                monkeypatch.setattr(NativeEnrollmentClient, "poll", traced_poll)

                def reconcile(
                    submitted_receipt: AutomationReceiptProjection, /, *, timeout: float
                ) -> AutomationReceiptProjection:
                    progress("reconcile_enter")
                    deadline = time.monotonic() + timeout
                    metadata = enrollment.delivered_credential_metadata()
                    assert metadata.profile_id == profile.profile_id and metadata.client_id == initial.client_id
                    assert metadata.destination_id == initial.destination_id
                    assert metadata.review_digest == submitted_receipt.review_digest

                    def remaining() -> float:
                        budget = deadline - time.monotonic()
                        if budget <= 0:
                            raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
                        return budget

                    async def reconcile_fresh() -> AutomationReceiptProjection:
                        fresh = await open_installed_credential_client(
                            profile_id=profile.profile_id,
                            credential_reference=metadata.credential_reference,
                            frontend=OperationFrontendProjection.TUI,
                            timeout=remaining(),
                            secrets_store=native_store,
                        )
                        reconciliation_primary: BaseException | None = None
                        try:
                            receipt = await await_cancellation_complete(
                                asyncio.to_thread(
                                    fresh.reconcile_enrollment, submitted_receipt.request_id, timeout=remaining()
                                ),
                                task_name="tui-sdk-fresh-reconciliation",
                            )
                            assert receipt.request_id == submitted_receipt.request_id
                            assert receipt.review_digest == submitted_receipt.review_digest
                            return receipt
                        except BaseException as error:
                            reconciliation_primary = error
                            raise
                        finally:
                            await close_async_resources(
                                RuntimeTransportCleanup(fresh),
                                task_name="tui-sdk-fresh-reconciliation-close",
                                primary_error=reconciliation_primary,
                            )

                    try:
                        return asyncio.run(reconcile_fresh())
                    finally:
                        progress("reconcile_exit")

                journey = AutomationRequesterJourney(enrollment, timeout=120, reconcile=reconcile)
                proposal = EnrollmentProposal(
                    kind=EnrollmentKind.ROTATE,
                    scope=_scope_for_auth_read(initial.destination_id),
                    expires_at=grant.expires_at,
                    key_expires_at=min(now() + timedelta(days=15), grant.expires_at),
                    unattended=grant.unattended,
                    allow_os_lock=grant.allow_os_lock,
                    target_grant_id=grant.grant_id,
                    target_key_id=initial.key_id,
                )
                submitted = await asyncio.to_thread(journey.submit, proposal)
                assert submitted.stage is EnrollmentStage.REQUESTED and submitted.grant_id == grant.grant_id
                progress("requester_submitted")
                inventory = RuntimeAutomationInventoryScreen(human)
                delivery = asyncio.create_task(asyncio.to_thread(journey.wait_for_terminal), name="tui-sdk-delivery")

                async def drive(pilot: Pilot[object]) -> None:
                    await pilot.pause()
                    await _until(
                        pilot,
                        lambda: inventory.access_lost or (inventory._inventory is not None and not inventory._busy),
                    )
                    assert not inventory.access_lost
                    rows = inventory._inventory
                    assert rows is not None
                    index = next(
                        i for i, item in enumerate(rows.requests) if item.receipt.request_id == submitted.request_id
                    )
                    review = rows.requests[index]
                    assert review.receipt == submitted and review.proposal.kind is EnrollmentKind.ROTATE
                    assert review.proposal.scope == grant.scope and review.proposal.expires_at == grant.expires_at
                    assert review.proposal.target_key_id == initial.key_id
                    table = inventory.query_one("#automation-inventory-requests", DataTable)
                    table.focus()
                    table.move_cursor(row=index)

                    def exact_selection_ready() -> bool:
                        selected = inventory._selected_review
                        return (
                            selected is not None
                            and selected.receipt == submitted
                            and selected.proposal == review.proposal
                            and not inventory._busy
                            and not inventory.query_one("#automation-inventory-approve", Button).disabled
                        )

                    await _until(pilot, lambda: inventory.access_lost or exact_selection_ready())
                    assert not inventory.access_lost and exact_selection_ready()
                    inventory.query_one("#automation-inventory-approve", Button).press()
                    await _until(pilot, lambda: isinstance(pilot.app.screen, RuntimeAutomationDecisionScreen))
                    await pilot.pause()
                    decision = pilot.app.screen
                    assert isinstance(decision, RuntimeAutomationDecisionScreen)
                    consent = str(decision.query_one("#automation-decision-review", Static).content)
                    assert str(submitted.request_id) in consent and submitted.review_digest in consent
                    assert str(initial.key_id) in consent and str(grant.grant_id) in consent
                    proof = decision.query_one("#automation-decision-password", Input)
                    assert proof.password and proof.value == ""
                    proof.value = PROFILE_INPUT
                    progress("approve_enter")
                    decision.query_one("#automation-decision-confirm", Button).press()
                    await _until(pilot, lambda: decision.settled_outcome is not None and not decision._busy)
                    progress("approve_exit")
                    outcome = decision.settled_outcome
                    assert outcome is not None and outcome.completed and not outcome.access_lost, safe_trace()
                    assert outcome.terminal_condition is OperationTerminalCondition.SUCCEEDED
                    assert outcome.effect is OperationEffect.UPDATED and outcome.operation_id is not None
                    assert proof.value == "" and decision._pending_proof is None
                    decision.action_close()
                    await _until(pilot, lambda: pilot.app.screen is inventory)
                    inventory.action_close()

                await ScreenHostApp(inventory).run_async(headless=True, auto_pilot=drive)
                progress("delivery_wait_enter")
                completion = await await_cancellation_complete(delivery, task_name="tui-sdk-delivery-settle")
                progress("delivery_wait_exit")
                assert completion == journey.completion
                completed = journey.completion
                assert completed is not None and completed.terminal.stage is EnrollmentStage.COMPLETE
                rotated = completed.credential
                assert rotated is not None and rotated.credential_reference != reference
                cleanup.owned.append(rotated)
                cleanup.pending = None
                assert rotated.grant_id == initial.grant_id and rotated.key_id != initial.key_id
                assert rotated.profile_id == profile.profile_id and rotated.client_id == initial.client_id
                assert (
                    rotated.destination_id == initial.destination_id
                    and rotated.review_digest == submitted.review_digest
                )
                assert protected.inspect(credential_reference=rotated.credential_reference) == rotated
                after = (await asyncio.to_thread(read_automation_inventory, human)).projection
                unchanged = next(item for item in after.grants if item.grant_id == grant.grant_id)
                assert unchanged == grant
                predecessor = next(item for item in after.keys if item.key_id == initial.key_id)
                successor = next(item for item in after.keys if item.key_id == rotated.key_id)
                assert predecessor.expires_at <= now() + KEY_ROTATION_MAXIMUM_OVERLAP
                assert successor.state is AuthorityState.ACTIVE and successor.expires_at == proposal.key_expires_at
            except BaseException as error:
                review_primary = error
                raise
            finally:
                progress("review_cleanup_enter")
                try:
                    try:
                        await _settle_delivery(delivery)
                    except BaseException as error:
                        if review_primary is None:
                            review_primary = error
                            raise
                        review_primary.add_note(f"delivery settlement also failed ({type(error).__name__})")
                finally:
                    await close_async_resources(
                        human_owner, requester_owner, task_name="tui-sdk-review-close", primary_error=review_primary
                    )
                    progress("review_cleanup_exit")

            assert rotated is not None
            with (tmp_path / "tui-grant-rotated.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters(rotated.credential_reference), errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as sdk,
                ):
                    progress("rotated_sdk_initialize_enter")
                    await sdk.initialize()
                    progress("rotated_sdk_initialized")
                    status = await sdk.call_tool("status", {})
                    assert not status.is_error
                    second = _status(status.structured_content, profile.profile_id)
                    assert second.session_id is not None and second.session_id != first.session_id
                    assert (
                        second.effective_scope == first.effective_scope
                        and second.grant_expires_at == first.grant_expires_at
                    )
                    assert second.grant_expires_at == grant.expires_at and second.session_expires_at is not None
                    assert second.session_expires_at > now()
                    assert profile.registered_sessions() == (second.session_id,)
                    worker = await asyncio.to_thread(profile.worker_health, second.session_id)
                    assert worker.identity.binding == profile.binding and worker.exact_session_admitted
                    assert worker.alive
                    if sys.platform == "linux":
                        assert worker.linux_scope_owns_worker and worker.kernel_control_groups_match
                    else:
                        assert worker.windows_job_owns_worker
                    progress("rotated_sdk_read_enter")
                    result_request = await _private_read(sdk, profile.profile_id)
                    progress("rotated_sdk_read_exit")
                    delete_profile_session(storage_root=tmp_path / "cadrumo-storage", profile_id=profile.profile_id)
                    progress("cli_deny_enter")
                    denied = await asyncio.to_thread(
                        profile.invoke_password,
                        "config",
                        "profile",
                        "automation",
                        "deny",
                        "grant",
                        str(initial.grant_id),
                    )
                    progress("cli_deny_exit")
                    assert denied.exit_code == 0, denied.output
                    document = _record(json.loads(denied.stdout))
                    assert document["command"] == "config.profile.automation.deny"
                    denial = _record(document["result"])
                    assert denial["kind"] == "grant" and denial["target_id"] == str(initial.grant_id)
                    assert _record(denial["receipt"])["access_denied"] is True
                    for tool, arguments in (
                        ("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID}),
                        ("result", {"result": result_request.model_dump(mode="json")}),
                    ):
                        refused = await sdk.call_tool(tool, arguments)
                        assert refused.is_error
                        refusal = _record(refused.structured_content)
                        assert refusal["outcome"] == "refused" and refusal["code"] in _FENCED
                        assert str(reference) not in repr(refusal) and str(rotated.credential_reference) not in repr(
                            refusal
                        )

            with (tmp_path / "tui-grant-revoked.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters(rotated.credential_reference), errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as sdk,
                ):
                    progress("revoked_sdk_initialize_enter")
                    await sdk.initialize()
                    progress("revoked_sdk_initialized")
                    status = await sdk.call_tool("status", {})
                    assert not status.is_error
                    revoked = _record(status.structured_content)
                    assert revoked["outcome"] == "status" and revoked["profile_id"] == str(profile.profile_id)
                    assert revoked["authenticated"] is False and revoked["denial"] in _REVOKED
                    refused = await sdk.call_tool("search", {"query": AUTH_READ_OPERATION_DEFINITION_ID})
                    assert refused.is_error and _record(refused.structured_content) == {
                        "outcome": "refused",
                        "code": revoked["denial"],
                    }
        except BaseException as error:
            primary = error
            error.add_note(safe_trace())
            raise
        finally:
            progress("cleanup_enter")
            await close_async_resources(cleanup, task_name="tui-sdk-native-credentials-close", primary_error=primary)
            progress("cleanup_exit")
    progress("fixture_exited")
