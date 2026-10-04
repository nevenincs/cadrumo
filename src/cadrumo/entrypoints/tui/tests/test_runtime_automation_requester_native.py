"""Installed TUI first enrollment uses a separate human review and native delivery."""

from __future__ import annotations

import asyncio
import sys
import traceback
from collections.abc import Callable, Coroutine
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import timedelta
from functools import partial
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import SecretBytes
from textual.pilot import Pilot
from textual.widgets import Button, Checkbox, Input, Select, SelectionList, Static

from cadrumo.adapters.local_runtime import runtime_credentials
from cadrumo.adapters.local_runtime.automation_decision import run_automation_decision
from cadrumo.adapters.local_runtime.automation_inventory import read_automation_inventory
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.runtime_client import open_installed_runtime_client
from cadrumo.adapters.local_runtime.runtime_credentials import open_installed_credential_client
from cadrumo.adapters.local_runtime.runtime_transport_cleanup import RuntimeTransportCleanup
from cadrumo.adapters.local_runtime.tests.profile_worker_support import NativeRuntimeFixtureOwner, owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode
from cadrumo.application.runtime.worker_authorization import WorkerAuthorizationRequest
from cadrumo.application.runtime.worker_enrollment import WorkerApprovalPublication, WorkerApprovalRequest
from cadrumo.application.user_profile.access_contracts import (
    KEY_ROTATION_MAXIMUM_OVERLAP,
    AccessAction,
    AccessScope,
    ApiKeyRecord,
    AuthorityState,
    AutomationGrant,
    Availability,
    LoginEligibility,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.automation_enrollment import (
    EnrollmentKind,
    EnrollmentStage,
    EnrollmentTransition,
)
from cadrumo.core.async_cleanup import AsyncCloseable, await_cancellation_complete, close_async_resources
from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import tr
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.runtime.profile_host import RuntimeProfileHost
from cadrumo.entrypoints.tui import installed_session
from cadrumo.entrypoints.tui.components.status import PinnedStatusBar
from cadrumo.entrypoints.tui.launcher import main
from cadrumo.entrypoints.tui.runtime_session import RuntimeRestrictedSessionApp
from cadrumo.entrypoints.tui.secret.automation_requester import RuntimeAutomationRequesterScreen
from cadrumo.entrypoints.tui.secret.automation_requester_contracts import AutomationRequestOutcome
from cadrumo.entrypoints.tui.secret.runtime_login import RuntimeLoginScreen
from cadrumo.entrypoints.tui.secret.runtime_login_contracts import RuntimeLoginMethod

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "tui-requester-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            locked=False,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


async def _until(pilot: Pilot[object], predicate, *, timeout: float = 90) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.05)


def test_prelogin_tui_request_delivers_only_to_client_after_separate_human_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No login or local custody is inherited by the requesting TUI screen."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    installation = runtime_installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()
        delete_profile_session(storage_root=storage_root, profile_id=profile_id)
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=storage_root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        monkeypatch.setattr(installed_session, "installed_automation_secret_store", lambda: subject.client_native)
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: subject.client_native)
        monkeypatch.setattr(
            installed_session,
            "RuntimeAutomationRequesterScreen",
            partial(RuntimeAutomationRequesterScreen, journey_timeout=30),
        )
        approval_stage = ["not_started"]
        approval_failed_stage = ["none"]
        approval_updated = [False]
        approval_client_closed = [False]
        approval_failures: list[tuple[str, str, tuple[str, ...]]] = []
        original_phase = RuntimeProfileHost.approval_phase
        original_publication = RuntimeProfileHost.approval_publication

        def record_failure(phase: str, error: AutomationCustodyError) -> None:
            locations = tuple(
                f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
                for frame in traceback.extract_tb(error.__traceback__)
            )
            approval_failures.append((phase, error.reason.value, locations))
            del approval_failures[:-32]

        def observe_phase(
            host: RuntimeProfileHost, request: WorkerApprovalRequest, password: SecretBytes | None
        ) -> bool | None:
            try:
                return original_phase(host, request, password)
            except AutomationCustodyError as error:
                record_failure(f"approval_phase.{request.phase}", error)
                raise

        def observe_publication(
            host: RuntimeProfileHost, authority: WorkerAuthorizationRequest, command: WorkerApprovalPublication
        ) -> EnrollmentTransition | None:
            try:
                return original_publication(host, authority, command)
            except AutomationCustodyError as error:
                record_failure(f"approval_publication.{command.phase}", error)
                raise

        monkeypatch.setattr(RuntimeProfileHost, "approval_phase", observe_phase)
        monkeypatch.setattr(RuntimeProfileHost, "approval_publication", observe_publication)

        def annotate_approval_error(error: BaseException, outcome: AutomationRequestOutcome | None) -> None:
            safe_codes = {code.value for code in RuntimeRefusalCode} | {code.value for code in AutomationCustodyCode}
            reason = outcome.reason if outcome is not None and outcome.reason in safe_codes else "unreported"
            error.add_note(
                f"Approval terminal failure: failed_stage={approval_failed_stage[0]}, "
                f"stage={approval_stage[0]}, decision_updated={approval_updated[0]}, "
                f"client_closed={approval_client_closed[0]}, "
                f"outcome_stage={None if outcome is None or outcome.stage is None else outcome.stage.value}, "
                f"outcome_uncertain={None if outcome is None else outcome.uncertain}, "
                f"outcome_reason={reason}, phase_failures={tuple(approval_failures)!r}"
            )

        def approve(request_id: UUID) -> None:
            approval_stage[0] = "opening"
            human = asyncio.run(
                open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
            )
            human_owner = RuntimeTransportCleanup(human)
            primary: BaseException | None = None
            try:
                approval_stage[0] = "login"
                proof = bytearray(PROFILE_INPUT.encode())
                human.login_password(proof)
                assert proof == bytes(len(proof))
                approval_stage[0] = "inventory"
                inventory = read_automation_inventory(human).projection
                review = next(item for item in inventory.requests if item.receipt.request_id == request_id)
                approval_stage[0] = "decision"
                fresh = bytearray(PROFILE_INPUT.encode())
                completed = run_automation_decision(human, review, decision="approve", password=fresh)
                assert fresh == bytes(len(fresh))
                assert completed.effect.value == "updated"
                approval_updated[0] = completed.effect.value == "updated"
            except BaseException as error:
                approval_failed_stage[0] = approval_stage[0]
                primary = error
                raise
            finally:
                approval_stage[0] = "closing"
                asyncio.run(
                    close_async_resources(human_owner, task_name="tui-approval-human-close", primary_error=primary)
                )
                approval_client_closed[0] = human_owner.released
                approval_stage[0] = "done"

        with override_settings(cadrumo_local_storage_root=storage_root):
            runtime_owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=20)
            resources: list[AsyncCloseable] = [runtime_owner]
            primary: BaseException | None = None
            try:
                pool = ThreadPoolExecutor(max_workers=3)
                runtime_owner.executor = pool
                context = copy_context()

                def serve() -> None:
                    context.run(server.serve)

                runtime_owner.running = pool.submit(serve)
                runtime_owner.server = server
                assert server.ready.wait(3)

                async def drive(pilot: Pilot[object]) -> None:
                    login = pilot.app.screen
                    assert isinstance(login, RuntimeLoginScreen)
                    await pilot.click("#runtime-login-request-access")
                    await _until(pilot, lambda: isinstance(pilot.app.screen, RuntimeAutomationRequesterScreen))
                    request = pilot.app.screen
                    assert isinstance(request, RuntimeAutomationRequesterScreen)
                    assert request._client is None
                    cast_operations = request.query_one("#automation-request-operations", SelectionList)
                    cast_operations.select("user-profile.view")
                    request.query_one("#automation-request-actions", SelectionList).select("observe")
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
                    await _until(pilot, lambda: request._submitted is not None)
                    submitted = request._submitted
                    assert submitted is not None and submitted.stage is EnrollmentStage.REQUESTED
                    assert submitted.profile_id == profile_id
                    approval = pool.submit(copy_context().run, approve, submitted.request_id)
                    runtime_owner.auxiliary.append(approval)
                    await _until(pilot, lambda: request._outcome is not None or approval.done(), timeout=30)
                    if approval.done():
                        approval_error = await await_cancellation_complete(
                            asyncio.to_thread(approval.exception, timeout=0), task_name="tui-approval-result"
                        )
                        if approval_error is not None:
                            annotate_approval_error(approval_error, request._outcome)
                            raise approval_error
                    if request._outcome is None:
                        await _until(pilot, lambda: request._outcome is not None, timeout=30)
                    try:
                        approval_error = await await_cancellation_complete(
                            asyncio.to_thread(approval.exception, timeout=10), task_name="tui-approval-result"
                        )
                    except TimeoutError as error:
                        annotate_approval_error(error, request._outcome)
                        error.add_note(
                            f"Approval thread did not settle: stage={approval_stage[0]}, "
                            f"decision_updated={approval_updated[0]}, client_closed={approval_client_closed[0]}, "
                            f"outcome_arrived={request._outcome is not None}, "
                            f"future_done={approval.done()}, future_cancelled={approval.cancelled()}"
                        )
                        raise
                    if approval_error is not None:
                        annotate_approval_error(approval_error, request._outcome)
                        raise approval_error
                    outcome = request._outcome
                    assert outcome is not None and outcome.stage is EnrollmentStage.COMPLETE
                    assert not outcome.uncertain
                    assert outcome.request_id == submitted.request_id
                    assert outcome.credential_reference is not None
                    request.action_close()
                    await _until(pilot, lambda: pilot.app.screen is login)
                    login.action_abandon()

                assert main(headless=True, auto_pilot=drive) == 0
                assert len(subject.store.snapshot().grants) == len(subject.store.snapshot().keys) == 1
                reference = next(iter(subject.client_native.items))[1]
                assert (CLIENT_NAMESPACE, reference) in subject.client_native.items
                fresh_api = asyncio.run(
                    open_installed_credential_client(
                        profile_id=profile_id,
                        credential_reference=UUID(reference),
                        frontend=OperationFrontendProjection.TUI,
                        secrets_store=subject.client_native,
                    )
                )
                fresh_api_owner = RuntimeTransportCleanup(fresh_api)
                resources.insert(0, fresh_api_owner)
                client_primary: BaseException | None = None
                try:
                    assert fresh_api.status().status.grant_valid
                except BaseException as error:
                    client_primary = error
                    raise
                finally:
                    asyncio.run(
                        close_async_resources(
                            fresh_api_owner, task_name="tui-requester-api-close", primary_error=client_primary
                        )
                    )
            except BaseException as error:
                primary = error
                raise
            finally:
                asyncio.run(
                    close_async_resources(*resources, task_name="tui-requester-native-close", primary_error=primary)
                )


def test_restricted_tui_reviews_renew_rotation_and_scope_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each typed own-grant change needs a separate human and a fresh client proof."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    installation = runtime_installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        scope = AccessScope(
            operations=frozenset({"user-profile.field-mutation"}),
            actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.RESULT, AccessAction.COMMIT}),
            disclosures=frozenset(),
            periods=None,
            allow_period_independent=True,
            allow_delegation=False,
        )
        enrollment_id = uuid4()
        subject.service.request(enrollment_id, changed(subject.proposal, scope=scope))
        original = subject.approve(enrollment_id)
        assert original.credential_reference is not None and original.key_id is not None
        profile_id = subject.store.binding.profile_id
        reference = original.credential_reference
        close_active_bucket_session()
        delete_profile_session(storage_root=storage_root, profile_id=profile_id)
        stop, boot = Event(), uuid4()
        profiles = RuntimeProfileConnections(
            storage_root=storage_root,
            storage_identity=endpoint.storage_identity,
            runtime_boot_id=boot,
            stop=stop,
            capture_login=lambda _channel: _LoginObservation(),
            secret_store=lambda: subject.native,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        monkeypatch.setattr(installed_session, "installed_automation_secret_store", lambda: subject.client_native)
        monkeypatch.setattr(runtime_credentials, "installed_automation_secret_store", lambda: subject.client_native)
        monkeypatch.setattr(
            installed_session,
            "RuntimeAutomationRequesterScreen",
            partial(RuntimeAutomationRequesterScreen, journey_timeout=45),
        )

        def approve(request_id: UUID) -> None:
            human = asyncio.run(
                open_installed_runtime_client(profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
            )
            human_owner = RuntimeTransportCleanup(human)
            primary: BaseException | None = None
            try:
                password = bytearray(PROFILE_INPUT.encode())
                human.login_password(password)
                assert password == bytes(len(password))
                inventory = read_automation_inventory(human).projection
                review = next(item for item in inventory.requests if item.receipt.request_id == request_id)
                fresh = bytearray(PROFILE_INPUT.encode())
                result = run_automation_decision(human, review, decision="approve", password=fresh)
                assert fresh == bytes(len(fresh))
                assert result.effect.value == "updated"
            except BaseException as error:
                primary = error
                raise
            finally:
                asyncio.run(
                    close_async_resources(human_owner, task_name="tui-approval-human-close", primary_error=primary)
                )

        with override_settings(cadrumo_local_storage_root=storage_root):
            runtime_owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=20)
            resources: list[AsyncCloseable] = [runtime_owner]
            primary: BaseException | None = None
            try:
                pool = ThreadPoolExecutor(max_workers=3)
                runtime_owner.executor = pool
                context = copy_context()

                def serve() -> None:
                    context.run(server.serve)

                runtime_owner.running = pool.submit(serve)
                runtime_owner.server = server
                assert server.ready.wait(3)
                admitted = subject.store.snapshot()
                assert admitted.grants[0].state is AuthorityState.ACTIVE
                assert admitted.grants[0].unattended
                assert AccessAction.COMMIT in admitted.grants[0].scope.actions
                assert any(
                    key.key_id == original.key_id and key.state is AuthorityState.ACTIVE for key in admitted.keys
                )
                assert (CLIENT_NAMESPACE, str(reference)) in subject.client_native.items
                probe = asyncio.run(
                    open_installed_credential_client(
                        profile_id=profile_id,
                        credential_reference=reference,
                        frontend=OperationFrontendProjection.TUI,
                        secrets_store=subject.client_native,
                    )
                )
                probe_owner = RuntimeTransportCleanup(probe)
                resources.insert(0, probe_owner)
                client_primary: BaseException | None = None
                try:
                    assert probe.status().status.grant_valid
                except BaseException as error:
                    client_primary = error
                    raise
                finally:
                    asyncio.run(
                        close_async_resources(
                            probe_owner, task_name="tui-requester-api-close", primary_error=client_primary
                        )
                    )
                for kind in (EnrollmentKind.RENEW, EnrollmentKind.ROTATE, EnrollmentKind.CHANGE_SCOPE):
                    before = subject.store.snapshot()
                    grant = before.grants[0]
                    current_key = next(key for key in before.keys if key.state is AuthorityState.ACTIVE)
                    prior_reference = reference
                    outcome_holder: list[AutomationRequestOutcome] = []

                    def drive_for(
                        selected_kind: EnrollmentKind,
                        selected_grant: AutomationGrant,
                        selected_key: ApiKeyRecord,
                        selected_reference: UUID,
                        outcomes: list[AutomationRequestOutcome],
                    ) -> Callable[[Pilot[object]], Coroutine[Any, Any, None]]:
                        async def drive(pilot: Pilot[object]) -> None:
                            login = pilot.app.screen
                            if isinstance(login, RuntimeLoginScreen):
                                if outcomes:
                                    login.action_abandon()
                                    return
                                selection = login.query_one("#runtime-login-method", Select)
                                selection.value = RuntimeLoginMethod.API_REFERENCE
                                await pilot.pause()
                                credential = login.query_one("#runtime-login-credential", Input)
                                assert credential.password and credential.value == "" and not credential.display
                                login.query_one("#runtime-login-reference", Input).value = str(selected_reference)
                                await pilot.click("#runtime-login-submit")
                                await _until(pilot, lambda: not login._busy, timeout=20)
                                if not login._transferred:
                                    status = login.query_one("#runtime-login-status", PinnedStatusBar)
                                    raise AssertionError(f"API reference login did not hand off: {status.message}")
                                return
                            app = pilot.app
                            assert isinstance(app, RuntimeRestrictedSessionApp)
                            await _until(
                                pilot,
                                lambda: str(profile_id) in str(app.query_one("#restricted-profile", Static).render()),
                                timeout=20,
                            )
                            request_button = app.query_one("#restricted-request-access", Button)
                            clicked = await pilot.click("#restricted-request-access")
                            if not clicked:
                                raise AssertionError(
                                    f"Restricted requester button was not clicked: kind={selected_kind.value}, "
                                    f"disabled={request_button.disabled}, cleared={app._cleared}, locking={app._locking}"
                                )
                            try:
                                await _until(
                                    pilot, lambda: isinstance(app.screen, RuntimeAutomationRequesterScreen), timeout=10
                                )
                            except TimeoutError as error:
                                availability = app.query_one("#restricted-availability", Static)
                                invalid = str(availability.render()) == tr("tui.automation_request.invalid")
                                error.add_note(
                                    f"Restricted requester did not open: kind={selected_kind.value}, clicked={clicked}, "
                                    f"disabled={request_button.disabled}, cleared={app._cleared}, locking={app._locking}, "
                                    f"screen_type={type(app.screen).__name__}, invalid_availability={invalid}"
                                )
                                raise
                            request = app.screen
                            assert isinstance(request, RuntimeAutomationRequesterScreen)
                            assert request._client is not None
                            assert request._client.profile_id == profile_id
                            assert request._client.frontend is OperationFrontendProjection.TUI
                            request.query_one("#automation-request-kind", Select).value = selected_kind
                            await asyncio.sleep(0.05)
                            operation = "user-profile.field-mutation"
                            request.query_one("#automation-request-operations", SelectionList).select(operation)
                            chosen_actions = (
                                selected_grant.scope.actions - {AccessAction.RESULT}
                                if selected_kind is EnrollmentKind.CHANGE_SCOPE
                                else selected_grant.scope.actions
                            )
                            for action in chosen_actions:
                                request.query_one("#automation-request-actions", SelectionList).select(action.value)
                            request.query_one("#automation-request-period-mode", Select).value = "all"
                            request.query_one("#automation-request-independent", Checkbox).value = True
                            request.query_one("#automation-request-unattended", Checkbox).value = True
                            expiry = (
                                selected_grant.expires_at + timedelta(days=30)
                                if selected_kind is EnrollmentKind.RENEW
                                else selected_grant.expires_at
                            )
                            request.query_one("#automation-request-expiry", Input).value = expiry.isoformat()
                            request.query_one("#automation-request-grant", Input).value = str(selected_grant.grant_id)
                            request.query_one("#automation-request-reference", Input).value = str(selected_reference)
                            if selected_kind is EnrollmentKind.ROTATE:
                                request.query_one("#automation-request-key", Input).value = str(selected_key.key_id)
                                request.query_one("#automation-request-key-expiry", Input).value = (
                                    now() + timedelta(days=15)
                                ).isoformat()
                            draft = request._draft()
                            typed = draft.proposal(uuid4())
                            assert typed.kind is selected_kind
                            assert typed.scope.actions == chosen_actions
                            assert typed.target_grant_id == selected_grant.grant_id
                            if selected_kind in {EnrollmentKind.RENEW, EnrollmentKind.ROTATE}:
                                assert typed.scope == selected_grant.scope
                            if selected_kind is EnrollmentKind.RENEW:
                                assert typed.expires_at > selected_grant.expires_at
                            assert draft.credential_reference == selected_reference
                            request.query_one("#automation-request-submit", Button).press()
                            await asyncio.sleep(0.1)
                            if not request._busy and request._submitted is None:
                                status = request.query_one("#automation-request-status", Static)
                                raise AssertionError(f"request refused before submit: {status.render()}")
                            await _until(
                                pilot,
                                lambda: request._submitted is not None or request._outcome is not None,
                                timeout=20,
                            )
                            if request._submitted is None:
                                status = request.query_one("#automation-request-status", Static)
                                outcome = request._outcome
                                raise AssertionError(
                                    f"request did not submit: {status.render()}; "
                                    f"safe reason={None if outcome is None else outcome.reason}"
                                )
                            submitted = request._submitted
                            assert submitted is not None and submitted.stage is EnrollmentStage.REQUESTED
                            approval = pool.submit(copy_context().run, approve, submitted.request_id)
                            runtime_owner.auxiliary.append(approval)
                            await _until(pilot, lambda: request._outcome is not None or approval.done(), timeout=45)
                            if approval.done():
                                approval_error = await await_cancellation_complete(
                                    asyncio.to_thread(approval.exception, timeout=0), task_name="tui-approval-result"
                                )
                                if approval_error is not None:
                                    raise approval_error
                            if request._outcome is None:
                                await _until(pilot, lambda: request._outcome is not None, timeout=45)
                            approval_error = await await_cancellation_complete(
                                asyncio.to_thread(approval.exception, timeout=10), task_name="tui-approval-result"
                            )
                            if approval_error is not None:
                                raise approval_error
                            outcome = request._outcome
                            assert outcome is not None and outcome.stage is EnrollmentStage.COMPLETE
                            assert not outcome.uncertain and outcome.request_id == submitted.request_id
                            if selected_kind is not EnrollmentKind.ROTATE:
                                try:
                                    source_status = await asyncio.to_thread(request._client.status)
                                except RuntimeFrontendRefusedError:
                                    pass
                                else:
                                    assert source_status.status.denial is not None
                            assert PROFILE_INPUT not in str(
                                request.query_one("#automation-request-status", Static).render()
                            )
                            outcomes.append(outcome)
                            request.action_close()
                            if app.is_running:
                                await _until(pilot, lambda: app.screen is app or not app.is_running, timeout=5)
                                if app.is_running:
                                    app.action_leave()

                        return drive

                    assert (
                        main(
                            headless=True,
                            auto_pilot=drive_for(kind, grant, current_key, prior_reference, outcome_holder),
                        )
                        == 0
                    )
                    assert len(outcome_holder) == 1
                    result = outcome_holder[0]
                    after = subject.store.snapshot()
                    assert after.grants[0].grant_id == grant.grant_id
                    assert after.grants[0].state is AuthorityState.ACTIVE
                    assert AccessAction.COMMIT in after.grants[0].scope.actions
                    if kind in {EnrollmentKind.RENEW, EnrollmentKind.ROTATE}:
                        assert after.grants[0].scope == grant.scope
                    else:
                        assert after.grants[0].scope.actions == grant.scope.actions - {AccessAction.RESULT}
                    if kind is EnrollmentKind.ROTATE:
                        assert result.credential_reference is not None
                        assert result.credential_reference != prior_reference
                        reference = result.credential_reference
                        predecessor = next(key for key in after.keys if key.key_id == current_key.key_id)
                        assert predecessor.expires_at <= now() + KEY_ROTATION_MAXIMUM_OVERLAP
                        successor = next(key for key in after.keys if key.key_id != current_key.key_id)
                        assert successor.state is AuthorityState.ACTIVE
                        assert (CLIENT_NAMESPACE, str(reference)) in subject.client_native.items
                    else:
                        assert result.credential_reference is None
                        assert reference == prior_reference
                        assert after.grants[0].generation == grant.generation + 1
                    fresh_api = asyncio.run(
                        open_installed_credential_client(
                            profile_id=profile_id,
                            credential_reference=reference,
                            frontend=OperationFrontendProjection.TUI,
                            secrets_store=subject.client_native,
                        )
                    )
                    fresh_api_owner = RuntimeTransportCleanup(fresh_api)
                    resources.insert(0, fresh_api_owner)
                    client_primary: BaseException | None = None
                    try:
                        assert fresh_api.status().status.grant_valid
                    except BaseException as error:
                        client_primary = error
                        raise
                    finally:
                        asyncio.run(
                            close_async_resources(
                                fresh_api_owner, task_name="tui-requester-api-close", primary_error=client_primary
                            )
                        )
            except BaseException as error:
                primary = error
                raise
            finally:
                asyncio.run(
                    close_async_resources(*resources, task_name="tui-requester-native-close", primary_error=primary)
                )
