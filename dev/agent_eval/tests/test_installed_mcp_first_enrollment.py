"""First authorization uses installed SDK tools and an actual native secret store.

The encrypted profile, runtime, workers, server control/wrap records and newly
delivered client item are real. Linux acceptance requires the selected protected
GNOME fixture; Windows acceptance requires the selected normal-desktop Windows
Credential Manager fixture. OS-login observations and the fixture's earlier,
independent grant are synthetic setup. No key from that grant is copied or used
by this journey; this does not prove an actual desktop-login lifecycle.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import delete_profile_session
from cadrumo.adapters.persistence.storage.custody.automation_client_credentials import NativeClientCredentialStore
from cadrumo.adapters.persistence.storage.custody.automation_secret_store import (
    WindowsAutomationSecretStore,
    native_automation_secret_store,
)
from cadrumo.adapters.persistence.storage.custody.linux_secret_service_store import (
    LinuxSecretServiceAutomationSecretStore,
)
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import PROFILE_INPUT
from cadrumo.adapters.persistence.storage.custody.tests.test_windows_automation_secret_store_native import (
    require_selected_normal_desktop,
)
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID, AuthReadRequest
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore, NativeSecretBackend
from cadrumo.application.user_profile.automation_enrollment import (
    AutomationReceiptProjection,
    AutomationReviewProjection,
    EnrollmentKind,
    EnrollmentProposal,
    EnrollmentStage,
)
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo.core.config import override_settings
from cadrumo.core.hashing import canonical_json_bytes
from cadrumo.core.operations import profile_operation_subject
from cadrumo.core.time.clock import now
from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path
from cadrumo.entrypoints.cli.tests.native_api_cli_support import native_api_cli_session

from .test_installed_authenticated_stdio import _installed_mcp_executable, _scope_for_auth_read
from .test_installed_mcp_tui_grant_parity import _private_read, _record, _status

if TYPE_CHECKING:
    from click.testing import Result

    from cadrumo.entrypoints.cli.tests.native_api_cli_support import NativeApiCliSession

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_core,
    pytest.mark.os_keychain,
    pytest.mark.skipif(
        sys.platform not in {"linux", "win32"},
        reason="requires installed MCP and a supported native secret store",
    ),
]

_GNOME_EXPECTATION = "CADRUMO_TEST_GNOME_COLLECTION_EXPECTATION"
_WINDOWS_EXPECTATION = "CADRUMO_TEST_WINDOWS_CREDENTIAL_MANAGER_EXPECTATION"


def _selected_native_store() -> tuple[NativeSecretBackend, AutomationSecretStore]:
    """Use only the explicitly selected protected store for this machine."""
    if os.environ.get(_GNOME_EXPECTATION) == "protected" and sys.platform != "linux":
        pytest.fail("protected GNOME acceptance requires Linux", pytrace=False)
    if os.environ.get(_WINDOWS_EXPECTATION) == "protected" and sys.platform != "win32":
        pytest.fail("protected Windows Credential Manager acceptance requires Windows", pytrace=False)

    if sys.platform == "linux":
        selected = os.environ.get(_GNOME_EXPECTATION)
        if selected is None:
            pytest.skip("requires explicit protected GNOME native custody selection")
        if selected == "unsuitable":
            pytest.skip("the selected GNOME collection is unsuitable for protected delivery")
        if selected != "protected":
            pytest.fail("GNOME collection expectation must be protected or unsuitable", pytrace=False)
        backend = NativeSecretBackend.LINUX_DBUS
        store = native_automation_secret_store(backend)
        assert isinstance(store, LinuxSecretServiceAutomationSecretStore)
        return backend, store

    if sys.platform == "win32":
        require_selected_normal_desktop()
        backend = NativeSecretBackend.WINDOWS_CREDENTIAL_MANAGER
        store = native_automation_secret_store(backend)
        assert isinstance(store, WindowsAutomationSecretStore)
        return backend, store

    pytest.skip("requires Linux Secret Service or Windows Credential Manager")


def _inspect_request(profile: NativeApiCliSession[None], request_id: UUID) -> AutomationReviewProjection:
    inspected = profile.invoke_password("config", "profile", "automation", "inspect", str(request_id))
    assert inspected.exit_code == 0, inspected.output
    document = _record(json.loads(inspected.stdout))
    assert document["command"] == "config.profile.automation.inspect"
    review = AutomationReviewProjection.model_validate_json(canonical_json_bytes(_record(document["result"])["review"]))
    assert review.receipt.request_id == request_id and review.receipt.profile_id == profile.profile_id
    return review


def _approve_request(profile: NativeApiCliSession[None], receipt: AutomationReceiptProjection) -> Result:
    """Supply a separate bounded fresh-password descriptor to the human leaf."""
    reader, writer = os.pipe()
    reader_identity = os.fstat(reader)
    proof = bytearray(json.dumps({"passphrase": PROFILE_INPUT}).encode("utf-8"))
    try:
        try:
            assert os.write(writer, proof) == len(proof)
        finally:
            proof[:] = bytes(len(proof))
            os.close(writer)
        return profile.invoke_password(
            "config",
            "profile",
            "automation",
            "approve",
            str(receipt.request_id),
            "--review-digest",
            receipt.review_digest,
            "--secrets-fd",
            str(reader),
        )
    finally:
        # The canonical reader consumes/closes its descriptor. If refusal
        # happened before consumption, release only this same retained pipe.
        try:
            current = os.fstat(reader)
        except OSError:
            pass
        else:
            if (current.st_dev, current.st_ino) == (reader_identity.st_dev, reader_identity.st_ino):
                os.close(reader)


class _EnrollmentCleanup:
    """Retain exact request/native ownership, including an uncertain candidate."""

    def __init__(self, profile: NativeApiCliSession[None], store: NativeClientCredentialStore) -> None:
        self.profile, self.store = profile, store
        self.submitted: AutomationReceiptProjection | None = None
        self.native_settled = False
        self.grant_settled = False

    async def close(self) -> None:
        """Use canonical human denial and exact native deletion before fixture drain."""
        submitted = self.submitted
        if submitted is None or (self.native_settled and self.grant_settled):
            return
        review = await asyncio.to_thread(_inspect_request, self.profile, submitted.request_id)
        receipt = review.receipt
        assert receipt.grant_id == submitted.grant_id and receipt.review_digest == submitted.review_digest
        if receipt.stage is EnrollmentStage.REQUESTED:
            declined = await asyncio.to_thread(
                self.profile.invoke_password,
                "config",
                "profile",
                "automation",
                "decline",
                str(receipt.request_id),
                "--review-digest",
                receipt.review_digest,
            )
            assert declined.exit_code == 0, declined.output
            self.native_settled = self.grant_settled = True
            return
        if receipt.stage is EnrollmentStage.DECLINED and receipt.credential_reference is None:
            self.native_settled = self.grant_settled = True
            return
        # Register the current test-owned server wrapping accounts for the
        # fixture's exact post-drain native cleanup, without reading key bytes.
        await asyncio.to_thread(self.profile.server_custody_health)
        failures: list[BaseException] = []
        if not self.grant_settled:
            try:
                denied = await asyncio.to_thread(
                    self.profile.invoke_password,
                    "config",
                    "profile",
                    "automation",
                    "deny",
                    "grant",
                    str(receipt.grant_id),
                )
                assert denied.exit_code == 0, denied.output
                document = _record(json.loads(denied.stdout))
                result = _record(document["result"])
                assert result["kind"] == "grant" and result["target_id"] == str(receipt.grant_id)
                assert _record(result["receipt"])["access_denied"] is True
            except BaseException as error:
                failures.append(error)
            else:
                self.grant_settled = True
        if not self.native_settled:
            try:
                assert receipt.credential_reference is not None and receipt.key_id is not None
                await asyncio.to_thread(
                    self.store.delete,
                    credential_reference=receipt.credential_reference,
                    grant_id=receipt.grant_id,
                    key_id=receipt.key_id,
                    review_digest=receipt.review_digest,
                )
            except BaseException as error:
                failures.append(error)
            else:
                self.native_settled = True
        if failures:
            raise BaseExceptionGroup("exact enrollment cleanup requires retry", failures)


@pytest.mark.anyio
async def test_installed_sdk_first_enrollment_delivers_native_reference_and_reconnects(tmp_path: Path) -> None:
    """An unauthenticated SDK requires exact human approval and proves new possession."""
    backend, native_store = _selected_native_store()
    executable = _installed_mcp_executable()
    assert executable.is_file(), "the installed cadrumo-mcp executable is required"
    with (
        override_settings(
            cadrumo_output_language="en",
            cadrumo_profile_kdf_measure_calibration=False,
            cadrumo_cli_reveal_identifiers=True,
        ),
        native_api_cli_session(
            tmp_path,
            scope_for_destination=_scope_for_auth_read,
            prepare_profile=lambda _profile_id, _root: None,
            server_native_store=native_store,
        ) as profile,
    ):

        def parameters(reference: UUID | None = None) -> StdioServerParameters:
            arguments = ["--profile-id", str(profile.profile_id)]
            if reference is not None:
                arguments.extend(("--credential-reference", str(reference)))
            return StdioServerParameters(
                command=str(executable),
                args=arguments,
                cwd=tmp_path,
                env={
                    "CADRUMO_LOCAL_STORAGE_ROOT": str(tmp_path / "cadrumo-storage"),
                    "CADRUMO_AUTHORITY_ROOT": str(bundled_authority_descriptor_path().parent),
                    "PYDANTIC_DISABLE_PLUGINS": "__all__",
                },
            )

        cleanup: _EnrollmentCleanup | None = None
        primary: BaseException | None = None
        try:
            with (tmp_path / "first-enrollment.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters(), errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as sdk,
                ):
                    await sdk.initialize()
                    status = await sdk.call_tool("status", {})
                    assert not status.is_error
                    assert _record(status.structured_content) == {
                        "outcome": "status",
                        "profile_id": str(profile.profile_id),
                        "authenticated": False,
                        "denial": "authentication_required",
                    }
                    private_arguments = {
                        "definition_id": AUTH_READ_OPERATION_DEFINITION_ID,
                        "subject_ref": profile_operation_subject(str(profile.profile_id)),
                        "payload": AuthReadRequest(profile_id=profile.profile_id, kind="status").model_dump(
                            mode="json"
                        ),
                    }
                    refused = await sdk.call_tool("execute", private_arguments)
                    assert refused.is_error and _record(refused.structured_content) == {
                        "outcome": "refused",
                        "code": "authentication_required",
                    }
                    prepared_call = await sdk.call_tool("authorization_prepare", {})
                    assert not prepared_call.is_error
                    prepared = _record(prepared_call.structured_content)
                    assert set(prepared) == {
                        "outcome",
                        "profile_id",
                        "request_id",
                        "client_id",
                        "destination_id",
                        "expires_at",
                    }
                    assert prepared["outcome"] == "prepared" and prepared["profile_id"] == str(profile.profile_id)
                    request_id = UUID(str(prepared["request_id"]))
                    client_id, destination_id = UUID(str(prepared["client_id"])), UUID(str(prepared["destination_id"]))
                    assert client_id == destination_id
                    # Preparing the unadmitted enrollment door creates the
                    # exact runtime host; it publishes no access session.
                    assert profile.registered_sessions() == ()
                    baseline = await asyncio.to_thread(profile.server_custody_health)
                    assert baseline.backend is backend and baseline.runtime_uses_same_store
                    assert baseline.wrapping_keys_valid and len(baseline.grant_ids) == 1
                    cleanup = _EnrollmentCleanup(
                        profile,
                        NativeClientCredentialStore(
                            secrets_store=native_store,
                            binding=profile.binding,
                            client_id=client_id,
                            destination_id=destination_id,
                        ),
                    )
                    proposal = EnrollmentProposal(
                        kind=EnrollmentKind.ENROLL,
                        scope=_scope_for_auth_read(destination_id),
                        expires_at=now() + timedelta(days=30),
                        key_expires_at=now() + timedelta(days=15),
                        unattended=True,
                        allow_os_lock=False,
                    )
                    requested = await sdk.call_tool(
                        "authorization_request", {"proposal": proposal.model_dump(mode="json")}
                    )
                    assert not requested.is_error
                    document = _record(requested.structured_content)
                    assert set(document) == {"outcome", "receipt"} and document["outcome"] == "recorded"
                    submitted = AutomationReceiptProjection.model_validate_json(
                        canonical_json_bytes(document["receipt"])
                    )
                    cleanup.submitted = submitted
                    assert submitted.request_id == request_id and submitted.profile_id == profile.profile_id
                    assert submitted.stage is EnrollmentStage.REQUESTED and submitted.grant_id not in baseline.grant_ids
                    assert submitted.key_id is None and submitted.credential_reference is None
                    refused = await sdk.call_tool("execute", private_arguments)
                    assert refused.is_error and _record(refused.structured_content)["code"] == "authentication_required"
                    review = await asyncio.to_thread(_inspect_request, profile, request_id)
                    assert (
                        review.receipt == submitted
                        and review.client_id == client_id
                        and review.destination_id == destination_id
                    )
                    assert EnrollmentProposal.model_validate_json(review.proposal.model_dump_json()) == proposal
                    delete_profile_session(storage_root=tmp_path / "cadrumo-storage", profile_id=profile.profile_id)
                    stop, started = asyncio.Event(), asyncio.Event()

                    async def poll_authorization() -> AutomationReceiptProjection | None:
                        started.set()
                        async with asyncio.timeout(120):
                            while not stop.is_set():
                                polled = await sdk.call_tool("authorization_poll", {})
                                assert not polled.is_error
                                progress = _record(polled.structured_content)
                                assert set(progress) == {"outcome", "receipt", "delivery_state"}
                                assert progress["outcome"] == "recorded"
                                receipt = AutomationReceiptProjection.model_validate_json(
                                    canonical_json_bytes(progress["receipt"])
                                )
                                assert (
                                    receipt.request_id == submitted.request_id
                                    and receipt.review_digest == submitted.review_digest
                                )
                                assert receipt.grant_id == submitted.grant_id
                                if receipt.stage is EnrollmentStage.COMPLETE:
                                    assert progress["delivery_state"] == "processed"
                                    return receipt
                                assert progress["delivery_state"] == "waiting"
                                await asyncio.sleep(0.05)
                        return None

                    polling = asyncio.create_task(poll_authorization(), name="installed-first-enrollment-poll")
                    approval_primary: BaseException | None = None
                    try:
                        await started.wait()
                        approved = await asyncio.to_thread(_approve_request, profile, submitted)
                        assert approved.exit_code == 0, approved.output
                        approved_document = _record(json.loads(approved.stdout))
                        assert approved_document["command"] == "config.profile.automation.approve"
                        approved_result = _record(approved_document["result"])
                        assert approved_result["decision"] == "approve" and approved_result["effect"] == "updated"
                        assert len(str(approved_result["operation_id"])) == 64
                        human_receipt = AutomationReceiptProjection.model_validate_json(
                            canonical_json_bytes(approved_result["receipt"])
                        )
                        completed = await await_cancellation_complete(
                            polling, task_name="installed-first-enrollment-settle"
                        )
                        assert completed is not None and completed == human_receipt
                    except BaseException as error:
                        approval_primary = error
                        raise
                    finally:
                        stop.set()
                        try:
                            await await_cancellation_complete(polling, task_name="installed-first-enrollment-settle")
                        except BaseException as error:
                            if approval_primary is None:
                                raise
                            approval_primary.add_note(f"authorization settlement also failed ({type(error).__name__})")
                    assert completed.credential_reference is not None and completed.key_id is not None
                    reference = completed.credential_reference
                    metadata = await asyncio.to_thread(cleanup.store.inspect, credential_reference=reference)
                    assert metadata.profile_id == profile.profile_id and metadata.client_id == client_id
                    assert metadata.destination_id == destination_id and metadata.grant_id == completed.grant_id
                    assert metadata.key_id == completed.key_id and metadata.review_digest == submitted.review_digest
                    authenticated = await sdk.call_tool("authenticate", {"credential_reference": str(reference)})
                    assert not authenticated.is_error
                    admitted = _record(authenticated.structured_content)
                    assert admitted["outcome"] == "authenticated"
                    first = _status({"outcome": "status", "status": admitted["status"]}, profile.profile_id)
                    assert first.effective_scope == proposal.scope and first.grant_expires_at == proposal.expires_at
                    await _private_read(sdk, profile.profile_id)
                    assert first.session_id is not None
                    worker = await asyncio.to_thread(profile.worker_health, first.session_id)
                    assert worker.identity.binding == profile.binding and worker.exact_session_admitted and worker.alive
                    if backend is NativeSecretBackend.LINUX_DBUS:
                        assert worker.linux_scope_owns_worker and worker.kernel_control_groups_match
                        assert worker.windows_job_owns_worker is None
                    else:
                        assert worker.linux_scope_owns_worker is None and worker.kernel_control_groups_match is None
                        assert worker.windows_job_owns_worker is True
                    custody = await asyncio.to_thread(profile.server_custody_health)
                    assert custody.wrapping_keys_valid and custody.runtime_uses_same_store
                    assert set(custody.grant_ids) == {*baseline.grant_ids, submitted.grant_id}
            assert profile.registered_sessions() == ()
            with (tmp_path / "first-enrollment-reconnect.stderr").open("w", encoding="utf-8") as error_log:
                async with (
                    stdio_client(parameters(reference), errlog=error_log) as (reader, writer),
                    ClientSession(reader, writer, read_timeout_seconds=60) as sdk,
                ):
                    await sdk.initialize()
                    status = await sdk.call_tool("status", {})
                    assert not status.is_error
                    second = _status(status.structured_content, profile.profile_id)
                    assert second.session_id is not None and second.session_id != first.session_id
                    assert second.effective_scope == proposal.scope and second.grant_expires_at == proposal.expires_at
                    await _private_read(sdk, profile.profile_id)
                    assert await asyncio.to_thread(cleanup.store.inspect, credential_reference=reference) == metadata
        except BaseException as error:
            primary = error
            raise
        finally:
            await close_async_resources(cleanup, task_name="installed-first-enrollment-cleanup", primary_error=primary)
