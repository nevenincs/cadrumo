"""Native TUI and CLI parity for grant changes, revocation and profile recovery."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from click.testing import Result
from textual.app import AutopilotCallbackType
from textual.pilot import Pilot
from textual.widgets import Button, Checkbox, Input, Select, SelectionList, Static

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_native_identity import CLIENT_NAMESPACE
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.auth.auth_read_contracts import (
    AUTH_READ_OPERATION_DEFINITION_ID,
    AUTH_READ_RESULT_SCHEMA_ID,
    AuthReadProjection,
    AuthReadRequest,
)
from cadrumo.application.operations.frontend_requests import (
    OPERATION_OBSERVATION_PROJECTION_ID,
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.user_profile.access_contracts import (
    KEY_ROTATION_MAXIMUM_OVERLAP,
    ApiKeyRecord,
    AutomationGrant,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.application.user_profile.automation_enrollment import EnrollmentStage
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.i18n.render import tr
from cadrumo.core.json_contract import SchemaEnvelope
from cadrumo.core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from cadrumo.core.time.clock import now
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_typer_app
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.components.status import PinnedStatusBar
from cadrumo_client.commands.access_management_payloads import ConfigProfileAutomationInspectResult
from cadrumo_client.commands.compiler import build_command_app
from cadrumo_client.commands.registered_operation import run_registered_operation
from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import (
    AccessAction,
    AccessScope,
    AuthorityState,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
)
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode
from cadrumo_client.contracts.automation_lifecycle import AutomationResumeReceipt
from cadrumo_client.contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
from cadrumo_client.contracts.enrollment_proposal import EnrollmentKind
from cadrumo_client.contracts.operation_access import OperationObserve, OperationObserved
from cadrumo_client.contracts.projection_pages import PROJECTION_PAGE_BYTES, ProjectionPage, ProjectionPageRequest
from cadrumo_client.transport import credentials
from cadrumo_client.transport.automation_decision import run_automation_decision
from cadrumo_client.transport.automation_inventory import read_automation_inventory
from cadrumo_client.transport.credentials import open_installed_credential_client
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.frontend_client_contracts import FrontendRefusedError
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.installed_client import open_installed_client
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.tests.profile_worker_support import NativeRuntimeFixtureOwner, owner_id
from cadrumo_runtime.adapters.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH
from cadrumo_runtime.commands.lifecycle import dispatch_runtime_behavior
from cadrumo_runtime.host.frontend.tui import installed_session
from cadrumo_runtime.host.frontend.tui.launcher import main
from cadrumo_runtime.host.frontend.tui.runtime_access_management import RuntimeAccessManagementScreen
from cadrumo_runtime.host.frontend.tui.runtime_session import RuntimeRestrictedSessionApp
from cadrumo_runtime.host.frontend.tui.secret.automation_requester import RuntimeAutomationRequesterScreen
from cadrumo_runtime.host.frontend.tui.secret.automation_requester_contracts import AutomationRequestOutcome
from cadrumo_runtime.host.frontend.tui.secret.runtime_login import RuntimeLoginScreen
from cadrumo_runtime.host.frontend.tui.secret.runtime_login_contracts import RuntimeLoginMethod
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]


class _LoginObservation:
    login_id = "tui-cli-grant-lock-parity-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


async def _until[PilotResult](pilot: Pilot[PilotResult], predicate: Callable[[], bool], *, timeout: float = 90) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.05)


def _grant_scope() -> AccessScope:
    """Keep native parity grants narrow to the one operation under review."""
    return AccessScope(
        operations=frozenset({"user-profile.field-mutation"}),
        actions=frozenset({AccessAction.SUBMIT, AccessAction.START, AccessAction.RESULT, AccessAction.COMMIT}),
        disclosures=frozenset(),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _cli_inspect(profile_id: UUID, request_id: UUID) -> ConfigProfileAutomationInspectResult:
    result: Result = invoke_typer_app(
        build_command_app(RUNTIME_COMMAND_GRAPH, dispatcher=dispatch_runtime_behavior),
        (
            "--format",
            "json",
            "--profile",
            str(profile_id),
            "--profile-secrets-stdin",
            "config",
            "profile",
            "automation",
            "inspect",
            str(request_id),
        ),
        input=json.dumps({"profile_passphrase": PROFILE_INPUT}),
    )
    assert result.exit_code == 0, result.output
    assert PROFILE_INPUT not in result.output
    envelope = SchemaEnvelope[ConfigProfileAutomationInspectResult].model_validate_json(result.stdout)
    assert envelope.command == "config.profile.automation.inspect"
    return envelope.result


def _connect_cli(profile_id: UUID, reference: UUID, secret_store: AutomationSecretStore) -> FrontendClient:
    return asyncio.run(
        open_installed_credential_client(
            profile_id=profile_id,
            credential_reference=reference,
            frontend=OperationFrontendProjection.CLI,
            secrets_store=secret_store,
        )
    )


def _assert_fenced(client: FrontendClient) -> None:
    try:
        reply = client.status()
    except FrontendRefusedError:
        return
    assert reply.status.denial is not None


def _assert_cli_refused(profile_id: UUID, reference: UUID, secret_store: AutomationSecretStore) -> None:
    try:
        client = _connect_cli(profile_id, reference, secret_store)
    except FrontendRefusedError as error:
        assert error.reason in {
            AccessDenialCode.GRANT_INACTIVE.value,
            AccessDenialCode.KEY_INACTIVE.value,
            AccessDenialCode.PROFILE_LOCKED.value,
            AccessDenialCode.AUTOMATION_SUSPENDED.value,
            AutomationCustodyCode.CREDENTIAL_REJECTED.value,
        }
        return
    client.close()
    raise AssertionError("revoked or suspended grant admitted a fresh CLI credential connection")


@dataclass(frozen=True)
class _ReleasedAuthRead:
    """The completed auth read and the exact released document later grant revisions are held to."""

    completion: Any
    result_reference: OperationResultProjectionRequestV1
    typed_result: OperationResultProjectionSuccessV1[AuthReadProjection]
    expected_document: bytes
    expected_digest: str


def _assert_first_page(page: ProjectionPage, released: _ReleasedAuthRead) -> None:
    assert page.offset == 0
    assert page.document_digest == released.expected_digest
    assert page.total_bytes == len(released.expected_document)
    assert page.decode()
    assert page.decode() == released.expected_document[:PROJECTION_PAGE_BYTES]


def _read_released_auth_result(result_client: FrontendClient, profile_id: UUID) -> _ReleasedAuthRead:
    assert result_client.status().status.grant_valid
    completion = run_registered_operation(
        result_client,
        AuthReadRequest(profile_id=profile_id, kind="status"),
        definition_id=AUTH_READ_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=AuthReadProjection,
        request_version=1,
        result_version=1,
        timeout=60,
    )
    assert completion.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert completion.effect is OperationEffect.NONE
    assert completion.projection.profile_id == profile_id
    assert completion.projection.kind == "status" and completion.projection.status is not None
    deadline = time.monotonic() + 10
    contract = result_client.contract(AUTH_READ_OPERATION_DEFINITION_ID, deadline=deadline)
    assert contract.result_schema is not None
    assert contract.result_schema.schema_id == AUTH_READ_RESULT_SCHEMA_ID
    observed = result_client.operation(
        OperationObserve(
            request_id=uuid4(),
            profile_id=profile_id,
            session_id=result_client.session_id,
            observation=OperationObservationRequestV1(
                operation_id=completion.operation_id, after_cursor=0, page_limit=32
            ),
        ),
        deadline=deadline,
    )
    assert isinstance(observed, OperationObserved)
    assert isinstance(observed.observation, OperationObservationSuccessV1)
    terminal = observed.observation.projection
    assert terminal.operation_id == completion.operation_id
    assert terminal.definition_id == AUTH_READ_OPERATION_DEFINITION_ID
    assert terminal.subject_ref == profile_operation_subject(str(profile_id))
    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    result_reference = OperationResultProjectionRequestV1(
        operation_id=completion.operation_id,
        terminal_revision=terminal.revision,
        definition_contract_digest=contract.definition_contract_digest,
        result_schema=contract.result_schema,
    )
    document = result_client.read_result_document(result_reference, timeout=10)
    typed_result = OperationResultProjectionSuccessV1[AuthReadProjection].model_validate_json(
        canonical_json_bytes(document)
    )
    assert typed_result.projection == completion.projection
    assert typed_result.result_schema == result_reference.result_schema
    assert typed_result.definition_contract_digest == result_reference.definition_contract_digest
    expected_document = canonical_json_bytes(document)
    expected_digest = sha256_hex(expected_document)
    released = _ReleasedAuthRead(completion, result_reference, typed_result, expected_document, expected_digest)
    released_page = result_client.read_result_page(
        result_reference,
        ProjectionPageRequest(expected_digest=expected_digest),
        deadline=time.monotonic() + 10,
    )
    _assert_first_page(released_page, released)
    return released


def _approve_in_tui(profile_id: UUID, request_id: UUID) -> None:
    human = asyncio.run(open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.TUI))
    try:
        password = bytearray(PROFILE_INPUT.encode("utf-8"))
        human.login_password(password)
        assert not any(password)
        inventory = read_automation_inventory(human).projection
        review = next(item for item in inventory.requests if item.receipt.request_id == request_id)
        fresh_proof = bytearray(PROFILE_INPUT.encode("utf-8"))
        receipt = run_automation_decision(human, review, decision="approve", password=fresh_proof)
        assert not any(fresh_proof)
        assert receipt.effect.value == "updated"
    finally:
        human_primary = sys.exception()
        asyncio.run(
            close_async_resources(
                human.cleanup_owner(primary_error=human_primary),
                task_name="grant-result-reviewer-close",
                primary_error=human_primary,
            )
        )


async def _sign_in_with_api_reference(pilot: Pilot[object], login: RuntimeLoginScreen, reference: UUID) -> None:
    # The screen first tries the stored sign-in for the selected profile and
    # ignores a method change until that attempt has been refused.
    await pilot.pause()
    await _until(pilot, lambda: not login._busy, timeout=25)
    login.query_one("#runtime-login-method", Select).value = RuntimeLoginMethod.API_REFERENCE
    await pilot.pause()
    credential = login.query_one("#runtime-login-credential", Input)
    assert credential.password and credential.value == "" and not credential.display
    login.query_one("#runtime-login-reference", Input).value = str(reference)
    login.query_one("#runtime-login-submit", Button).press()
    await pilot.pause()
    await _until(pilot, lambda: not login._busy, timeout=25)
    if not login._transferred:
        status = login.query_one("#runtime-login-status", PinnedStatusBar)
        raise AssertionError(f"credential login did not transfer: {status.message}")


def _fill_grant_change_form(
    request: RuntimeAutomationRequesterScreen,
    destination_id: UUID,
    kind: EnrollmentKind,
    grant: AutomationGrant,
    key: ApiKeyRecord,
    reference: UUID,
) -> None:
    for operation in grant.scope.operations:
        request.query_one("#automation-request-operations", SelectionList).select(operation)
    for disclosure in grant.scope.disclosures:
        request.query_one("#automation-request-disclosures", SelectionList).select(
            f"{disclosure.projection_id}|{disclosure.category.value}"
        )
    chosen_actions = (
        grant.scope.actions - {AccessAction.RESULT} if kind is EnrollmentKind.CHANGE_SCOPE else grant.scope.actions
    )
    for action in chosen_actions:
        request.query_one("#automation-request-actions", SelectionList).select(action.value)
    request.query_one("#automation-request-period-mode", Select).value = "all"
    request.query_one("#automation-request-independent", Checkbox).value = True
    request.query_one("#automation-request-unattended", Checkbox).value = True
    expiry = grant.expires_at + timedelta(days=30) if kind is EnrollmentKind.RENEW else grant.expires_at
    request.query_one("#automation-request-expiry", Input).value = expiry.isoformat()
    request.query_one("#automation-request-grant", Input).value = str(grant.grant_id)
    request.query_one("#automation-request-reference", Input).value = str(reference)
    if kind is EnrollmentKind.ROTATE:
        request.query_one("#automation-request-key", Input).value = str(key.key_id)
        request.query_one("#automation-request-key-expiry", Input).value = (now() + timedelta(days=15)).isoformat()
    proposed = request._draft().proposal(destination_id)
    assert proposed.kind is kind
    assert proposed.target_grant_id == grant.grant_id
    assert proposed.scope.actions == chosen_actions
    assert proposed.scope == changed(grant.scope, actions=chosen_actions)


async def _submit_and_await_approval(
    pilot: Pilot[object],
    request: RuntimeAutomationRequesterScreen,
    profile_id: UUID,
    pool: ThreadPoolExecutor,
    owner: NativeRuntimeFixtureOwner,
) -> AutomationRequestOutcome:
    request.query_one("#automation-request-submit", Button).press()
    await _until(pilot, lambda: request._submitted is not None)
    submitted = request._submitted
    assert submitted is not None and submitted.stage is EnrollmentStage.REQUESTED
    approval_context = copy_context()
    approval = pool.submit(lambda: approval_context.run(_approve_in_tui, profile_id, submitted.request_id))
    owner.auxiliary.append(approval)
    await _until(pilot, lambda: request._outcome is not None or approval.done(), timeout=45)
    if approval.done():
        approval.result()
    if request._outcome is None:
        await _until(pilot, lambda: request._outcome is not None, timeout=45)
    approval_error = await await_cancellation_complete(
        asyncio.to_thread(approval.exception, timeout=45),
        task_name="grant-result-approval-settlement",
    )
    if approval_error is not None:
        raise approval_error
    outcome = request._outcome
    assert outcome is not None and outcome.stage is EnrollmentStage.COMPLETE
    assert not outcome.uncertain and outcome.request_id == submitted.request_id
    assert PROFILE_INPUT not in str(request.query_one("#automation-request-status", Static).render())
    return outcome


def _grant_change_driver(
    *,
    kind: EnrollmentKind,
    grant: AutomationGrant,
    key: ApiKeyRecord,
    reference: UUID,
    outcomes: list[AutomationRequestOutcome],
    profile_id: UUID,
    destination_id: UUID,
    pool: ThreadPoolExecutor,
    owner: NativeRuntimeFixtureOwner,
) -> AutopilotCallbackType:
    async def drive(pilot: Pilot[object]) -> None:
        login = pilot.app.screen
        if isinstance(login, RuntimeLoginScreen):
            if outcomes:
                login.action_abandon()
                return
            await _sign_in_with_api_reference(pilot, login, reference)
            return

        app = pilot.app
        assert isinstance(app, RuntimeRestrictedSessionApp)
        await _until(
            pilot,
            lambda: str(profile_id) in str(app.query_one("#restricted-profile", Static).render()),
        )
        await pilot.click("#restricted-request-access")
        await _until(pilot, lambda: isinstance(app.screen, RuntimeAutomationRequesterScreen))
        request = app.screen
        assert isinstance(request, RuntimeAutomationRequesterScreen)
        assert request._client is not None and request._client.profile_id == profile_id
        request.query_one("#automation-request-kind", Select).value = kind
        await asyncio.sleep(0.05)
        _fill_grant_change_form(request, destination_id, kind, grant, key, reference)
        outcomes.append(await _submit_and_await_approval(pilot, request, profile_id, pool, owner))
        request.action_close()
        await _until(pilot, lambda: not app.is_running or app.screen is app, timeout=10)
        if app.is_running:
            app.action_leave()

    return drive


def _assert_grant_change_applied(
    *,
    kind: EnrollmentKind,
    subject: AdministrationSubject,
    before: AutomationGrant,
    active_key: ApiKeyRecord,
    current_key: ApiKeyRecord,
    outcome: AutomationRequestOutcome,
    reference: UUID,
    initial_scope: AccessScope,
) -> tuple[AutomationGrant, UUID, ApiKeyRecord]:
    """Check the stored grant after one TUI-reviewed change; return it, the live reference and the live key."""
    prior_reference = reference
    after = subject.store.snapshot()
    grant = next(item for item in after.grants if item.grant_id == before.grant_id)
    assert grant.state is AuthorityState.ACTIVE
    expected_generation = before.generation + (kind is not EnrollmentKind.ROTATE)
    assert grant.generation == expected_generation
    if kind is EnrollmentKind.CHANGE_SCOPE:
        assert grant.scope.actions == before.scope.actions - {AccessAction.RESULT}
        assert grant.scope == changed(before.scope, actions=before.scope.actions - {AccessAction.RESULT})
        assert grant.scope.disclosures == initial_scope.disclosures
        assert reference == prior_reference
        preserved_key = next(item for item in after.keys if item.key_id == active_key.key_id)
        assert changed(preserved_key, last_used_at=active_key.last_used_at) == active_key
    else:
        assert grant.scope == before.scope
    if kind is EnrollmentKind.ROTATE:
        assert outcome.credential_reference is not None
        assert outcome.credential_reference != prior_reference
        reference = outcome.credential_reference
        predecessor = next(item for item in after.keys if item.key_id == active_key.key_id)
        assert predecessor.expires_at <= now() + KEY_ROTATION_MAXIMUM_OVERLAP
        current_key = next(
            item
            for item in after.keys
            if item.grant_id == grant.grant_id
            and item.state is AuthorityState.ACTIVE
            and item.key_id != active_key.key_id
        )
        assert (CLIENT_NAMESPACE, str(reference)) in subject.client_native.items
    else:
        assert outcome.credential_reference is None
        reference = prior_reference
    return grant, reference, current_key


def _assert_cli_inspects_the_change(
    profile_id: UUID,
    kind: EnrollmentKind,
    outcome: AutomationRequestOutcome,
    grant: AutomationGrant,
    current_key: ApiKeyRecord,
) -> None:
    assert outcome.request_id is not None
    inspect = _cli_inspect(profile_id, outcome.request_id)
    receipt = inspect.review.receipt
    assert inspect.profile_id == profile_id
    assert receipt.request_id == outcome.request_id
    assert receipt.grant_id == grant.grant_id
    assert receipt.stage is EnrollmentStage.COMPLETE
    assert receipt.credential_reference == outcome.credential_reference
    if kind is EnrollmentKind.ROTATE:
        assert receipt.key_id == current_key.key_id
    else:
        assert receipt.key_id is None


def _assert_revised_grant_reads(cli_api: FrontendClient, kind: EnrollmentKind, released: _ReleasedAuthRead) -> None:
    result_reference = released.result_reference
    if kind is EnrollmentKind.CHANGE_SCOPE:
        with pytest.raises(FrontendRefusedError) as full_denial:
            cli_api.read_result_document(result_reference, timeout=10)
        assert full_denial.value.reason == AccessDenialCode.OPERATION_DENIED.value
        with pytest.raises(FrontendRefusedError) as page_denial:
            cli_api.read_result_page(
                result_reference,
                ProjectionPageRequest(expected_digest=released.expected_digest),
                deadline=time.monotonic() + 10,
            )
        assert page_denial.value.reason == AccessDenialCode.OPERATION_DENIED.value
        assert cli_api.status().status.grant_valid
        return
    current_document = cli_api.read_result_document(result_reference, timeout=10)
    current_result = OperationResultProjectionSuccessV1[AuthReadProjection].model_validate_json(
        canonical_json_bytes(current_document)
    )
    assert current_result == released.typed_result
    assert current_result.projection == released.completion.projection
    assert current_result.result_schema == result_reference.result_schema
    assert current_result.definition_contract_digest == result_reference.definition_contract_digest
    assert canonical_json_bytes(current_document) == released.expected_document
    current_page = cli_api.read_result_page(
        result_reference,
        ProjectionPageRequest(expected_digest=released.expected_digest),
        deadline=time.monotonic() + 10,
    )
    _assert_first_page(current_page, released)


def _revoke_active_key_with_tui(subject: AdministrationSubject, profile_id: UUID, active_key: ApiKeyRecord) -> None:
    human = asyncio.run(open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.TUI))
    try:
        proof = bytearray(PROFILE_INPUT.encode("utf-8"))
        human.login_password(proof)
        assert not any(proof)

        async def no_recovery(*, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> FrontendClient:
            raise AssertionError("key revocation does not open a recovery connection")

        access = RuntimeAccessManagementScreen(human, open_recovery_client=no_recovery)

        async def revoke_with_tui(pilot: Pilot[None]) -> None:
            await _until(pilot, lambda: access._admin_available and not access._busy)
            access.query_one("#runtime-access-target", Input).value = str(active_key.key_id)
            access.query_one("#runtime-access-deny-key", Button).press()
            await _until(
                pilot,
                lambda: (
                    not access._busy
                    and any(
                        key.key_id == active_key.key_id and key.state is AuthorityState.REVOKED
                        for key in subject.store.snapshot().keys
                    )
                ),
            )
            assert str(access.query_one("#runtime-access-status", Static).content) == tr(
                "tui.runtime_access.denial_acknowledgement",
                access_denied=tr("flows.confirm.yes"),
                cleanup_pending=tr("flows.confirm.no"),
            )
            access.action_close()

        async def run_revoke_screen() -> None:
            async with ScreenHostApp(access).run_test(size=(120, 40)) as pilot:
                await revoke_with_tui(pilot)

        asyncio.run(run_revoke_screen())
    finally:
        human_primary = sys.exception()
        asyncio.run(
            close_async_resources(
                human.cleanup_owner(primary_error=human_primary),
                task_name="grant-result-revoker-close",
                primary_error=human_primary,
            )
        )


def test_tui_rotates_renews_changes_scope_and_cli_inspects_same_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each TUI-reviewed grant revision is visible through fresh CLI authority and inspection."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsEndpoint(storage_root=storage_root)
    installation_identity = installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with (
        override_settings(cadrumo_profile_kdf_measure_calibration=False),
        administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation_identity.installation_id
        ) as subject,
    ):
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=subject.client_native
        )
        destination_id = requester.client_id
        initial_scope = changed(
            _grant_scope(),
            operations=_grant_scope().operations | {AUTH_READ_OPERATION_DEFINITION_ID},
            actions=_grant_scope().actions | {AccessAction.OBSERVE},
            disclosures=frozenset(
                {
                    DisclosurePermission(
                        destination_id=destination_id,
                        projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                        category=DisclosureCategory.OPERATION_METADATA,
                    ),
                    DisclosurePermission(
                        destination_id=destination_id,
                        projection_id=AUTH_READ_RESULT_SCHEMA_ID,
                        category=DisclosureCategory.PROFILE_VALUES,
                    ),
                }
            ),
        )
        # Expand only this fixture's synthetic authority before actual consent.
        facts = subject.owner.current
        assert facts.session is not None
        subject.owner.current = changed(
            facts,
            profile=changed(facts.profile, scope=initial_scope),
            session=changed(facts.session, scope=initial_scope),
        )
        initial_request = uuid4()
        subject.service.request(initial_request, changed(subject.proposal, scope=initial_scope))
        initial = subject.approve(initial_request)
        assert initial.credential_reference is not None and initial.key_id is not None
        profile_id = subject.store.binding.profile_id
        reference = initial.credential_reference
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
        monkeypatch.setattr(credentials, "installed_automation_secret_store", lambda: subject.client_native)

        with override_settings(
            cadrumo_storage_root=storage_root,
            cadrumo_output_language="en",
            cadrumo_cli_reveal_identifiers=True,
        ):
            owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=20)
            resources = [owner]
            opened_clients: list[FrontendClient] = []
            primary: BaseException | None = None
            pool = ThreadPoolExecutor(max_workers=3)
            owner.executor = pool
            try:
                context = copy_context()

                def serve() -> None:
                    context.run(server.serve)

                owner.running = pool.submit(serve)
                owner.server = server
                assert server.ready.wait(3)
                before = subject.store.snapshot()
                grant = next(item for item in before.grants if item.state is AuthorityState.ACTIVE)
                assert grant.client_id == destination_id
                assert {permission.destination_id for permission in grant.scope.disclosures} == {grant.client_id}
                current_key = next(
                    item
                    for item in before.keys
                    if item.grant_id == grant.grant_id and item.state is AuthorityState.ACTIVE
                )
                result_client = _connect_cli(profile_id, reference, subject.client_native)
                try:
                    released = _read_released_auth_result(result_client, profile_id)
                finally:
                    result_primary = sys.exception()
                    asyncio.run(
                        close_async_resources(
                            result_client.cleanup_owner(primary_error=result_primary),
                            task_name="grant-result-positive-close",
                            primary_error=result_primary,
                        )
                    )
                changes = (EnrollmentKind.ROTATE, EnrollmentKind.RENEW, EnrollmentKind.CHANGE_SCOPE)

                for kind in changes:
                    before_change = subject.store.snapshot()
                    current_grant = next(item for item in before_change.grants if item.grant_id == grant.grant_id)
                    active_key = next(
                        item
                        for item in before_change.keys
                        if item.grant_id == grant.grant_id and item.state is AuthorityState.ACTIVE
                    )
                    outcome_holder: list[AutomationRequestOutcome] = []
                    driver = _grant_change_driver(
                        kind=kind,
                        grant=current_grant,
                        key=active_key,
                        reference=reference,
                        outcomes=outcome_holder,
                        profile_id=profile_id,
                        destination_id=destination_id,
                        pool=pool,
                        owner=owner,
                    )
                    assert main(headless=True, auto_pilot=driver) == 0
                    assert len(outcome_holder) == 1
                    outcome = outcome_holder[0]
                    assert outcome.request_id is not None
                    grant, reference, current_key = _assert_grant_change_applied(
                        kind=kind,
                        subject=subject,
                        before=current_grant,
                        active_key=active_key,
                        current_key=current_key,
                        outcome=outcome,
                        reference=reference,
                        initial_scope=initial_scope,
                    )
                    _assert_cli_inspects_the_change(profile_id, kind, outcome, grant, current_key)
                    cli_api = _connect_cli(profile_id, reference, subject.client_native)
                    try:
                        assert cli_api.profile_id == profile_id
                        assert cli_api.status().status.grant_valid
                        _assert_revised_grant_reads(cli_api, kind, released)
                    finally:
                        cli_primary = sys.exception()
                        asyncio.run(
                            close_async_resources(
                                cli_api.cleanup_owner(primary_error=cli_primary),
                                task_name="grant-result-revised-close",
                                primary_error=cli_primary,
                            )
                        )

                active_key = current_key
                live_cli = _connect_cli(profile_id, reference, subject.client_native)
                opened_clients.append(live_cli)
                assert live_cli.status().status.grant_valid
                _revoke_active_key_with_tui(subject, profile_id, active_key)
                revoked = next(item for item in subject.store.snapshot().keys if item.key_id == active_key.key_id)
                assert revoked.state is AuthorityState.REVOKED
                _assert_fenced(live_cli)
                _assert_cli_refused(profile_id, reference, subject.client_native)
            except BaseException as error:
                primary = error
                raise
            finally:
                asyncio.run(
                    close_async_resources(
                        *(client.cleanup_owner(primary_error=primary) for client in reversed(opened_clients)),
                        *resources,
                        task_name="grant-lock-parity-native-close",
                        primary_error=primary,
                    )
                )


def test_tui_profile_lock_resumes_only_selected_grant_seen_by_cli(tmp_path: Path) -> None:
    """A TUI profile lock fences an open CLI lease; fresh proof resumes only the selected grant."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsEndpoint(storage_root=storage_root)
    installation_identity = installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with (
        override_settings(cadrumo_profile_kdf_measure_calibration=False),
        administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation_identity.installation_id
        ) as subject,
    ):
        issued: list[tuple[UUID, UUID]] = []
        for _ in range(2):
            request_id = uuid4()
            subject.service.request(request_id, changed(subject.proposal, scope=_grant_scope()))
            outcome = subject.approve(request_id)
            assert outcome.grant_id is not None and outcome.credential_reference is not None
            issued.append((outcome.grant_id, outcome.credential_reference))
        (selected_grant, selected_reference), (held_grant, held_reference) = issued
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
        with override_settings(cadrumo_storage_root=storage_root):
            owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=20)
            pool = ThreadPoolExecutor(max_workers=2)
            owner.executor = pool
            opened_clients: list[FrontendClient] = []
            primary: BaseException | None = None
            try:
                context = copy_context()

                def serve() -> None:
                    context.run(server.serve)

                owner.running = pool.submit(serve)
                owner.server = server
                assert server.ready.wait(3)
                selected_cli = _connect_cli(profile_id, selected_reference, subject.client_native)
                opened_clients.append(selected_cli)
                assert selected_cli.status().status.grant_valid
                human = asyncio.run(
                    open_installed_client(profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
                )
                opened_clients.append(human)
                proof = bytearray(PROFILE_INPUT.encode("utf-8"))
                admitted = human.login_password(proof)
                assert not any(proof)
                assert admitted.status.profile_id == profile_id and admitted.status.credential_authenticated

                async def open_recovery_client(
                    *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
                ) -> FrontendClient:
                    return await open_installed_client(
                        profile_id=profile_id, frontend=OperationFrontendProjection.TUI, timeout=timeout
                    )

                access = RuntimeAccessManagementScreen(human, open_recovery_client=open_recovery_client)

                async def lock_and_resume(pilot: Pilot[None]) -> None:
                    await _until(pilot, lambda: access._admin_available and not access._busy)
                    session_text = str(access.query_one("#runtime-access-sessions", Static).content)
                    assert str(selected_cli.session_id) in session_text
                    access.query_one("#runtime-access-lock-profile", Button).press()
                    await _until(pilot, lambda: access.access_lost and not access._busy)
                    assert subject.store.profile_lock_state().globally_locked
                    assert {item.state for item in subject.store.snapshot().grants} == {AuthorityState.SUSPENDED}
                    await asyncio.to_thread(_assert_fenced, selected_cli)
                    password = access.query_one("#runtime-access-password", Input)
                    assert password.password
                    password.value = PROFILE_INPUT
                    access.query_one("#runtime-access-grants", Input).value = str(selected_grant)
                    access.query_one("#runtime-access-resume", Button).press()
                    await _until(pilot, lambda: access._resume_receipt is not None and not access._busy, timeout=30)
                    receipt = access._resume_receipt
                    assert isinstance(receipt, AutomationResumeReceipt)
                    assert receipt.profile_id == profile_id
                    assert receipt.reactivated_grants == frozenset({selected_grant})
                    assert password.value == ""
                    assert access.query_one("#runtime-access-grants", Input).value == ""
                    access.action_close()

                async def run_screen() -> None:
                    async with ScreenHostApp(access).run_test(size=(120, 40)) as pilot:
                        await lock_and_resume(pilot)

                asyncio.run(run_screen())
                states = {item.grant_id: item.state for item in subject.store.snapshot().grants}
                assert not subject.store.profile_lock_state().globally_locked
                assert states[selected_grant] is AuthorityState.ACTIVE
                assert states[held_grant] is AuthorityState.SUSPENDED
                _assert_fenced(selected_cli)
                fresh = _connect_cli(profile_id, selected_reference, subject.client_native)
                try:
                    assert fresh.status().status.grant_valid
                finally:
                    fresh.close()
                _assert_cli_refused(profile_id, held_reference, subject.client_native)
            except BaseException as error:
                primary = error
                raise
            finally:
                for client in reversed(opened_clients):
                    client.close()
                asyncio.run(
                    close_async_resources(
                        owner,
                        task_name="profile-lock-parity-native-close",
                        primary_error=primary,
                    )
                )
                pool.shutdown(wait=True, cancel_futures=True)


async def _assert_administration_presented_disabled(
    pilot: Pilot[None], app: ScreenHostApp[None], access: RuntimeAccessManagementScreen, factories: list[FrontendClient]
) -> None:
    await _until(
        pilot,
        lambda: (
            AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value
            in str(access.query_one("#runtime-access-status", Static).content)
        ),
    )
    # Wait for the actual inventory request, not just the initial default flags.
    await asyncio.wait_for(app.workers.wait_for_complete(), 30)
    assert not access.access_lost
    assert not access.query_one("#runtime-access-sessions", Static).content
    assert not access.query_one("#runtime-access-lock-current", Button).disabled
    for suffix in (
        "create-automation",
        "view-automation",
        "refresh",
        "lock-selected",
        "lock-profile",
        "deny-key",
        "deny-grant",
        "deny-all",
    ):
        assert access.query_one(f"#runtime-access-{suffix}", Button).disabled
    create = access.query_one("#runtime-access-create-automation", Button)
    access.on_button_pressed(Button.Pressed(create))
    await pilot.pause()
    assert app.screen is access and not factories


async def _assert_forced_commands_refused(
    app: ScreenHostApp[None],
    access: RuntimeAccessManagementScreen,
    api: FrontendClient,
    subject: AdministrationSubject,
    factories: list[FrontendClient],
    *,
    targets: tuple[tuple[str, UUID | None], ...],
    before: object,
    enrollment_before: object,
    lock_before: object,
) -> None:
    # Force real command dispatch past disabled-button presentation. Authority still refuses.
    for suffix, target in targets:
        access.query_one("#runtime-access-target", Input).value = str(target) if target else ""
        access.query_one("#runtime-access-status", Static).update("")
        access.on_button_pressed(Button.Pressed(access.query_one(f"#runtime-access-{suffix}", Button)))
        await asyncio.wait_for(app.workers.wait_for_complete(), 30)
        assert AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value in str(
            access.query_one("#runtime-access-status", Static).content
        )
        assert not access.access_lost and not access._admin_available
        current = subject.store.snapshot()
        assert current == before
        assert subject.store.enrollment_state() == enrollment_before
        assert subject.store.profile_lock_state() == lock_before
        assert (await asyncio.to_thread(api.status)).status.grant_valid
    assert not factories


async def _lock_only_the_current_session(
    pilot: Pilot[None],
    access: RuntimeAccessManagementScreen,
    api: FrontendClient,
    sibling: FrontendClient,
    subject: AdministrationSubject,
    session_id: UUID,
    *,
    before: object,
    enrollment_before: object,
    lock_before: object,
) -> None:
    access.query_one("#runtime-access-lock-current", Button).press()
    await _until(pilot, lambda: access.access_lost and not access._busy)
    assert str(session_id) in str(access.query_one("#runtime-access-status", Static).content)
    await asyncio.to_thread(_assert_fenced, api)
    current = subject.store.snapshot()
    assert current == before
    assert subject.store.enrollment_state() == enrollment_before
    assert subject.store.profile_lock_state() == lock_before
    assert (await asyncio.to_thread(sibling.status)).status.grant_valid
    access.action_close()


def test_api_reference_tui_refuses_programmatic_administration_but_can_lock_own_session(
    tmp_path: Path,
) -> None:
    """Real encrypted workers refuse API administration; login and custody are explicit test ports."""
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsEndpoint(storage_root=storage_root)
    installation_identity = installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with (
        override_settings(cadrumo_profile_kdf_measure_calibration=False),
        administration_subject(
            tmp_path, os_owner_id=owner_id(), installation_id=installation_identity.installation_id
        ) as subject,
    ):
        initial_request = uuid4()
        subject.service.request(initial_request, changed(subject.proposal, scope=_grant_scope()))
        initial = subject.approve(initial_request)
        assert initial.credential_reference is not None and initial.key_id is not None
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
        factories: list[FrontendClient] = []

        async def journey() -> None:
            api = await open_installed_credential_client(
                profile_id=profile_id,
                credential_reference=initial.credential_reference,
                frontend=OperationFrontendProjection.TUI,
                secrets_store=subject.client_native,
            )
            client_primary: BaseException | None = None
            related_clients: list[FrontendClient] = []
            try:
                status = await asyncio.to_thread(api.status)
                assert status.status.profile_id == profile_id and status.status.grant_valid
                assert status.status.session_id == api.session_id
                session_id = api.session_id
                with pytest.raises(FrontendRefusedError) as denied:
                    await asyncio.to_thread(api.sessions)
                assert denied.value.reason == AccessDenialCode.HUMAN_AUTHORITY_REQUIRED.value
                sibling = await open_installed_credential_client(
                    profile_id=profile_id,
                    credential_reference=initial.credential_reference,
                    frontend=OperationFrontendProjection.CLI,
                    secrets_store=subject.client_native,
                )
                related_clients.append(sibling)
                sibling_id = sibling.session_id
                assert sibling_id != session_id
                before = subject.store.snapshot()
                enrollment_before = subject.store.enrollment_state()
                lock_before = subject.store.profile_lock_state()
                assert not lock_before.globally_locked

                async def no_recovery(*, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> FrontendClient:
                    raise AssertionError("API administration must not acquire fresh human proof")

                def no_requester(reviewer: FrontendClient) -> RuntimeAutomationRequesterScreen:
                    factories.append(reviewer)
                    raise AssertionError("API authority must not open human enrollment")

                access = RuntimeAccessManagementScreen(
                    api, open_recovery_client=no_recovery, requester_factory=no_requester
                )
                app = ScreenHostApp(access)
                async with app.run_test(size=(140, 48)) as pilot:
                    await _assert_administration_presented_disabled(pilot, app, access, factories)
                    await _assert_forced_commands_refused(
                        app,
                        access,
                        api,
                        subject,
                        factories,
                        targets=(
                            ("lock-selected", sibling_id),
                            ("deny-key", initial.key_id),
                            ("deny-grant", initial.grant_id),
                            ("deny-all", None),
                            ("lock-profile", None),
                        ),
                        before=before,
                        enrollment_before=enrollment_before,
                        lock_before=lock_before,
                    )
                    await _lock_only_the_current_session(
                        pilot,
                        access,
                        api,
                        sibling,
                        subject,
                        session_id,
                        before=before,
                        enrollment_before=enrollment_before,
                        lock_before=lock_before,
                    )
                # Locking this lease does not revoke its protected credential or grant.
                fresh = await open_installed_credential_client(
                    profile_id=profile_id,
                    credential_reference=initial.credential_reference,
                    frontend=OperationFrontendProjection.TUI,
                    secrets_store=subject.client_native,
                )
                fresh_primary: BaseException | None = None
                try:
                    renewed = await asyncio.to_thread(fresh.status)
                    assert renewed.status.grant_valid and fresh.session_id != session_id
                except BaseException as error:
                    fresh_primary = error
                    raise
                finally:
                    await close_async_resources(
                        fresh.cleanup_owner(primary_error=fresh_primary),
                        task_name="api-refusal-fresh-client-close",
                        primary_error=fresh_primary,
                    )
            except BaseException as error:
                client_primary = error
                raise
            finally:
                await close_async_resources(
                    *(client.cleanup_owner(primary_error=client_primary) for client in reversed(related_clients)),
                    api.cleanup_owner(primary_error=client_primary),
                    task_name="api-refusal-client-close",
                    primary_error=client_primary,
                )

        with override_settings(cadrumo_storage_root=storage_root, cadrumo_output_language="en"):
            owner = NativeRuntimeFixtureOwner(endpoint, stop, timeout=20)
            owner.executor = ThreadPoolExecutor(max_workers=1)
            primary: BaseException | None = None
            try:
                context = copy_context()

                def serve() -> None:
                    context.run(server.serve)

                owner.running = owner.executor.submit(serve)
                owner.server = server
                assert server.ready.wait(3)
                asyncio.run(journey())
            except BaseException as error:
                primary = error
                raise
            finally:
                owner.close_from_sync(task_name="api-refusal-runtime-close", primary_error=primary)
