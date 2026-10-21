"""Live rewording keeps mounted screen, modal and staged edit identities."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import cast

import pytest
from textual.app import App
from textual.widgets import Button, DataTable, Input, Label, OptionList, Static

from cadrumo_client.transport.frontend_client import FrontendClient

from ....application.invoices.catalogue_add_operation import (
    build_invoice_add_definition,
    build_invoice_add_registration,
)
from ....application.invoices.catalogue_creation_ports import CatalogueCreationPortsFactory
from ....application.modelo.work_form_models import ModeloFormField
from ....application.operations.registry import OperationRegistry
from ....application.search.workbench import WorkbenchDestinationAdmissionState
from ....application.user_profile.language_resolver import adopt_profile_output_language, register_language_resolver
from ....application.user_profile.overview import ProfileFieldView
from ....core.config import override_settings
from ....core.credentials import assess_profile_password
from ....core.external_constants import OutputLanguage
from ....core.i18n.render import output_language, tr
from ..account import AccountFactoriesV1, ProfileLanguageInvalidated
from ..app import CadrumoTuiApp, RootPresentationV1
from ..components.dialogs import ConfirmScreen
from ..components.host import ScreenHostApp
from ..components.language import localized, refresh_localized_widgets
from ..components.theme import install_cadrumo_themes
from ..home import HomeScreen
from ..installation.destination import InstallationScreen
from ..modelo.workbench.casilla_list import CasillaList
from ..modelo.workbench.editor import CasillaEditorPanel, CasillaEditorScreen
from ..modelo.workbench.ports import WorkbenchParsed
from ..modelo.workbench.screen import ModeloWorkbenchScreen
from ..modelo.workbench.tests.workbench_fixture import FakeActions, FakeReader
from ..navigation import TUI_DESTINATION_CATALOGUE, TuiDestinationAdmissionV1, build_destination_catalogue
from ..operations.catalogue import OperationCatalogueSourceV1
from ..operations.destination import OperationsCatalogueScreen
from ..profile.edit_screens import FieldEditScreen
from ..reference.destination import ReferenceScreen
from ..secret.passphrase import PassphraseScreen
from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_hidden_home_and_open_modal_reword_without_replacing_input_or_selection() -> None:
    with override_settings(cadrumo_output_language=""):
        register_language_resolver()
        adopt_profile_output_language(OutputLanguage.EN)
        home = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.READY))
        callbacks: list[Callable[[], None]] = []
        attempts = 0

        def unused(*_args: object):
            raise AssertionError("no account action is part of language observation")

        def subscribe(callback: Callable[[], None]) -> Callable[[], None]:
            callbacks.append(callback)
            return lambda: callbacks.remove(callback)

        async def refresh() -> bool:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ConnectionError("transient language read")
            return adopt_profile_output_language(OutputLanguage.ES)

        factories = AccountFactoriesV1(
            profile=unused,
            change_user=unused,
            password=None,
            appearance=unused,
            language=unused,
            sign_out=unused,
            subscribe_language=subscribe,
            refresh_language=refresh,
        )
        app = CadrumoTuiApp(account_factories=factories)
        async with app.run_test(size=(140, 45)) as pilot:
            await app.push_screen(home)
            await pilot.pause()
            table = home.query_one("#home-actions", DataTable)
            table.move_cursor(row=1)
            selected = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            field = ProfileFieldView(
                path="identity.tax_id",
                label=tr("profile.schema.field.identity.tax_id.label"),
                value="",
                masked=False,
                required=True,
            )
            modal = FieldEditScreen(field)
            await app.push_screen(modal)
            await pilot.pause()
            control = modal.query_one("#edit-input", Input)
            control.value = "Unfinished name"
            control.cursor_position = 5
            focus = app.focused
            assert len(callbacks) == 1
            callbacks[0]()
            for _ in range(30):
                await pilot.pause(0.1)
                if attempts >= 2 and str(modal.query_one("#btn-edit-save", Button).label) == tr(
                    "flows.manager.edit.save", locale="es"
                ):
                    break
            assert attempts == 2
            assert output_language() == "es"
            assert str(modal.query_one("#btn-edit-save", Button).label) == tr("flows.manager.edit.save", locale="es")
            assert home.query_one(".cadrumo-banner", Static).content == tr("tui.home.title", locale="es")
            assert modal.query_one("#edit-label", Label).content == tr(
                "profile.schema.field.identity.tax_id.label", locale="es"
            )
            assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == selected
            assert app.focused is focus
            assert modal.query_one("#edit-input", Input) is control
            assert control.value == "Unfinished name"
            assert control.cursor_position == 5
        register_language_resolver()


@pytest.mark.asyncio
async def test_workbench_language_keeps_staged_typed_value_and_box_cursor() -> None:
    reader = FakeReader()
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(reader, actions=FakeActions())
        async with ScreenHostApp(screen).run_test(size=(140, 45)) as pilot:
            await pilot.pause()
            await pilot.pause()
            listing = screen.query_one(CasillaList)
            entry = listing.highlighted
            assert entry is not None
            assert screen._session.stage_value(entry.field, Decimal("1234.5"), "1,234.50") is None
            before = screen.staged_changes[0]
            loads = reader.loads
            with override_settings(cadrumo_output_language="es"):
                await screen.refresh_language()
                await pilot.pause()
                after = screen.staged_changes[0]
                assert after.change == before.change
                assert after.before_changed == before.before_changed
                assert screen.query_one(CasillaList) is listing
                assert listing.highlighted is not None and listing.highlighted.key == entry.key
                assert reader.loads == loads
                assert "1.234,50" in after.text


@pytest.mark.asyncio
async def test_copy_metadata_keeps_interpolation_and_leaves_newer_status_alone() -> None:
    with override_settings(cadrumo_output_language="en"):
        home = HomeScreen(build_home_projection_fixture(HomeFixtureScenario.READY))
        async with ScreenHostApp(home).run_test(size=(140, 45)) as pilot:
            copy = localized(
                Static(tr("tui.home.messages_summary", count=7), markup=True), "tui.home.messages_summary", count=7
            )
            status = localized(Static(tr("tui.modelo.workbench.loading")), "tui.modelo.workbench.loading")
            await home.mount(copy, status)
            status.update("ongoing operation detail")
            with override_settings(cadrumo_output_language="ca"):
                refresh_localized_widgets(home)
                await pilot.pause()
                assert copy.content == tr("tui.home.messages_summary", count=7)
                assert status.content == "ongoing operation detail"


@pytest.mark.asyncio
async def test_open_amount_draft_keeps_its_original_parse_locale_after_rewording() -> None:
    seen: list[OutputLanguage] = []

    def parse(field: ModeloFormField, text: str, language: OutputLanguage) -> WorkbenchParsed:
        del field
        seen.append(language)
        lexeme = text.replace(",", "") if language is OutputLanguage.EN else text.replace(".", "").replace(",", ".")
        value = Decimal(lexeme)
        return WorkbenchParsed(value=value, display=str(value))

    field = next(item for item in FakeReader().form.fields() if item.box == "06")
    with override_settings(cadrumo_output_language="en"):
        panel = CasillaEditorPanel(field, parse=parse, language=OutputLanguage.EN)
        screen = CasillaEditorScreen(panel)
        async with ScreenHostApp(screen).run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            control = panel.query_one("#editor-input", Input)
            control.value = "1,234"
            await pilot.pause()
            assert panel._parsed is not None and panel._parsed.value == Decimal("1234")
            before = panel._parsed
            with override_settings(cadrumo_output_language="es"):
                await screen.refresh_language()
                assert panel._parsed is before
                assert panel.query_one("#editor-input", Input) is control
                assert control.value == "1,234"
                control.focus()
                await pilot.press("end", "backspace", "4")
                await pilot.pause()
                assert control.value == "1,234"
                assert panel._parsed is not None and panel._parsed.value == Decimal("1234")
                assert seen and set(seen) == {OutputLanguage.EN}


@pytest.mark.asyncio
async def test_reference_list_rewords_rows_without_replacing_selection() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ReferenceScreen()
        async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            table = screen.query_one("#reference-reads", DataTable)
            table.move_cursor(row=2)
            identity = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            before = tuple(tuple(table.get_row_at(index)) for index in range(table.row_count))
            with override_settings(cadrumo_output_language="es"):
                await screen.refresh_language()
                await pilot.pause()
                assert screen.query_one("#reference-reads", DataTable) is table
                assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == identity
                assert tuple(tuple(table.get_row_at(index)) for index in range(table.row_count)) != before
                assert screen.query_one(".cadrumo-banner", Static).content == tr("tui.reference.title", locale="es")


@pytest.mark.asyncio
async def test_confirmation_resolves_canonical_copy_and_retains_pending_choice() -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ConfirmScreen(
            title=lambda: tr("tui.modelo.workbench.leave.title"),
            message=lambda: tr("tui.modelo.workbench.leave.message", count=7),
            confirm_label=lambda: tr("tui.modelo.workbench.leave.discard"),
            cancel_label=lambda: tr("tui.modelo.workbench.leave.stay"),
        )
        app = App[bool]()
        install_cadrumo_themes(app)
        async with app.run_test(size=(100, 35)) as pilot:
            await app.push_screen(screen)
            await pilot.pause()
            focused = screen.focused
            cancel = screen.query_one("#btn-confirm-cancel", Button)
            with override_settings(cadrumo_output_language="es"):
                await screen.refresh_language()
                await pilot.pause()
                assert screen.query_one("#confirm-message", Static).content == tr(
                    "tui.modelo.workbench.leave.message", count=7, locale="es"
                )
                assert str(cancel.label) == tr("tui.modelo.workbench.leave.stay", locale="es")
                assert screen.focused is focused
                assert screen.is_mounted


@pytest.mark.asyncio
async def test_password_reword_does_not_repopulate_or_clear_secret_controls() -> None:
    def rotate(*_args: str):
        raise AssertionError("language refresh cannot rotate a password")

    with override_settings(cadrumo_output_language="en"):
        screen = PassphraseScreen(assess=assess_profile_password, rotate=rotate)
        async with ScreenHostApp(screen).run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            controls = tuple(
                screen.query_one(selector, Input) for selector in ("#field-current", "#field-new", "#field-confirm")
            )
            for index, control in enumerate(controls):
                control.value = f"synthetic-in-progress-{index}"
                control.cursor_position = 3
            await pilot.pause()
            focused = screen.focused
            with override_settings(cadrumo_output_language="es"):
                await screen.refresh_language()
                await pilot.pause()
                assert screen.query_one("#label-current", Label).content == tr(
                    "flows.passphrase.current_label", locale="es"
                )
                assert (
                    tuple(
                        screen.query_one(selector, Input)
                        for selector in ("#field-current", "#field-new", "#field-confirm")
                    )
                    == controls
                )
                assert tuple(control.value for control in controls) == tuple(
                    f"synthetic-in-progress-{index}" for index in range(3)
                )
                assert tuple(control.cursor_position for control in controls) == (3, 3, 3)
                assert screen.focused is focused
                assert not screen.attempt_in_flight


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ("installation", "operations"))
async def test_catalogue_language_refresh_keeps_held_catalogue_and_semantic_selection(owner: str) -> None:
    with override_settings(cadrumo_output_language="en"):
        if owner == "installation":
            screen = InstallationScreen()
        else:
            # This presentation test never runs an operation or opens a client.
            def unused_ports(**_kwargs: object):
                raise AssertionError("catalogue presentation must not execute an operation")

            definition = build_invoice_add_definition(cast(CatalogueCreationPortsFactory, unused_ports))
            registry = OperationRegistry(
                definitions=(definition,), public_registrations=(build_invoice_add_registration(definition),)
            )
            screen = OperationsCatalogueScreen(
                cast(FrontendClient, object()), OperationCatalogueSourceV1(lambda: registry)
            )
        async with ScreenHostApp(screen).run_test(size=(130, 45)) as pilot:
            await pilot.pause()
            if isinstance(screen, InstallationScreen):
                table = screen.query_one("#installation-acts", DataTable)
                table.move_cursor(row=2)
                identity = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
                offered = screen._offered
                with override_settings(cadrumo_output_language="es"):
                    await screen.refresh_language()
                    await pilot.pause()
                    assert screen.query_one("#installation-acts", DataTable) is table
                    assert table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value == identity
                    assert screen._offered is offered
                    assert screen.query_one(".cadrumo-banner", Static).content == tr(
                        "tui.installation.title", locale="es"
                    )
            else:
                await screen.workers.wait_for_complete()
                await pilot.pause()
                assert screen._catalogue is not None
                catalogue = screen._catalogue
                chosen = catalogue.entries[0].definition_id
                query = screen.query_one("#operations-search", Input)
                query.value = chosen
                await pilot.pause()
                listed = screen.query_one("#operations-list", OptionList)
                listed.highlighted = listed.get_option_index(chosen)
                with override_settings(cadrumo_output_language="es"):
                    await screen.refresh_language()
                    await pilot.pause()
                    assert screen.query_one("#operations-list", OptionList) is listed
                    assert query.value == chosen
                    assert listed.highlighted is not None
                    assert listed.get_option_at_index(listed.highlighted).id == chosen
                    assert screen._catalogue is catalogue
                    assert screen.query_one(".cadrumo-banner", Static).content == tr(
                        "tui.operations.title", locale="es"
                    )


@pytest.mark.asyncio
async def test_home_factory_replacement_cannot_strand_inflight_language_refresh() -> None:
    entered, release, adopted = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls: list[str] = []

    def unused(*_args: object):
        raise AssertionError("language observation cannot run an account action")

    async def old_refresh() -> bool:
        calls.append("old")
        entered.set()
        await release.wait()
        return False

    async def new_refresh() -> bool:
        calls.append("new")
        adopted.set()
        return True

    factories = AccountFactoriesV1(
        profile=unused,
        change_user=unused,
        password=None,
        appearance=unused,
        language=unused,
        sign_out=unused,
        refresh_language=old_refresh,
    )
    replacement = replace(factories, refresh_language=new_refresh)
    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    with override_settings(cadrumo_output_language="en"):
        app = CadrumoTuiApp(account_factories=factories)
        async with app.run_test(size=(130, 45)) as pilot:
            app.post_message(ProfileLanguageInvalidated())
            await asyncio.wait_for(entered.wait(), 5)
            assert app._language_refreshing
            # Exercise the actual Home presentation handoff, which replaces
            # account doors while the old canonical read still awaits.
            app._apply_home_refresh(
                RootPresentationV1(
                    home=projection,
                    destination_catalogue=build_destination_catalogue(
                        admissions={
                            descriptor.destination: TuiDestinationAdmissionV1(
                                destination=descriptor.destination,
                                state=WorkbenchDestinationAdmissionState.UNAVAILABLE,
                                reason_code="workbench.destination.unavailable",
                            )
                            for descriptor in TUI_DESTINATION_CATALOGUE
                        }
                    ),
                    workbench_search_service=None,
                    account_factories=replacement,
                ),
                None,
            )
            await pilot.pause()
            release.set()
            await asyncio.wait_for(adopted.wait(), 5)
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert calls == ["old", "new"]
            assert app._account_factories is replacement
            assert not app._language_refreshing
            assert not app._language_pending
            assert app._language_retry_timer is None
