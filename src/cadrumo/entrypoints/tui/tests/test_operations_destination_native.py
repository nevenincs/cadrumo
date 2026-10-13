"""The Operations destination lists every registered operation and runs them on a real runtime.

One native runtime and one human session serve the whole journey: a read, a
change that a second read then observes, and an operation that takes a
one-shot secret. Every submission goes through the real request form and the
real ``RuntimeOperationController``; nothing stands in for the runtime.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from threading import Event
from typing import override
from uuid import UUID, uuid4

import pytest
from textual.app import App, ComposeResult
from textual.command import Hit
from textual.pilot import Pilot
from textual.widgets import Button, Input, OptionList, Select, Static, TextArea

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.installation import runtime_installation
from cadrumo.adapters.local_runtime.tests.profile_worker_support import owner_id
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    PROFILE_INPUT,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_projection import OperationPublicProjectionV1
from cadrumo.application.operations.frontend_requests import OperationObservationSuccessV1
from cadrumo.application.operations.mcp_surfaces import DEFAULT_MCP_SURFACE, mcp_surface
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.search.workbench import WorkbenchDestinationAdmissionState
from cadrumo.application.user_profile.access_contracts import (
    Availability,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
)
from cadrumo.application.user_profile.view_operation import ProfileViewOperationRequest, ProfileViewPageKind
from cadrumo.core.config import override_settings
from cadrumo.core.i18n.render import tr
from cadrumo.core.operations import OperationLifecycle, profile_operation_subject
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.runtime.profile_connections import RuntimeProfileConnections
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.navigation import (
    TUI_DESTINATION_CATALOGUE,
    TuiDestinationAdmissionV1,
    TuiDestinationCatalogueV1,
    TuiNavigationTargetV1,
    TuiScreenContextV1,
    TuiScreenFactoryV1,
    build_destination_catalogue,
)
from cadrumo.entrypoints.tui.operations.catalogue import OperationCatalogueSourceV1
from cadrumo.entrypoints.tui.operations.destination import (
    OPERATIONS_DESTINATION,
    OperationsCatalogueScreen,
    OperationsDestinationV1,
)
from cadrumo.entrypoints.tui.operations.palette import WorkbenchOperationProviderV1
from cadrumo.entrypoints.tui.operations.run_screen import OperationRunScreen
from cadrumo.entrypoints.tui.operations.runtime_controller import RuntimeOperationController
from cadrumo_harness.mcp.admitted_operations import call_admitted_operation
from cadrumo_harness.mcp.operation_contract_cache import OperationContractCache
from cadrumo_harness.mcp.runtime_admission import AdmissionDenial, McpAdmission

from ....adapters.local_runtime.tests.retained_server import RetainedRuntimeTransportServer

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_TYPED_INPUT = "operations-one-shot-input-do-not-print"
_RECIPIENT = "synthetic-accountant"
_RECIPIENT_KEY = "5a" * 32
_VIEW = "user-profile.view"
_RECIPIENT_ADD = "config.collab.recipient.add"
_RECIPIENT_LIST = "config.collab.recipient.list"
_GUARDED_OPERATION = "auth.certificate.secret.set"
_TYPED_INPUT_OPERATION = "modelo.edit.apply"
_REPLAY_KEY = "tui-operations-replay-key-synthetic"
_REPLAY_KEY_FIELD = "#operation-replay-key"
_SETTLE_SECONDS = 180


class _LoginObservation:
    login_id = "tui-operations-destination-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _connect(endpoint: WindowsRuntimeEndpoint) -> VerifiedRuntimeConnection:
    return VerifiedRuntimeConnection(
        endpoint.connect(timeout=3),
        expected=RuntimeClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


async def _until(pilot: Pilot[None], predicate: Callable[[], bool], *, seconds: float = 30) -> None:
    async with asyncio.timeout(seconds):
        while not predicate():
            await pilot.pause(0.05)


def _text(widget: Static) -> str:
    return str(widget.content)


def _field(run: OperationRunScreen, name: str) -> str:
    return f"#operation-field-{[field.name for field in run._fields].index(name)}"


def _operation_id(run: OperationRunScreen) -> str:
    """Read the operation a settled run's receipt names."""
    return _text(run.query_one("#operation-result-receipt", Static)).splitlines()[0].rsplit(": ", 1)[1]


def _rendered(app: App[None]) -> str:
    """Return every text the application currently holds in a widget."""
    parts: list[str] = []
    for screen in app.screen_stack:
        for widget in screen.query("*"):
            if isinstance(widget, Static):
                parts.append(_text(widget))
            elif isinstance(widget, Input):
                parts.append(widget.value)
            elif isinstance(widget, TextArea):
                parts.append(widget.text)
    return "\n".join(parts)


async def _open(pilot: Pilot[None], listing: OperationsCatalogueScreen, definition_id: str) -> OperationRunScreen:
    listed = listing.query_one("#operations-list", OptionList)
    listed.highlighted = listed.get_option_index(definition_id)
    listed.action_select()
    await _until(pilot, lambda: isinstance(pilot.app.screen, OperationRunScreen))
    run = pilot.app.screen
    assert isinstance(run, OperationRunScreen)
    assert _text(run.query_one("#operation-run-title", Static)) == definition_id
    return run


async def _run(pilot: Pilot[None], run: OperationRunScreen) -> None:
    """Press Run and wait until the operation has settled and its result has been read."""
    run.query_one("#operation-run", Button).press()
    receipt = run.query_one("#operation-result-receipt", Static)
    await _until(
        pilot,
        lambda: pilot.app.screen is run and bool(_text(receipt)) and all(worker.is_finished for worker in run.workers),
        seconds=_SETTLE_SECONDS,
    )


async def _close(pilot: Pilot[None], run: OperationRunScreen, listing: OperationsCatalogueScreen) -> None:
    run.action_close()
    await _until(pilot, lambda: pilot.app.screen is listing)


def _result(run: OperationRunScreen) -> dict[str, object]:
    assert run._pages, _text(run.query_one("#operation-run-notice", Static))
    document = json.loads("\n".join(run._pages))
    assert isinstance(document, dict)
    return {str(name): value for name, value in document.items()}


class _McpConnection:
    """What an admitted MCP connection hands its tools, held over this test's own session."""

    def __init__(self, client: RuntimeFrontendClient) -> None:
        self.client: RuntimeFrontendClient | None = client
        self.profile_id: UUID | None = client.profile_id
        self.admission: McpAdmission | None = McpAdmission.SIGN_IN
        self.surface = mcp_surface(DEFAULT_MCP_SURFACE)
        self._admission_denial: AdmissionDenial | None = None
        self._contracts = OperationContractCache()

    def _admitted(self) -> RuntimeFrontendClient:
        assert self.client is not None
        return self.client

    def held_secret(self, reference: UUID) -> bytearray:
        """Answer as a connection that holds nothing under any reference."""
        raise ValueError("no secret is held under that reference")

    def check_held_secret(self, reference: UUID) -> None:
        """Answer as a connection that holds nothing under any reference."""
        raise ValueError("no secret is held under that reference")


async def _settled_projection(client: RuntimeFrontendClient, operation_id: str) -> OperationPublicProjectionV1:
    """Observe one operation until it has settled, so nothing is left running when the runtime stops."""
    controller = RuntimeOperationController(client=client, operation_id=operation_id, session_id=client.session_id)
    async with asyncio.timeout(_SETTLE_SECONDS):
        while True:
            observed = await controller.observe(0, page_limit=1)
            assert isinstance(observed, OperationObservationSuccessV1)
            if observed.projection.lifecycle is OperationLifecycle.TERMINAL:
                return observed.projection
            await asyncio.sleep(0.05)


class _PaletteHost(App[None]):
    """The root seam a palette provider reads; it records targets and mounts nothing."""

    def __init__(self, catalogue: TuiDestinationCatalogueV1) -> None:
        super().__init__()
        self._catalogue = catalogue
        self.targets: list[TuiNavigationTargetV1] = []

    @property
    def workbench_search_service(self) -> object:
        return object()

    @property
    def workbench_search_refusal_code(self) -> str | None:
        return "workbench.search.unavailable"

    @property
    def destination_catalogue(self) -> TuiDestinationCatalogueV1:
        return self._catalogue

    def navigate_to(self, target: TuiNavigationTargetV1, /) -> None:
        self.targets.append(target)

    @override
    def compose(self) -> ComposeResult:
        yield Static("workbench")


def _marker(_context: TuiScreenContextV1) -> OperationsCatalogueScreen:
    raise AssertionError("no other destination is opened by this test")


def _destinations(operations: OperationsDestinationV1) -> TuiDestinationCatalogueV1:
    admissions: dict[str, TuiDestinationAdmissionV1] = {
        descriptor.destination: TuiDestinationAdmissionV1(
            destination=descriptor.destination, state=WorkbenchDestinationAdmissionState.AVAILABLE
        )
        for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories: dict[str, TuiScreenFactoryV1] = {
        descriptor.destination: _marker for descriptor in TUI_DESTINATION_CATALOGUE
    }
    factories[OPERATIONS_DESTINATION] = operations
    return build_destination_catalogue(admissions=admissions, factories=factories)


async def _journey(
    client: RuntimeFrontendClient,
    registry: OperationRegistry,
    secret_buffers: list[bytearray],
) -> None:
    registered = [contract.definition_id for contract in registry.public_contract_set.definitions]
    subject = profile_operation_subject(str(client.profile_id))

    # A secret and the contract must agree before anything is recorded, and a refused buffer is still wiped.
    named_source = registry.lookup(_GUARDED_OPERATION).request_type.model_validate(
        {"profile_id": client.profile_id, "name": "synthetic-certificate-source"}
    )
    with pytest.raises(RuntimeRefusalError) as missing_secret:
        await RuntimeOperationController.submit(
            client, definition_id=_GUARDED_OPERATION, subject_ref=subject, payload=named_source
        )
    assert missing_secret.value.reason is RuntimeRefusalCode.INVALID_FRAME
    stray = bytearray(_TYPED_INPUT, "utf-8")
    view = ProfileViewOperationRequest(profile_id=client.profile_id, page_kind=ProfileViewPageKind.STATUS)
    with pytest.raises(RuntimeRefusalError) as stray_secret:
        await RuntimeOperationController.submit(
            client, definition_id=_VIEW, subject_ref=subject, payload=view, secret=stray
        )
    assert stray_secret.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert len(stray) == len(_TYPED_INPUT) and not any(stray)

    operations = OperationsDestinationV1(client, OperationCatalogueSourceV1(lambda: registry))
    listing = operations(TuiScreenContextV1(destination=OPERATIONS_DESTINATION))
    assert isinstance(listing, OperationsCatalogueScreen)
    app = ScreenHostApp[None](listing)
    async with app.run_test(size=(140, 60)) as pilot:
        await _until(pilot, lambda: listing._catalogue is not None)
        listed = listing.query_one("#operations-list", OptionList)

        def offered() -> list[str]:
            return [
                option.id for option in listed.options if option.id is not None and not option.id.startswith("family:")
            ]

        # Every registered operation is listed, under one family heading each.
        assert sorted(offered()) == registered
        headings = [option for option in listed.options if option.id is not None and option.id.startswith("family:")]
        assert len(headings) == len({definition_id.split(".", 1)[0] for definition_id in registered})
        assert all(option.disabled for option in headings)
        search = listing.query_one("#operations-search", Input)
        search.value = _VIEW
        await _until(pilot, lambda: offered() == [_VIEW])
        search.value = ""
        await _until(pilot, lambda: len(offered()) == len(registered))

        # A read: the form refuses an incomplete request against its field, then runs the valid one.
        run = await _open(pilot, listing, _VIEW)
        assert _text(run.query_one(_field(run, "profile_id"), Static)) == str(client.profile_id)
        assert str(client.session_id) in _text(run.query_one("#operation-run-session", Static))
        run.query_one("#operation-run", Button).press()
        await pilot.pause(0.2)
        assert tr("tui.operations.form.invalid") in _text(run.query_one("#operation-run-notice", Static))
        page_kind_error = _field(run, "page_kind").replace("operation-field-", "operation-field-error-")
        assert _text(run.query_one(page_kind_error, Static))
        assert not _text(run.query_one("#operation-result-receipt", Static))
        run.query_one(_field(run, "page_kind"), Select).value = "status"
        await pilot.pause()
        assert _text(run.query_one("#operation-run-subject", Static)).endswith(f": {subject}")
        await _run(pilot, run)
        receipt = _text(run.query_one("#operation-result-receipt", Static))
        assert tr("operation.modal.terminal.succeeded") in receipt
        viewed = _result(run)
        assert viewed["profile_id"] == str(client.profile_id)
        assert viewed["page_kind"] == "status"
        assert not _text(run.query_one("#operation-result-stopped", Static))
        await _close(pilot, run, listing)

        # A change, entered through the whole-request JSON editor, and a read that observes it.
        run = await _open(pilot, listing, _RECIPIENT_ADD)
        run.query_one("#operation-toggle-json", Button).press()
        await pilot.pause()
        whole_request = run.query_one("#operation-json", TextArea)
        assert json.loads(whole_request.text) == {"profile_id": str(client.profile_id)}
        whole_request.load_text(
            json.dumps(
                {"profile_id": str(client.profile_id), "recipient_id": _RECIPIENT, "public_key_hex": _RECIPIENT_KEY}
            )
        )
        await _run(pilot, run)
        receipt = _text(run.query_one("#operation-result-receipt", Static))
        assert tr("operation.modal.terminal.succeeded") in receipt
        assert f"{tr('tui.operations.receipt.effect')}: updated" in receipt
        await _close(pilot, run, listing)

        run = await _open(pilot, listing, _RECIPIENT_LIST)
        await _run(pilot, run)
        assert tr("operation.modal.terminal.succeeded") in _text(run.query_one("#operation-result-receipt", Static))
        assert _RECIPIENT in json.dumps(_result(run))
        assert _RECIPIENT_KEY in json.dumps(_result(run))
        listed_by_form = _text(run.query_one("#operation-result-receipt", Static)).splitlines()[0].rsplit(": ", 1)[1]
        await _close(pilot, run, listing)

        # A replay key: the same key from the form names the same operation, no key starts another one, and an
        # operation that takes the typed operator input has no field to enter one in.
        run = await _open(pilot, listing, _RECIPIENT_LIST)
        run.query_one(_REPLAY_KEY_FIELD, Input).value = f"  {_REPLAY_KEY}  "
        await _run(pilot, run)
        first_keyed = _operation_id(run)
        await _close(pilot, run, listing)
        run = await _open(pilot, listing, _RECIPIENT_LIST)
        run.query_one(_REPLAY_KEY_FIELD, Input).value = _REPLAY_KEY
        await _run(pilot, run)
        assert _operation_id(run) == first_keyed
        await _close(pilot, run, listing)
        run = await _open(pilot, listing, _RECIPIENT_LIST)
        assert not run.query_one(_REPLAY_KEY_FIELD, Input).value
        await _run(pilot, run)
        unkeyed = _operation_id(run)
        assert unkeyed not in {first_keyed, listed_by_form}
        await _close(pilot, run, listing)
        run = await _open(pilot, listing, _TYPED_INPUT_OPERATION)
        assert not run.query(_REPLAY_KEY_FIELD)
        await _close(pilot, run, listing)

        # An operation with a one-shot secret: without the secret nothing is sent; with it, it travels and settles.
        run = await _open(pilot, listing, _GUARDED_OPERATION)
        secret_field = run.query_one("#operation-secret", Input)
        assert secret_field.password
        run.query_one(_field(run, "name"), Input).value = "synthetic-certificate-source"
        run.query_one("#operation-run", Button).press()
        await pilot.pause(0.2)
        assert tr("tui.operations.form.secret_required") in _text(run.query_one("#operation-run-notice", Static))
        assert not _text(run.query_one("#operation-result-receipt", Static))
        secret_field.value = _TYPED_INPUT
        await _run(pilot, run)
        assert secret_field.value == ""
        assert _TYPED_INPUT not in _rendered(app)
        assert [len(buffer) for buffer in secret_buffers] == [0, len(_TYPED_INPUT.encode())]
        assert not any(secret_buffers[1])
        # The runtime took the secret and ran the operation, which refuses a source this profile never registered.
        receipt = _text(run.query_one("#operation-result-receipt", Static))
        assert tr("operation.modal.terminal.refused") in receipt
        assert f"{tr('operation.modal.detail.receipt_refusal')}: REFUSED_AUTH_CERTIFICATE_SOURCE_NOT_FOUND" in receipt
        assert f"{tr('tui.operations.receipt.effect')}: none" in receipt
        assert run._pages == ()
        assert not _text(run.query_one("#operation-run-notice", Static))
        await _close(pilot, run, listing)
        listing.action_back()

    # The MCP execute tool, given the same request, names the same operation subject as the form did.
    executed = await asyncio.to_thread(
        call_admitted_operation,
        _McpConnection(client),
        "execute",
        {"definition_id": _RECIPIENT_LIST, "payload": {"profile_id": str(client.profile_id)}},
    )
    assert executed["outcome"] == "submitted"
    by_mcp = await _settled_projection(client, executed["receipt"]["operation_id"])
    by_form = await _settled_projection(client, listed_by_form)
    assert by_mcp.operation_id != by_form.operation_id
    assert (by_mcp.definition_id, by_mcp.subject_ref) == (by_form.definition_id, by_form.subject_ref)
    assert (by_form.definition_id, by_form.subject_ref) == (_RECIPIENT_LIST, subject)

    # The palette offers every registered operation and opens the destination on the chosen one.
    host = _PaletteHost(_destinations(operations))
    async with host.run_test() as palette_pilot:
        provider = WorkbenchOperationProviderV1(host.screen)
        hits = [hit async for hit in provider.search(".") if isinstance(hit, Hit)]
        assert sorted(str(hit.text).split("  ", 1)[0] for hit in hits) == registered
        chosen = next(hit for hit in hits if str(hit.text).split("  ", 1)[0] == _RECIPIENT_LIST)
        command = chosen.command
        assert callable(command)
        command()
        await palette_pilot.pause()
    (target,) = host.targets
    opened = host.destination_catalogue.create_screen(target)
    assert isinstance(opened, OperationsCatalogueScreen)
    focused = ScreenHostApp[None](opened)
    async with focused.run_test(size=(140, 60)) as focused_pilot:
        await _until(focused_pilot, lambda: isinstance(focused.screen, OperationRunScreen))
        assert _text(focused.screen.query_one("#operation-run-title", Static)) == _RECIPIENT_LIST


def test_every_registered_operation_is_listed_and_a_read_a_change_and_a_secret_run_on_a_real_runtime(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    caplog.set_level(logging.DEBUG)
    secret_buffers: list[bytearray] = []
    take_secret = OperationRunScreen._take_secret

    def observed_take_secret(screen: OperationRunScreen) -> bytearray | None:
        taken = take_secret(screen)
        if taken is not None:
            secret_buffers.append(taken)
        return taken

    monkeypatch.setattr(OperationRunScreen, "_take_secret", observed_take_secret)

    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsRuntimeEndpoint(storage_root=storage_root)
    installation = runtime_installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation.installation_id
    ) as subject:
        requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
        subject.owner.requesting = requester
        subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
            requester=requester, secrets_store=subject.client_native
        )
        enrollment_request = uuid4()
        subject.service.request(enrollment_request, subject.proposal)
        subject.approve(enrollment_request)
        profile_id = subject.store.binding.profile_id
        close_active_bucket_session()

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
        registry = build_production_operation_registry()
        with override_settings(cadrumo_local_storage_root=storage_root), ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    client = RuntimeFrontendClient(
                        _connect(endpoint), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    cleanup.callback(client.close)
                    proof = bytearray(PROFILE_INPUT.encode())
                    client.login_password(proof, timeout=25)
                    assert not any(proof)
                    asyncio.run(_journey(client, registry, secret_buffers))
            finally:
                primary = sys.exception()
                stop.set()
                try:
                    try:
                        running.result(timeout=20)
                    except Exception:
                        if primary is None:
                            raise
                finally:
                    endpoint.close()

    logged = "\n".join(f"{record.getMessage()} {record.__dict__!r}" for record in caplog.records)
    assert caplog.records
    assert _TYPED_INPUT not in logged
