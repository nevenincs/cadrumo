"""Walk the production profile wizard against native workers and encrypted storage."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from uuid import UUID

import pytest
from dev.acceptance.income_tax.installed_tui_child import register_profile_through_installed_tui
from textual.pilot import Pilot
from textual.widgets import Button, Input, OptionList, Select, Static

from cadrumo.adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.core.bucket_pointer import require_active_bucket_id
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.user_profile.values import ProfileSetupState
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.profile.aeat_auth_setup import AeatAuthSetupScreen
from cadrumo.entrypoints.tui.profile.edit_screens import FieldEditScreen
from cadrumo.entrypoints.tui.profile.runtime_manager import RuntimeProfileManagerComposition
from cadrumo.entrypoints.tui.profile.setup_journey import ProfileSetupStage
from cadrumo_client.contracts.contracts import ClientHello
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.frontend_client import FrontendClient
from cadrumo_client.transport.windows import WindowsEndpoint
from cadrumo_runtime.commands.tests.runtime_profile_cli_fixture import (
    native_cli_profile_scope,
    native_cli_profile_server,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.windows_only]

_ANSWERS = {
    "identity.name": "Wizard",
    "identity.surnames": "Journey",
    "tax_residence.ccaa": "madrid",
    "tax_residence.jurisdiction_scope": "common_regime",
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "trabajo",
    "taxpayer_type.fiscal_residency": "resident_irpf",
    "activities.description": "Wizard verification",
    "irpf.estimation_regime": "directa_normal",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    "provenance.source": "manual_cli",
    "preferences.output_language": "en",
}


async def _until(pilot: Pilot, condition: Callable[[], bool], stage: str) -> None:
    print(f"Wizard step: {stage}", flush=True)
    deadline = time.monotonic() + 90
    while not condition():
        if time.monotonic() >= deadline:
            raise AssertionError(f"Wizard did not finish step: {stage}")
        await pilot.pause(0.05)


async def _click(pilot: Pilot, selector: str) -> None:
    button = pilot.app.screen.query_one(selector, Button)
    button.scroll_visible(immediate=True)
    await pilot.pause()
    assert await pilot.click(button), f"Wizard control could not be clicked: {selector}"


async def _walk(client: FrontendClient, label: str) -> None:
    composition = RuntimeProfileManagerComposition(client, profile_label=label, output_language=OutputLanguage.EN)
    screen = await asyncio.to_thread(composition.compose)
    async with ScreenHostApp(screen).run_test(size=(160, 60)) as pilot:
        await _until(pilot, lambda: screen.query_one("#onboarding-continue", Button).is_attached, "overview")
        assert screen.overview.setup_state is ProfileSetupState.INCOMPLETE
        assert screen._setup_stage is ProfileSetupStage.OVERVIEW
        await _click(pilot, "#onboarding-continue")
        await _until(pilot, lambda: screen._setup_stage is ProfileSetupStage.GET_DATA, "get data")
        await _until(pilot, lambda: screen._auth_readiness is not None, "initial authentication requirements")
        assert screen.query_one("#source-censal_review Button", Button).disabled
        await _click(pilot, "#manager-auth-edit")
        await _until(pilot, lambda: isinstance(pilot.app.screen, AeatAuthSetupScreen), "open authentication")
        editor = pilot.app.screen
        assert isinstance(editor, AeatAuthSetupScreen)
        await _until(pilot, lambda: not editor.query_one("#aeat-auth-save", Button).disabled, "load saved settings")
        editor.query_one("#aeat-auth-method", Select).value = "clave_movil"
        editor.query_one("#aeat-auth-route", Select).value = "app_request"
        editor.query_one("#aeat-auth-field-0", Input).value = "12345678Z"
        editor.query_one("#aeat-auth-field-1", Input).value = "12345678Z"
        await _click(pilot, "#aeat-auth-save")
        await _until(pilot, lambda: not editor._busy, "save incomplete authentication")
        assert editor._snapshot is not None
        assert not editor._snapshot[1].ready
        assert any(
            item.field == "auth.fecha_validez" and not item.satisfied for item in editor._snapshot[1].requirements
        )
        editor.query_one("#aeat-auth-field-2", Input).value = "not-a-date"
        await _click(pilot, "#aeat-auth-save")
        await _until(pilot, lambda: not editor._busy, "reject invalid validity date")
        assert str(editor.query_one("#aeat-auth-message", Static).render()).strip()
        assert not editor._snapshot[1].ready
        editor.query_one("#aeat-auth-field-2", Input).value = "2030-01-01"
        await _click(pilot, "#aeat-auth-save")
        await _until(pilot, lambda: not editor._busy, "save complete authentication")
        assert editor._snapshot is not None and editor._snapshot[1].ready, str(
            editor.query_one("#aeat-auth-message", Static).render()
        )
        await _click(pilot, "#aeat-auth-close")
        await _until(pilot, lambda: pilot.app.screen is screen, "return to get data")
        await _until(
            pilot, lambda: not screen.query_one("#source-censal_review Button", Button).disabled, "enable sync"
        )
        await _click(pilot, "#manager-auth-edit")
        await _until(pilot, lambda: isinstance(pilot.app.screen, AeatAuthSetupScreen), "reopen authentication")
        reopened = pilot.app.screen
        assert isinstance(reopened, AeatAuthSetupScreen)
        await _until(pilot, lambda: reopened._snapshot is not None, "reload persisted authentication")
        assert reopened._snapshot is not None and reopened._snapshot[1].ready
        assert reopened.query_one("#aeat-auth-method", Select).value == "clave_movil"
        assert reopened.query_one("#aeat-auth-route", Select).value == "app_request"
        await _click(pilot, "#aeat-auth-close")
        await _until(pilot, lambda: pilot.app.screen is screen, "return from reopened authentication")
        await _click(pilot, "#onboarding-continue")
        await _until(pilot, lambda: screen._setup_stage is ProfileSetupStage.REQUIRED, "required answers")
        print("wizard required fields:", ", ".join(screen.overview.missing_required))
        await _click(pilot, "#onboarding-continue")
        for _ in range(50):
            await _until(
                pilot,
                lambda: (
                    isinstance(pilot.app.screen, FieldEditScreen)
                    or (screen._pending_write is None and not screen.overview.missing_required)
                ),
                "next required answer",
            )
            if not isinstance(pilot.app.screen, FieldEditScreen):
                break
            dialog = pilot.app.screen
            field = dialog._field
            assert field.path in _ANSWERS, f"No verified answer supplied for wizard field {field.path}"
            answer = _ANSWERS[field.path]
            if field.choices:
                values = [choice.value for choice in field.choices]
                assert answer in values, f"Wizard field {field.path} has different choices: {values}"
                dialog.query_one("#edit-options", OptionList).highlighted = values.index(answer)
            else:
                dialog.query_one("#edit-input", Input).value = answer
            await _click(pilot, "#btn-edit-save")
            await pilot.pause()
        assert not screen.overview.missing_required, screen.overview.missing_required
        await _until(pilot, lambda: screen._setup_stage is ProfileSetupStage.REVIEW, "review")
        assert screen.overview.setup_state is ProfileSetupState.INCOMPLETE
        await _click(pilot, "#onboarding-continue")
        await _until(pilot, lambda: screen.overview.setup_state is ProfileSetupState.COMPLETE, "finish setup")
        assert screen._setup_stage is ProfileSetupStage.READY


def test_native_wizard_registration_authentication_and_completion(
    tmp_path: Path, authority_operation: PinnedAuthorityOperation
) -> None:
    """Create through the screen, save through native operations, and finish the wizard."""
    assert sys.platform == "win32"
    with native_cli_profile_scope(tmp_path) as profile:
        label = "Wizard step verification"
        asyncio.run(register_profile_through_installed_tui(profile_label=label, passphrase=profile.passphrase))
        profile_id = UUID(require_active_bucket_id())
        close_active_bucket_session()
        with native_cli_profile_server(profile.storage_root):
            endpoint = WindowsEndpoint(storage_root=profile.storage_root)
            connection = VerifiedConnection(
                endpoint.connect(timeout=10),
                expected=ClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
                deadline=time.monotonic() + 10,
            )
            client = FrontendClient(connection, profile_id=profile_id, frontend=OperationFrontendProjection.TUI)
            try:
                client.login_password(bytearray(profile.passphrase, "utf-8"))
                asyncio.run(_walk(client, label))
            finally:
                client.close()
