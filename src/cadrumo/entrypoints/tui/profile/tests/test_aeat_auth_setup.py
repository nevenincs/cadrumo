"""Authentication editing and persisted-readback gates on both synchronization surfaces."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import override
from uuid import uuid4

import pytest
from textual.widgets import Button, Input, Select, Static

from .....application.auth.sync_readiness import AuthSyncReadiness, AuthSyncRequirement
from .....application.user_profile.overview import ProfileFieldView, ProfileOverview, ProfileSectionView
from .....core.auth_provider import AuthProviderKind, ClaveMovilRoute
from .....core.i18n.render import tr
from .....domain.user_profile.values import ProfileSetupState
from ...components.host import ScreenHostApp
from ...components.widgets import DisclosureGroup
from ..aeat_auth_setup import AeatAuthSetupScreen, readiness_text
from ..auth_fields import AeatAuthFieldSaveError
from ..overview import ProfileManagerScreen

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
        self.snapshot_calls = 0
        self.readiness_calls = 0

    async def read_readiness(self) -> AuthSyncReadiness:
        self.readiness_calls += 1
        if self.fail_read:
            raise RuntimeError("private provider diagnostics must stay private")
        return self.readiness

    async def snapshot(self) -> tuple[ProfileOverview, AuthSyncReadiness]:
        self.snapshot_calls += 1
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
        self.overview = _overview(fields, self.overview.record_revision + 1).model_copy(
            update={"profile_id": self.overview.profile_id}
        )
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
        assert door.snapshot_calls == 0
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
        assert door.snapshot_calls == 2  # editor load and saved readback only
        assert not screen.query_one("#source-censal_review Button", Button).disabled
        assert not launched
        door.fail_read = True
        await screen._refresh_auth()
        assert screen.query_one("#source-censal_review Button", Button).disabled
        assert "private provider" not in str(screen.query_one("#manager-auth-readiness", Static).render())


@pytest.mark.asyncio
async def test_returned_editor_projection_cannot_replace_a_newer_or_different_profile() -> None:
    door = _Door()
    current = door.overview.model_copy(update={"record_revision": 5})
    screen = ProfileManagerScreen(current, persist=lambda *_args: current, aeat_auth_setup=door)
    async with ScreenHostApp(screen).run_test(size=(110, 65)) as pilot:
        await pilot.pause()
        await screen._reload_auth(
            (current.model_copy(update={"record_revision": 2}), _readiness("clave_movil", ready=True))
        )
        assert screen.overview is current
        assert screen._auth_readiness is not None and not screen._auth_readiness.ready
        assert door.snapshot_calls == 0
        await screen._reload_auth((_overview({}, revision=6), _readiness("clave_movil", ready=True)))
        assert screen.overview is current
        assert screen._auth_readiness is None




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
