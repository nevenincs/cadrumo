"""Authentication editing and persisted-readback gates on both synchronization surfaces."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import cast, override
from uuid import uuid4

import pytest
from pydantic import BaseModel
from textual.widgets import Button, Input, Select, Static

from cadrumo_client.transport.frontend_client import FrontendClient

from .....application.auth.credential_operations import AuthCredentialSaveResult
from .....application.auth.operation_definitions import AuthConfigureOperationRequest
from .....application.auth.provider_configure_operation_access import AuthConfigurePublicResultV2
from .....application.auth.sync_readiness import AuthSyncReadiness, AuthSyncRequirement
from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from .....core.i18n.render import tr
from .....domain.user_profile.values import ProfileSetupState
from ...components.host import ScreenHostApp
from ...components.widgets import DisclosureGroup
from .. import runtime_aeat_auth
from ..aeat_auth_setup import AeatAuthSetupScreen, readiness_text
from ..overview import ProfileManagerScreen
from ..runtime_aeat_auth import AeatAuthFieldSaveError, RuntimeAeatAuthSetup

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_PATHS = ("identity.tax_id", "auth.dni_nie", "auth.fecha_validez", "auth.numero_soporte")


def _overview(values: Mapping[str, str], revision: int = 1) -> ProfileOverview:
    return ProfileOverview(
        profile_id=str(uuid4()),
        label="Selected profile",
        record_revision=revision,
        content_digest="a" * 64,
        setup_state=ProfileSetupState.INCOMPLETE,
        sections=(
            ProfileSectionView(
                key="identity",
                title="Identity",
                summary="",
                repeatable=False,
                fields=tuple(
                    ProfileFieldView(path=path, label=path, value=values.get(path), masked=False, required=True)
                    for path in _PATHS
                ),
            ),
        ),
    )


def _readiness(provider: str = "", *, ready: bool = False) -> AuthSyncReadiness:
    return AuthSyncReadiness(
        provider=provider,
        ready=ready,
        route="app_request" if provider == "clave_movil" else "",
        requirements=(
            AuthSyncRequirement(field="identity.tax_id", satisfied=ready, reason="profile_tax_id_required"),
            AuthSyncRequirement(field="auth.provider", satisfied=bool(provider), reason="auth_method_required"),
        ),
    )


class _Door:
    def __init__(self) -> None:
        self.overview = _overview({})
        self.readiness = _readiness()
        self.calls: list[tuple[AuthProviderKind, ClaveMovilRoute, dict[str, str], str, bytes | None]] = []
        self.fail_read = False

    async def snapshot(self) -> tuple[ProfileOverview, AuthSyncReadiness]:
        if self.fail_read:
            raise RuntimeError("private provider diagnostics must stay private")
        return self.overview, self.readiness

    async def save(
        self,
        provider: AuthProviderKind,
        route: ClaveMovilRoute,
        fields: dict[str, str],
        certificate_path: str,
        secret: bytearray | None,
    ) -> tuple[ProfileOverview, AuthSyncReadiness]:
        self.calls.append(
            (provider, route, fields.copy(), certificate_path, bytes(secret) if secret is not None else None)
        )
        self.overview = _overview(fields, self.overview.record_revision + 1)
        self.readiness = _readiness(provider.value, ready=True)
        return await self.snapshot()


@pytest.mark.asyncio
async def test_editor_processes_input_while_native_snapshot_is_pending() -> None:
    """A pending runtime read must not hold the screen's message queue."""
    loaded = asyncio.Event()

    class PendingDoor(_Door):
        @override
        async def snapshot(self) -> tuple[ProfileOverview, AuthSyncReadiness]:
            await loaded.wait()
            return await super().snapshot()

    screen = AeatAuthSetupScreen(PendingDoor())
    async with ScreenHostApp(screen).run_test(size=(100, 55)) as pilot:
        await pilot.pause()
        assert screen.query_one("#aeat-auth-save", Button).disabled
        assert await pilot.press("escape") is None
        assert pilot.app.screen is not screen
        loaded.set()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", list(AuthProviderKind))
async def test_method_specific_editor_saves_then_reopens_stored_fields_and_hides_password(
    provider: AuthProviderKind,
) -> None:
    door = _Door()
    screen = AeatAuthSetupScreen(door)
    async with ScreenHostApp(screen).run_test(size=(100, 55)) as pilot:
        await pilot.pause()
        methods = screen.query_one("#aeat-auth-method", Select)
        assert (tr(f"auth.catalogue.{provider.value}_label"), provider.value) in methods._options
        routes = screen.query_one("#aeat-auth-route", Select)
        assert (tr("flows.manager.action.auth_clave_movil_route_qr"), "qr") in routes._options
        assert (tr("flows.manager.action.auth_clave_movil_route_app_request"), "app_request") in routes._options
        screen.query_one("#aeat-auth-method", Select).value = provider.value
        await pilot.pause()
        screen.query_one("#aeat-auth-field-0", Input).value = "12345678Z"
        secret = screen.query_one("#aeat-auth-secret", Input)
        assert secret.password
        assert secret.display is (provider is not AuthProviderKind.CLAVE_MOVIL)
        assert screen.query_one("#aeat-auth-route").display is (provider is AuthProviderKind.CLAVE_MOVIL)
        assert screen.query_one("#aeat-auth-path").display is (provider is AuthProviderKind.CERTIFICATE)
        if secret.display:
            secret.value = "private-password-sentinel"
        save = screen.query_one("#aeat-auth-save", Button)
        save.scroll_visible(immediate=True)
        await pilot.pause()
        assert await pilot.click(save)
        await pilot.pause()
        assert door.calls[-1][0] is provider
        assert door.calls[-1][2]["identity.tax_id"] == "12345678Z"
        assert secret.value == ""
        assert tr("tui.aeat_auth.ready") in str(screen.query_one("#aeat-auth-readiness", Static).render())
        assert "private-password-sentinel" not in " ".join(str(widget.render()) for widget in screen.query(Static))
    reopened = AeatAuthSetupScreen(door)
    async with ScreenHostApp(reopened).run_test(size=(100, 55)) as pilot:
        await pilot.pause()
        assert reopened.query_one("#aeat-auth-field-0", Input).value == "12345678Z"
        assert reopened.query_one("#aeat-auth-method", Select).value == provider.value
        assert reopened.query_one("#aeat-auth-secret", Input).value == ""


@pytest.mark.asyncio
async def test_profile_acquisition_stays_blocked_until_editor_saved_and_readback_is_ready() -> None:
    door = _Door()
    launched: list[str] = []

    async def launch(source: object) -> None:
        launched.append(str(source))

    screen = ProfileManagerScreen(
        door.overview, persist=lambda *_args: door.overview, launch_source=launch, aeat_auth_setup=door
    )
    async with ScreenHostApp(screen).run_test(size=(110, 65)) as pilot:
        await pilot.pause()
        screen.query_one("#manager-sources-fold", DisclosureGroup).collapsed = False
        await pilot.pause()
        source = screen.query_one("#source-censal_review Button", Button)
        assert source.disabled
        assert tr("tui.aeat_auth.blocked") in str(screen.query_one("#manager-auth-readiness", Static).render())
        edit = screen.query_one("#manager-auth-edit", Button)
        edit.scroll_visible(immediate=True)
        await pilot.pause()
        assert await pilot.click(edit)
        await pilot.pause()
        assert isinstance(screen.app.screen, AeatAuthSetupScreen)
        editor = screen.app.screen
        editor.query_one("#aeat-auth-method", Select).value = "clave_movil"
        editor.query_one("#aeat-auth-field-0", Input).value = "12345678Z"
        await editor._save()
        editor.action_close()
        await pilot.pause()
        assert not screen.query_one("#source-censal_review Button", Button).disabled
        assert not launched
        door.fail_read = True
        await screen._refresh_auth()
        assert screen.query_one("#source-censal_review Button", Button).disabled
        assert "private provider" not in str(screen.query_one("#manager-auth-readiness", Static).render())


@pytest.mark.asyncio
async def test_runtime_setup_serializes_cas_writes_keeps_secrets_off_profile_and_rereads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = cast("FrontendClient", type("Client", (), {"profile_id": uuid4(), "session_id": uuid4()})())
    values: dict[str, str] = {}
    revision = [1]
    calls: list[tuple[str, int]] = []
    configured: list[AuthConfigureOperationRequest] = []
    secrets: list[bytes] = []

    def overview() -> ProfileOverview:
        return _overview(values, revision[0])

    def persist(path: str, value: str, expected: int, _digest: str) -> ProfileOverview:
        assert expected == revision[0]
        calls.append((path, expected))
        values[path] = value
        revision[0] += 1
        return overview()

    def configure(_client: FrontendClient, request: AuthConfigureOperationRequest) -> AuthConfigurePublicResultV2:
        assert request.expected_profile_revision == revision[0]
        configured.append(request)
        return AuthConfigurePublicResultV2(
            profile_id=client.profile_id,
            provider=request.provider,
            changed=True,
            certificate_file_provided=False,
            complete=False,
            profile_tax_id_present=True,
            provider_identity_present=True,
            identity_alignment="matches",
        )

    async def operation(
        _client: FrontendClient,
        definition: str,
        payload: BaseModel,
        result_type: type[BaseModel],
        *,
        secret: bytearray | None = None,
    ) -> AuthCredentialSaveResult:
        assert definition == "auth.credential.save"
        assert "private-password" not in payload.model_dump_json()
        assert secret is not None
        secrets.append(bytes(secret))
        return AuthCredentialSaveResult(provider="clave_permanente")

    async def readiness(_client: FrontendClient) -> AuthSyncReadiness:
        assert secrets and configured
        return _readiness("clave_permanente", ready=True)

    monkeypatch.setattr(runtime_aeat_auth, "configure_runtime_auth", configure)
    monkeypatch.setattr(runtime_aeat_auth, "run_auth_operation", operation)
    monkeypatch.setattr(runtime_aeat_auth, "read_runtime_sync_readiness", readiness)
    door = RuntimeAeatAuthSetup(client, overview=overview, persist=persist, pin=lambda: None)
    secret = bytearray(b"private-password")
    saved, result = await door.save(
        AuthProviderKind.CLAVE_PERMANENTE,
        ClaveMovilRoute.APP_REQUEST,
        {"identity.tax_id": "12345678Z", "auth.dni_nie": "12345678Z"},
        "",
        secret,
    )
    assert calls == [("identity.tax_id", 1), ("auth.dni_nie", 2)]
    assert saved.record_revision == 3 and result.ready
    assert json.loads(secrets[0]) == {"password": "private-password"}
    assert secret == bytes(len(secret))
    assert all("password" not in key for key in values)


def test_missing_requirements_are_human_readable_and_private_reasons_do_not_become_locale_keys() -> None:
    text = readiness_text(_readiness())
    assert "identity.tax_id" not in text
    assert "auth_method_required" not in text
    assert tr("tui.aeat_auth.blocked") in text


@pytest.mark.asyncio
async def test_invalid_field_reports_which_field_failed_without_disclosing_rejected_data() -> None:
    class RefusingDoor(_Door):
        @override
        async def save(
            self,
            provider: AuthProviderKind,
            route: ClaveMovilRoute,
            fields: dict[str, str],
            certificate_path: str,
            secret: bytearray | None,
        ) -> tuple[ProfileOverview, AuthSyncReadiness]:
            raise AeatAuthFieldSaveError("identity.tax_id") from ValueError("private rejected input sentinel")

    screen = AeatAuthSetupScreen(RefusingDoor())
    async with ScreenHostApp(screen).run_test(size=(100, 55)) as pilot:
        await pilot.pause()
        screen.query_one("#aeat-auth-method", Select).value = "clave_movil"
        await screen._save()
        message = str(screen.query_one("#aeat-auth-message", Static).render())
        assert tr("tui.aeat_auth.field_failed", field="identity.tax_id") in message
        assert "private rejected" not in message
        assert not screen.query_one("#aeat-auth-save", Button).disabled
