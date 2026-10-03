"""Native CLI/TUI enrollment, delivery and revocation parity through one runtime."""

from __future__ import annotations

import asyncio
import json
import sys
import time
import traceback
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import Context, copy_context
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from click.testing import Result
from textual.pilot import Pilot
from textual.widgets import Button, Checkbox, DataTable, Input, Select, SelectionList, Static

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.server import RuntimeTransportServer
from cadrumo.adapters.local_runtime.tests.profile_worker_support import NativeRuntimeFixtureOwner, owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationPublicContractSetV1
from cadrumo.application.runtime.access_management import RuntimeAccessManagementRequest
from cadrumo.application.runtime.contracts import RuntimeByteChannel
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode
from cadrumo.application.user_profile.automation_enrollment import (
    EnrollmentStage,
)
from cadrumo.application.user_profile.operations import PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID
from cadrumo.conftest import authority_operation
from cadrumo.core.async_cleanup import AsyncCloseable, close_async_resources
from cadrumo.core.config import override_settings
from cadrumo.entrypoints.cli.config import runtime_automation_request
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.cli.tests.runtime_profile_cli_fixture import (
    RuntimeFailureObservation,
    observe_native_runtime_failures,
    runtime_failure_observation,
)
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.tests.test_profile_connections import LoginObservation
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.profile.automation_inventory import RuntimeAutomationInventoryScreen
from cadrumo.entrypoints.tui.runtime_access_management import RuntimeAccessManagementScreen
from cadrumo.entrypoints.tui.secret.automation_decision import RuntimeAutomationDecisionScreen
from cadrumo.entrypoints.tui.secret.automation_requester import RuntimeAutomationRequesterScreen
from cadrumo.entrypoints.tui.secret.automation_requester_contracts import AutomationRequestOutcome

__all__ = ["authority_operation"]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


def test_human_tui_enrollment_review_delivery_is_inspected_and_revoked_by_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real Windows transport/workers bridge both interfaces; secret stores are memory ports."""

    async def _until(pilot: Pilot[object], predicate, *, timeout: float = 90) -> None:
        async with asyncio.timeout(timeout):
            while not predicate():
                await asyncio.sleep(0.05)

    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    installation = runtime_installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with (
        override_settings(cadrumo_profile_kdf_measure_calibration=False),
        administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
        ) as subject,
    ):
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        delete_profile_session(storage_root=storage_root, profile_id=profile_id)
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=storage_root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: LoginObservation(owner_id(), login_id="tui-requester-native-login"),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        outcomes: list[AutomationRequestOutcome] = []
        access_failures: list[str] = []
        manage_access = profiles.manage_access

        def observed_access(
            context: RuntimeConnectionContext, channel: RuntimeByteChannel, request: RuntimeAccessManagementRequest
        ) -> None:
            try:
                manage_access(context, channel, request)
            except Exception as error:
                frames = traceback.extract_tb(error.__traceback__)
                access_failures.append(
                    type(error).__name__ + ": " + " -> ".join(f"{frame.name}:{frame.lineno}" for frame in frames)
                )
                raise

        monkeypatch.setattr(profiles, "manage_access", observed_access)

        async def run_human_journey() -> None:
            human = await open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
            human_owner = RuntimeTransportCleanup(human)
            human_primary: BaseException | None = None
            try:
                proof = bytearray(PROFILE_INPUT, "utf-8")
                admitted = await asyncio.to_thread(human.login_password, proof)
                assert not any(proof)
                assert admitted.status.profile_id == profile_id and admitted.status.credential_authenticated
                contract = await asyncio.to_thread(
                    human.contract,
                    PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID,
                    deadline=time.monotonic() + 30,
                )
                contracts = OperationPublicContractSetV1.build((contract,))

                async def open_fresh(selected_profile: UUID) -> RuntimeFrontendClient:
                    assert selected_profile == profile_id
                    return await open_installed_runtime_client(
                        profile_id=selected_profile, frontend=OperationFrontendProjection.TUI
                    )

                async def open_recovery() -> RuntimeFrontendClient:
                    return await open_fresh(profile_id)

                def requester_for(reviewer: RuntimeFrontendClient) -> RuntimeAutomationRequesterScreen:
                    assert reviewer is human
                    return RuntimeAutomationRequesterScreen(
                        profile_id=profile_id,
                        contracts=contracts,
                        secrets_store=subject.client_native,
                        open_client=open_fresh,
                        reviewer_client=reviewer,
                        journey_timeout=60,
                    )

                access = RuntimeAccessManagementScreen(
                    human, open_recovery_client=open_recovery, requester_factory=requester_for
                )

                async def drive(pilot: Pilot[object]) -> None:
                    await pilot.pause()
                    await _until(pilot, lambda: access._admin_available or access.access_lost)
                    assert not access.access_lost, (
                        str(access.query_one("#runtime-access-status", Static).content),
                        access_failures,
                    )
                    await _until(pilot, lambda: not access._busy)
                    access.query_one("#runtime-access-create-automation", Button).press()
                    await _until(pilot, lambda: isinstance(pilot.app.screen, RuntimeAutomationRequesterScreen))
                    await pilot.pause()
                    request = pilot.app.screen
                    assert isinstance(request, RuntimeAutomationRequesterScreen)
                    assert request._client is None and request._reviewer_client is human
                    request.query_one("#automation-request-operations", SelectionList).select(
                        PROFILE_FIELD_MUTATION_OPERATION_DEFINITION_ID
                    )
                    for action in subject.proposal.scope.actions:
                        request.query_one("#automation-request-actions", SelectionList).select(action.value)
                    request.query_one("#automation-request-period-mode", Select).value = "all"
                    request.query_one("#automation-request-independent", Checkbox).value = True
                    request.query_one("#automation-request-unattended", Checkbox).value = True
                    request.query_one(
                        "#automation-request-expiry", Input
                    ).value = subject.proposal.expires_at.isoformat()
                    assert subject.proposal.key_expires_at is not None
                    request.query_one(
                        "#automation-request-key-expiry", Input
                    ).value = subject.proposal.key_expires_at.isoformat()
                    request.query_one("#automation-request-submit", Button).press()
                    await _until(pilot, lambda: request._submitted is not None or request.safe_outcome is not None)
                    submitted = request._submitted
                    assert submitted is not None and submitted.stage is EnrollmentStage.REQUESTED
                    request.query_one("#automation-request-review", Button).press()
                    await _until(pilot, lambda: isinstance(pilot.app.screen, RuntimeAutomationInventoryScreen))
                    await pilot.pause()
                    inventory = pilot.app.screen
                    assert isinstance(inventory, RuntimeAutomationInventoryScreen)
                    assert inventory._client is human
                    await _until(pilot, lambda: inventory._inventory is not None and not inventory._busy)
                    current = inventory._inventory
                    assert current is not None
                    selected_index = next(
                        index
                        for index, item in enumerate(current.requests)
                        if item.receipt.request_id == submitted.request_id
                    )
                    table = inventory.query_one("#automation-inventory-requests", DataTable)
                    table.focus()
                    table.move_cursor(row=selected_index)
                    await _until(
                        pilot, lambda: not inventory.query_one("#automation-inventory-approve", Button).disabled
                    )
                    assert inventory._selected_review is current.requests[selected_index]
                    inventory.query_one("#automation-inventory-approve", Button).press()
                    await _until(pilot, lambda: isinstance(pilot.app.screen, RuntimeAutomationDecisionScreen))
                    await pilot.pause()
                    decision = pilot.app.screen
                    assert isinstance(decision, RuntimeAutomationDecisionScreen)
                    consent = str(decision.query_one("#automation-decision-review", Static).content)
                    assert str(submitted.request_id) in consent and submitted.review_digest in consent
                    password = decision.query_one("#automation-decision-password", Input)
                    assert password.password and password.value == ""
                    password.value = PROFILE_INPUT
                    decision.query_one("#automation-decision-confirm", Button).press()
                    await _until(pilot, lambda: decision.settled_outcome is not None and not decision._busy)
                    decision_outcome = decision.settled_outcome
                    assert decision_outcome is not None and decision_outcome.completed
                    assert password.value == "" and decision._pending_proof is None
                    decision.action_close()
                    await _until(pilot, lambda: pilot.app.screen is inventory)
                    inventory.action_close()
                    await _until(pilot, lambda: pilot.app.screen is request and request.safe_outcome is not None)
                    outcome = request.safe_outcome
                    assert outcome is not None and outcome.stage is EnrollmentStage.COMPLETE
                    assert not outcome.uncertain and outcome.request_id == submitted.request_id
                    assert outcome.credential_reference is not None
                    outcomes.append(outcome)
                    request.action_close()
                    await _until(pilot, lambda: pilot.app.screen is access and not access._busy)
                    access.action_close()

                await ScreenHostApp(access).run_async(headless=True, auto_pilot=drive)
            except BaseException as error:
                human_primary = error
                raise
            finally:
                await close_async_resources(human_owner, task_name="tui-reviewer-close", primary_error=human_primary)

        observations: list[RuntimeFailureObservation] = []

        def observe(observation: RuntimeFailureObservation) -> None:
            observations.append(observation)
            del observations[:-32]

        with (
            override_settings(cadrumo_local_storage_root=storage_root, cadrumo_output_language="en"),
            observe_native_runtime_failures(server, profiles, failure_observer=observe),
        ):
            runtime_owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=20)
            resources: list[AsyncCloseable] = [runtime_owner]
            primary: BaseException | None = None
            try:
                pool = ThreadPoolExecutor(max_workers=1)
                runtime_owner.executor = pool
                context = copy_context()

                def serve() -> None:
                    context.run(server.serve)

                runtime_owner.running = pool.submit(serve)
                runtime_owner.server = server
                assert server.ready.wait(3)
                asyncio.run(run_human_journey())
                assert len(outcomes) == 1
                outcome = outcomes[0]
                reference = outcome.credential_reference
                assert reference is not None and outcome.request_id is not None
                handle = NativeClientCredentialStore.resolve_reference(
                    credential_reference=reference, binding=subject.store.binding, secrets_store=subject.client_native
                )
                metadata = handle.metadata
                assert metadata.profile_id == profile_id and metadata.credential_reference == reference
                assert metadata.review_digest == outcome.review_digest
                api = asyncio.run(
                    open_installed_credential_client(
                        profile_id=profile_id,
                        credential_reference=reference,
                        frontend=OperationFrontendProjection.CLI,
                        secrets_store=subject.client_native,
                    )
                )
                resources.insert(0, RuntimeTransportCleanup(api))
                assert api.status().status.grant_valid

                def human_cli(*leaf: str) -> dict[str, Any]:
                    result = invoke_cached_cli(
                        (
                            "--format",
                            "json",
                            "--profile",
                            str(profile_id),
                            "--profile-secrets-stdin",
                            "config",
                            "profile",
                            "automation",
                            *leaf,
                        ),
                        input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
                    )
                    assert result.exit_code == 0, result.output
                    assert PROFILE_INPUT not in result.output
                    document = json.loads(result.stdout)
                    assert document["status"] in {"success", "warning"}
                    assert isinstance(document["result"], dict)
                    return document["result"]

                inspected = human_cli("inspect", str(outcome.request_id))
                receipt = inspected["review"]["receipt"]
                assert (
                    receipt["request_id"] == str(outcome.request_id)
                    and receipt["stage"] == EnrollmentStage.COMPLETE.value
                )
                assert receipt["grant_id"] == str(metadata.grant_id) and receipt["key_id"] == str(metadata.key_id)
                assert receipt["review_digest"] == outcome.review_digest
                denied = human_cli("deny", "key", str(metadata.key_id))
                assert denied["target_id"] == str(metadata.key_id) and denied["kind"] == "key"
                assert denied["receipt"]["access_denied"] is True
                try:
                    status = api.status()
                except RuntimeFrontendRefusedError:
                    pass
                else:
                    assert status.status.denial is not None
                with pytest.raises(RuntimeFrontendRefusedError) as stale:
                    asyncio.run(
                        open_installed_credential_client(
                            profile_id=profile_id,
                            credential_reference=reference,
                            frontend=OperationFrontendProjection.CLI,
                            secrets_store=subject.client_native,
                        )
                    )
                assert stale.value.reason in {
                    AccessDenialCode.GRANT_INACTIVE.value,
                    AccessDenialCode.KEY_INACTIVE.value,
                    AutomationCustodyCode.CREDENTIAL_REJECTED.value,
                }
            except BaseException as error:
                primary = error
                error.add_note("Sanitized runtime observations: " + repr(tuple(observations)))
                running = runtime_owner.running
                if running is not None and running.done() and not running.cancelled():
                    terminal_error = running.exception()
                    if terminal_error is not None:
                        error.add_note(repr(runtime_failure_observation("runtime_serve_terminal", terminal_error)))
                raise
            finally:
                asyncio.run(close_async_resources(*resources, task_name="tui-cli-parity-close", primary_error=primary))


def test_cli_created_requests_are_listed_reviewed_and_settled_by_tui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The TUI can review CLI-created enrollments and settle approval and decline."""

    async def _until(pilot: Pilot[object], predicate, *, timeout: float = 90) -> None:
        async with asyncio.timeout(timeout):
            while not predicate():
                await asyncio.sleep(0.05)

    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    installation = runtime_installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with (
        override_settings(cadrumo_profile_kdf_measure_calibration=False),
        administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
        ) as subject,
    ):
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        delete_profile_session(storage_root=storage_root, profile_id=profile_id)
        monkeypatch.setattr(
            runtime_automation_request, "installed_automation_secret_store", lambda: subject.client_native
        )
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=storage_root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: LoginObservation(owner_id(), login_id=f"tui-cli-review-{uuid4()}"),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        observations: list[RuntimeFailureObservation] = []

        def observe(observation: RuntimeFailureObservation) -> None:
            observations.append(observation)
            del observations[:-32]

        def invoke_create() -> Result:
            with override_settings(cadrumo_local_storage_root=storage_root, cadrumo_output_language="en"):
                return invoke_cached_cli(
                    (
                        "--format",
                        "json",
                        "--profile",
                        str(profile_id),
                        "config",
                        "profile",
                        "automation",
                        "create",
                        "--secrets-stdin",
                    ),
                    input=json.dumps({"proposal": subject.proposal.model_dump(mode="json")}),
                )

        def invoke_in_context(context: Context, operation: Callable[[], Result]) -> Result:
            return context.run(operation)

        def human_cli(*leaf: str) -> dict[str, Any]:
            result = invoke_cached_cli(
                (
                    "--format",
                    "json",
                    "--profile",
                    str(profile_id),
                    "--profile-secrets-stdin",
                    "config",
                    "profile",
                    "automation",
                    *leaf,
                ),
                input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
            )
            assert result.exit_code == 0, result.output
            assert PROFILE_INPUT not in result.output
            document = json.loads(result.stdout)
            assert document["status"] in {"success", "warning"}
            assert isinstance(document["result"], dict)
            return document["result"]

        with (
            override_settings(cadrumo_local_storage_root=storage_root, cadrumo_output_language="en"),
            observe_native_runtime_failures(server, profiles, failure_observer=observe),
        ):
            runtime_owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=20)
            runtime_pool = ThreadPoolExecutor(max_workers=1)
            runtime_owner.executor = runtime_pool
            cli_pool = ThreadPoolExecutor(max_workers=1)
            resources: list[AsyncCloseable] = [runtime_owner]
            primary: BaseException | None = None
            try:
                runtime_owner.running = runtime_pool.submit(server.serve)
                runtime_owner.server = server
                assert server.ready.wait(3)

                async def run_human_journey() -> tuple[dict[str, Any], dict[str, Any], frozenset[tuple[str, str]]]:
                    human = await open_installed_runtime_client(
                        profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    human_owner = RuntimeTransportCleanup(human)
                    human_primary: BaseException | None = None
                    try:
                        proof = bytearray(PROFILE_INPUT, "utf-8")
                        admitted = await asyncio.to_thread(human.login_password, proof)
                        assert not any(proof)
                        assert admitted.status.profile_id == profile_id and admitted.status.credential_authenticated
                        inventory = RuntimeAutomationInventoryScreen(human)
                        results: list[dict[str, Any]] = []
                        decline_store_before: frozenset[tuple[str, str]] | None = None

                        async def drive(pilot: Pilot[object]) -> None:
                            nonlocal decline_store_before
                            await _until(pilot, lambda: inventory._inventory is not None or inventory.access_lost)
                            assert not inventory.access_lost and not inventory._busy
                            for decision in ("approve", "decline"):
                                expected_stage = {
                                    "approve": EnrollmentStage.COMPLETE.value,
                                    "decline": EnrollmentStage.DECLINED.value,
                                }[decision]
                                before = {item.request_id for item in subject.store.enrollment_state().requests}
                                if decision == "decline":
                                    decline_store_before = frozenset(subject.client_native.items)
                                pending_cli: Future[Result] = cli_pool.submit(
                                    invoke_in_context, copy_context(), invoke_create
                                )
                                deadline = time.monotonic() + 30
                                while time.monotonic() < deadline:
                                    new_requests = tuple(
                                        item
                                        for item in subject.store.enrollment_state().requests
                                        if item.request_id not in before
                                    )
                                    if new_requests:
                                        break
                                    if pending_cli.done():
                                        pytest.fail(
                                            f"CLI create exited before its TUI review: {pending_cli.result()!r}"
                                        )
                                    await asyncio.sleep(0.05)
                                else:
                                    pytest.fail("CLI create did not publish a review for the TUI")
                                assert len(new_requests) == 1
                                request_id = new_requests[0].request_id

                                inventory.query_one("#automation-inventory-refresh", Button).press()
                                await _until(
                                    pilot,
                                    lambda request_id=request_id: (
                                        inventory.access_lost
                                        or (
                                            inventory._inventory is not None
                                            and not inventory._busy
                                            and any(
                                                item.receipt.request_id == request_id
                                                for item in inventory._inventory.requests
                                            )
                                        )
                                    ),
                                )
                                assert not inventory.access_lost
                                current = inventory._inventory
                                assert current is not None
                                review_index, review = next(
                                    (index, item)
                                    for index, item in enumerate(current.requests)
                                    if item.receipt.request_id == request_id
                                )
                                assert review.receipt.profile_id == profile_id
                                assert review.receipt.stage is EnrollmentStage.REQUESTED
                                request_table = inventory.query_one("#automation-inventory-requests", DataTable)
                                request_table.focus()
                                request_table.move_cursor(row=review_index)
                                await _until(pilot, lambda review=review: inventory._selected_review is review)
                                details = str(inventory.query_one("#automation-inventory-details", Static).content)
                                assert str(request_id) in details and review.receipt.review_digest in details

                                button_id = f"#automation-inventory-{decision}"
                                await _until(
                                    pilot,
                                    lambda button_id=button_id: not inventory.query_one(button_id, Button).disabled,
                                )
                                inventory.query_one(button_id, Button).press()
                                await _until(
                                    pilot,
                                    lambda: isinstance(pilot.app.screen, RuntimeAutomationDecisionScreen),
                                )
                                modal = pilot.app.screen
                                assert isinstance(modal, RuntimeAutomationDecisionScreen)
                                consent = str(modal.query_one("#automation-decision-review", Static).content)
                                assert str(request_id) in consent and review.receipt.review_digest in consent
                                if decision == "approve":
                                    approval_password = modal.query_one("#automation-decision-password", Input)
                                    assert approval_password.password and approval_password.value == ""
                                    approval_password.value = PROFILE_INPUT
                                else:
                                    assert not modal.query("#automation-decision-password")
                                modal.query_one("#automation-decision-confirm", Button).press()
                                await _until(
                                    pilot,
                                    lambda modal=modal: modal.settled_outcome is not None and not modal._busy,
                                )
                                settled = modal.settled_outcome
                                assert settled is not None and settled.completed and not settled.access_lost
                                if decision == "approve":
                                    wiped_password = modal.query_one("#automation-decision-password", Input)
                                    assert wiped_password.value == "" and modal._pending_proof is None
                                modal.action_close()
                                await _until(
                                    pilot,
                                    lambda: pilot.app.screen is inventory and inventory._inventory is None,
                                )
                                result = await asyncio.to_thread(pending_cli.result, 45)
                                assert result.exit_code == 0, result.output
                                assert PROFILE_INPUT not in result.output and '"proposal"' not in result.stdout
                                envelope = json.loads(result.stdout)
                                assert envelope["command"] == "config.profile.automation.create"
                                create_result = envelope["result"]
                                assert create_result["profile_id"] == "<profile-id>"
                                assert create_result["submitted"]["request_id"] == str(request_id)
                                assert create_result["terminal"]["request_id"] == str(request_id)
                                assert create_result["terminal"]["stage"] == expected_stage
                                results.append(create_result)

                            inventory.query_one("#automation-inventory-refresh", Button).press()
                            await _until(
                                pilot,
                                lambda: (
                                    inventory.access_lost or (inventory._inventory is not None and not inventory._busy)
                                ),
                            )
                            assert not inventory.access_lost
                            final = inventory._inventory
                            assert final is not None
                            assert len(final.grants) == len(final.keys) == 1
                            assert final.grants[0].state.value == final.keys[0].state.value == "active"
                            assert final.grants[0].grant_id == UUID(results[0]["terminal"]["grant_id"])
                            assert final.keys[0].key_id == UUID(results[0]["terminal"]["key_id"])
                            expected_requests = {
                                UUID(item["terminal"]["request_id"]): item["terminal"]["stage"] for item in results
                            }
                            final_requests = {item.receipt.request_id: item for item in final.requests}
                            assert set(expected_requests) <= set(final_requests)
                            for request_id, stage in expected_requests.items():
                                review = final_requests[request_id]
                                assert review.receipt.stage.value == stage
                                table = inventory.query_one("#automation-inventory-requests", DataTable)
                                table.focus()
                                table.move_cursor(row=tuple(final.requests).index(review))
                                await _until(pilot, lambda review=review: inventory._selected_review is review)
                                details = str(inventory.query_one("#automation-inventory-details", Static).content)
                                assert str(request_id) in details and review.receipt.review_digest in details
                            inventory.action_close()

                        await ScreenHostApp(inventory).run_async(headless=True, auto_pilot=drive)
                        assert len(results) == 2 and decline_store_before is not None
                        return results[0], results[1], decline_store_before
                    except BaseException as error:
                        human_primary = error
                        raise
                    finally:
                        await close_async_resources(
                            human_owner, task_name="cli-to-tui-review-close", primary_error=human_primary
                        )

                approved_result, declined_result, decline_store_before = asyncio.run(run_human_journey())
                approved_reference = approved_result["credential_reference"]
                assert isinstance(approved_reference, str)
                assert approved_result["terminal"]["credential_reference"] == approved_reference
                assert declined_result["credential_reference"] is None
                assert declined_result["terminal"]["credential_reference"] is None
                assert frozenset(subject.client_native.items) == decline_store_before
                assert (CLIENT_NAMESPACE, approved_reference) in decline_store_before
                assert len(tuple(item for item in decline_store_before if item[0] == CLIENT_NAMESPACE)) == 1

                approved_request_id = UUID(approved_result["terminal"]["request_id"])
                declined_request_id = UUID(declined_result["terminal"]["request_id"])
                approved_inspection = human_cli("inspect", str(approved_request_id))["review"]
                declined_inspection = human_cli("inspect", str(declined_request_id))["review"]
                assert approved_inspection["receipt"]["stage"] == EnrollmentStage.COMPLETE.value
                assert declined_inspection["receipt"]["stage"] == EnrollmentStage.DECLINED.value
                assert approved_inspection["receipt"]["key_id"] == approved_result["terminal"]["key_id"]
                assert declined_inspection["receipt"]["key_id"] is None
                listed = human_cli("list")["inventory"]
                assert len(listed["grants"]) == len(listed["keys"]) == 1
                assert listed["grants"][0]["grant_id"] == approved_result["terminal"]["grant_id"]
                assert listed["keys"][0]["key_id"] == approved_result["terminal"]["key_id"]
                assert listed["grants"][0]["state"] == listed["keys"][0]["state"] == "active"
                listed_requests = {item["receipt"]["request_id"]: item for item in listed["requests"]}
                assert listed_requests[str(approved_request_id)]["receipt"]["stage"] == EnrollmentStage.COMPLETE.value
                assert listed_requests[str(declined_request_id)]["receipt"]["stage"] == EnrollmentStage.DECLINED.value

                reference = UUID(approved_reference)
                handle = NativeClientCredentialStore.resolve_reference(
                    credential_reference=reference,
                    binding=subject.store.binding,
                    secrets_store=subject.client_native,
                )
                assert handle.metadata.profile_id == profile_id
                assert handle.metadata.credential_reference == reference
                api = asyncio.run(
                    open_installed_credential_client(
                        profile_id=profile_id,
                        credential_reference=reference,
                        frontend=OperationFrontendProjection.CLI,
                        secrets_store=subject.client_native,
                    )
                )
                try:
                    assert api.status().status.grant_valid
                finally:
                    asyncio.run(close_async_resources(RuntimeTransportCleanup(api), task_name="approved-cli-close"))
            except BaseException as error:
                primary = error
                error.add_note("Sanitized runtime observations: " + repr(tuple(observations)))
                raise
            finally:
                try:
                    asyncio.run(
                        close_async_resources(*resources, task_name="cli-to-tui-parity-close", primary_error=primary)
                    )
                finally:
                    cli_pool.shutdown(wait=True, cancel_futures=True)
