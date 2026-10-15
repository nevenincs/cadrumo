"""An API-key session reaches the operations, the installation acts and the reference from its shell.

One native runtime serves the journey under a real API key whose scope admits
one read operation. The shell lists every registered operation, the runtime
runs the one the scope admits and refuses another in its own words, an
installation act answers on its sessionless connection, and a reference read
answers from the published authority.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from importlib.metadata import version
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest
from textual.pilot import Pilot
from textual.widgets import Button, OptionList, Select, Static

from cadrumo.adapters.persistence.storage.custody.tests.enrollment_support import (
    AdministrationSubject,
    administration_subject,
    changed,
)
from cadrumo.adapters.persistence.storage.custody.tests.native_enrollment_recipient import NativeEnrollmentRecipient
from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from cadrumo.application.operations.registry import OperationFrontendProjection, OperationRegistry
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessScope,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    LoginEligibility,
    OsLockState,
    OsLoginContext,
    SessionKind,
)
from cadrumo.core.config import override_settings
from cadrumo.core.errors.error_codes import resolve_error_message
from cadrumo.core.errors.hierarchy import CadrumoError
from cadrumo.core.i18n.render import tr
from cadrumo.entrypoints.operation_composition import build_production_operation_registry
from cadrumo.entrypoints.tui.account import AccountRecomposeRequiredV1
from cadrumo.entrypoints.tui.components.status import PinnedStatusBar
from cadrumo.entrypoints.tui.installation.act_screen import InstallationActScreen
from cadrumo.entrypoints.tui.installation.destination import InstallationScreen
from cadrumo.entrypoints.tui.operations.destination import OperationsCatalogueScreen
from cadrumo.entrypoints.tui.operations.run_screen import OperationRunScreen
from cadrumo.entrypoints.tui.reference.destination import ReferenceScreen
from cadrumo.entrypoints.tui.reference.read_screen import ReferenceReadScreen
from cadrumo.entrypoints.tui.reference.reads import ReferenceQuery, ReferenceRead, read_reference
from cadrumo.entrypoints.tui.runtime_session import RuntimeRestrictedSessionApp
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.contracts.installation_requests import InstallationAct, StorageCheckRequest
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.installation import installation
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.adapters.tests.profile_worker_support import owner_id
from cadrumo_runtime.adapters.tests.retained_server import RetainedRuntimeTransportServer
from cadrumo_runtime.host.installation_composition import InstallationActRegistry
from cadrumo_runtime.host.profile_connections import RuntimeProfileConnections
from cadrumo_runtime.host.tests.installation_runtime import serve_check

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires real native profile workers"),
    pytest.mark.usefixtures("authority_operation"),
]

_ADMITTED = "user-profile.view"
_OUT_OF_SCOPE = "config.collab.recipient.list"
_SETTLE_SECONDS = 180
_SIZE = (140, 60)

type _Pilot = Pilot[AccountRecomposeRequiredV1 | None]


class _LoginObservation:
    login_id = "tui-restricted-destinations-native-login"

    def observe(self, *, credential_facilities: Availability) -> OsLoginContext:
        return OsLoginContext(
            login_id=self.login_id,
            os_owner_id=owner_id(),
            active=True,
            lock_state=OsLockState.UNLOCKED,
            unattended=LoginEligibility.ELIGIBLE,
            credential_facilities=credential_facilities,
        )


def _connect(endpoint: WindowsEndpoint) -> VerifiedConnection:
    return VerifiedConnection(
        endpoint.connect(timeout=3),
        expected=ClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
        deadline=time.monotonic() + 3,
    )


def _scope(destination_id: UUID, registry: OperationRegistry) -> AccessScope:
    """A scope that admits exactly one read operation and the reading of its result."""
    result_schema = registry.lookup_public_contract(_ADMITTED).result_schema
    assert result_schema is not None
    return AccessScope(
        operations=frozenset({_ADMITTED}),
        actions=frozenset(AccessAction),
        disclosures=frozenset(
            {
                DisclosurePermission(
                    destination_id=destination_id,
                    projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
                    category=DisclosureCategory.OPERATION_METADATA,
                ),
                DisclosurePermission(
                    destination_id=destination_id,
                    projection_id=result_schema.schema_id,
                    category=DisclosureCategory.PROFILE_VALUES,
                ),
            }
        ),
        periods=None,
        allow_period_independent=True,
        allow_delegation=False,
    )


def _issue_scoped_key(subject: AdministrationSubject, registry: OperationRegistry) -> bytes:
    requester = changed(subject.owner.requesting, destination_id=subject.owner.requesting.client_id)
    subject.owner.requesting = requester
    subject.owner.delivery.endpoint = NativeEnrollmentRecipient(
        requester=requester, secrets_store=subject.client_native
    )
    scope = _scope(requester.client_id, registry)
    facts = subject.owner.current
    assert facts.session is not None
    subject.owner.current = changed(
        facts, profile=changed(facts.profile, scope=scope), session=changed(facts.session, scope=scope)
    )
    request_id = uuid4()
    subject.service.request(request_id, changed(subject.proposal, scope=scope))
    receipt = subject.approve(request_id)
    record = next(item for item in subject.store.enrollment_state().requests if item.request_id == request_id)
    credential = subject.owner.delivery.endpoint.possession(record)
    assert receipt.key_id is not None and credential is not None
    return credential.get_secret_value()


async def _until(pilot: _Pilot, predicate: Callable[[], bool], *, seconds: float = 40) -> None:
    async with asyncio.timeout(seconds):
        while not predicate():
            await pilot.pause(0.05)


def _text(widget: Static) -> str:
    return str(widget.content)


async def _open_operation(pilot: _Pilot, listing: OperationsCatalogueScreen, definition_id: str) -> OperationRunScreen:
    listed = listing.query_one("#operations-list", OptionList)
    listed.highlighted = listed.get_option_index(definition_id)
    listed.action_select()
    await _until(
        pilot,
        lambda: isinstance(pilot.app.screen, OperationRunScreen) and bool(pilot.app.screen.query("#operation-run")),
    )
    run = pilot.app.screen
    assert isinstance(run, OperationRunScreen)
    assert _text(run.query_one("#operation-run-title", Static)) == definition_id
    return run


async def _journey(client: FrontendClient, registry: OperationRegistry, storage_root: Path) -> None:
    registered = sorted(contract.definition_id for contract in registry.public_contract_set.definitions)
    app = RuntimeRestrictedSessionApp(client, profile_label="Enrollment tests", operation_registry=lambda: registry)
    async with app.run_test(size=_SIZE) as pilot:
        await _until(pilot, lambda: str(client.profile_id) in _text(app.query_one("#restricted-profile", Static)))
        shell = app.screen
        assert _ADMITTED in _text(app.query_one("#restricted-operations", Static))
        assert _OUT_OF_SCOPE not in _text(app.query_one("#restricted-operations", Static))

        # Operations: every registered operation is listed, whatever the key's scope says.
        app.query_one("#restricted-open-operations", Button).press()
        await _until(
            pilot, lambda: isinstance(app.screen, OperationsCatalogueScreen) and app.screen._catalogue is not None
        )
        listing = app.screen
        assert isinstance(listing, OperationsCatalogueScreen)
        offered = sorted(
            option.id
            for option in listing.query_one("#operations-list", OptionList).options
            if option.id is not None and not option.id.startswith("family:")
        )
        assert offered == registered and _OUT_OF_SCOPE in offered

        # The read the scope admits runs, and its typed result is shown.
        run = await _open_operation(pilot, listing, _ADMITTED)
        page_kind = f"#operation-field-{[field.name for field in run._fields].index('page_kind')}"
        run.query_one(page_kind, Select).value = "status"
        await pilot.pause()
        run.query_one("#operation-run", Button).press()
        receipt = run.query_one("#operation-result-receipt", Static)
        await _until(
            pilot,
            lambda: app.screen is run and bool(_text(receipt)) and all(worker.is_finished for worker in run.workers),
            seconds=_SETTLE_SECONDS,
        )
        assert tr("operation.modal.terminal.succeeded") in _text(receipt)
        assert run._pages, _text(run.query_one("#operation-run-notice", Static))
        viewed = json.loads("\n".join(run._pages))
        assert viewed["profile_id"] == str(client.profile_id) and viewed["page_kind"] == "status"
        run.action_close()
        await _until(pilot, lambda: app.screen is listing)

        # An operation outside the scope is offered all the same, and the runtime refuses it in its own words.
        with pytest.raises(CadrumoError) as refused_directly:
            await asyncio.to_thread(client.contract, _OUT_OF_SCOPE, deadline=time.monotonic() + 30)
        runtime_words = resolve_error_message(refused_directly.value)
        assert runtime_words.strip()
        denied = await _open_operation(pilot, listing, _OUT_OF_SCOPE)
        notice = denied.query_one("#operation-run-notice", Static)
        denied.query_one("#operation-run", Button).press()
        await _until(pilot, lambda: bool(_text(notice)) and all(worker.is_finished for worker in denied.workers))
        assert _text(notice) == runtime_words
        assert not _text(denied.query_one("#operation-result-receipt", Static))
        denied.action_close()
        await _until(pilot, lambda: app.screen is listing)
        listing.action_back()
        await _until(pilot, lambda: app.screen is shell)

        # Installation: a read act answers on its own sessionless connection.
        app.query_one("#restricted-open-installation", Button).press()
        await _until(
            pilot, lambda: isinstance(app.screen, InstallationScreen) and bool(app.screen.query("#installation-hint"))
        )
        installation = app.screen
        assert isinstance(installation, InstallationScreen)
        installation.open_act(InstallationAct.STORAGE_CHECK)
        await _until(
            pilot,
            lambda: (
                isinstance(app.screen, InstallationActScreen) and bool(app.screen.query("#installation-act-result"))
            ),
        )
        check = app.screen
        assert isinstance(check, InstallationActScreen)
        status = check.query_one("#installation-act-status", PinnedStatusBar)
        await _until(pilot, lambda: status.tone in {"success", "error"})
        assert status.tone == "success", status.message
        assert str(storage_root) in _text(check.query_one("#installation-act-result", Static))
        check.action_close()
        await _until(pilot, lambda: app.screen is installation)
        installation.action_close()
        await _until(pilot, lambda: app.screen is shell)

        # Reference: a read answers from the published authority, with no session involved.
        app.query_one("#restricted-open-reference", Button).press()
        await _until(
            pilot, lambda: isinstance(app.screen, ReferenceScreen) and bool(app.screen.query("#reference-hint"))
        )
        reference = app.screen
        assert isinstance(reference, ReferenceScreen)
        reference.open_read(ReferenceRead.AUTH_PROVIDERS)
        await _until(pilot, lambda: isinstance(app.screen, ReferenceReadScreen) and app.screen.result is not None)
        providers = app.screen
        assert isinstance(providers, ReferenceReadScreen) and providers.result is not None
        assert providers.result.model_dump(mode="json") == read_reference(
            ReferenceQuery(ReferenceRead.AUTH_PROVIDERS)
        ).model_dump(mode="json")
        providers.action_close()
        await _until(pilot, lambda: app.screen is reference)
        reference.action_close()
        await _until(pilot, lambda: app.screen is shell)

        # The shell is still the admitted API session it was.
        assert not app._cleared and app.return_value is None
        await pilot.click("#restricted-close")


def test_an_api_key_session_runs_an_admitted_read_is_refused_another_and_reaches_installation_and_reference(
    tmp_path: Path,
) -> None:
    storage_root = tmp_path / "cadrumo-storage"
    storage_root.mkdir()
    endpoint = WindowsEndpoint(storage_root=storage_root)
    installation_identity = installation(
        storage_root=storage_root, os_owner_id=owner_id(), storage_identity=endpoint.storage_identity
    )
    registry = build_production_operation_registry()
    acts = InstallationActRegistry()
    acts.register(StorageCheckRequest, serve_check)
    with administration_subject(
        tmp_path, os_owner_id=owner_id(), installation_id=installation_identity.installation_id
    ) as subject:
        api_key = _issue_scoped_key(subject, registry)
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
            installation_acts=acts,
        )
        profiles.prepare_registry()
        server = RetainedRuntimeTransportServer(
            endpoint, product_version=version("cadrumo"), stop=stop, profiles=profiles, boot_id=boot
        )
        with override_settings(cadrumo_local_storage_root=storage_root), ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(server.serve)
            try:
                assert server.ready.wait(3)
                with ExitStack() as cleanup:
                    client = FrontendClient(
                        _connect(endpoint), profile_id=profile_id, frontend=OperationFrontendProjection.TUI
                    )
                    cleanup.callback(client.close)
                    proof = bytearray(api_key)
                    admitted = client.login_api_key(proof, timeout=25)
                    assert not any(proof) and admitted.status.grant_valid
                    assert admitted.status.effective_scope.operations == frozenset({_ADMITTED})
                    assert SessionKind.API_KEY.value == "api_key"
                    asyncio.run(_journey(client, registry, storage_root))
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
