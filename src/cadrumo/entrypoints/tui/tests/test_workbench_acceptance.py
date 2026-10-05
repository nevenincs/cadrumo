"""The workbench over real declarations says nothing technical, returns focus and forgets what was typed.

Driven over real encrypted storage and the bundled registry through the
production reader and actions, in every shipped language, both appearances and
compact 80x24 terminals and docked editors at 120x36 and 160x48:

* no transport token reaches what the filer reads -- no digest, no work-unit
  or calculation identity, no casilla slug and no binding identifier, on the
  workbench, its sources view or its expanded help;
* every dialog, and the box panel docked under the list, gives the focus
  back to the casilla list on the box it was opened from;
* a value the filer typed and abandoned is kept nowhere: not in the staged
  changes after a cancel or a discard, and not in any log record.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import OptionList, Static

from ....application.modelo.work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormEditability,
    ModeloFormField,
    ModeloWorkForm,
    address_key,
)
from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....tests.terminal_sizes import TERMINAL_FLOOR
from ..components.host import ScreenHostApp
from ..components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..modelo.workbench.casilla_list import CasillaList
from ..modelo.workbench.editor import CasillaEditorPanel
from ..modelo.workbench.installed import InstalledModeloWorkbench
from ..modelo.workbench.screen import ModeloWorkbenchScreen
from ..modelo.workbench.sources import WorkbenchSourcesScreen
from .modelo_workbench_session import real_workbench

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LANGUAGES = tuple(OutputLanguage)
# The shared 80x24 floor opens the compact dialog; 120x36 and 160x48 exercise
# the docked editor with ordinary and spacious working areas.
_SIZES = (TERMINAL_FLOOR, (120, 36), (160, 48))
_THEMES = (CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME)
_DIGEST = re.compile(r"\b[0-9a-f]{64}\b")
_SURFACES = [pytest.param((), id="workbench"), pytest.param(("s",), id="sources"), pytest.param(("f1",), id="help")]


@pytest.fixture(scope="module", params=["130", "303"])
def workbench(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Iterator[object]:
    """One real declaration per modelo, read-only for the token checks."""
    root: Path = tmp_path_factory.mktemp(f"acceptance-{request.param}")
    with real_workbench(root, modelo=request.param) as installed:
        yield installed


async def _panel_opened(pilot: Pilot[None]) -> bool:
    """Wait for the box panel Enter opens, docked or in the dialog, once the box's full help has been read."""
    for _ in range(200):
        if pilot.app.screen.query(CasillaEditorPanel):
            return True
        await pilot.pause()
    return False


async def _opened(pilot: Pilot[None], screen: ModeloWorkbenchScreen) -> ModeloWorkForm:
    for _ in range(200):
        await pilot.pause()
        if screen.form is not None:
            return screen.form
    raise AssertionError("the workbench never finished reading its declaration")


def _frame_text(app: ScreenHostApp[None]) -> str:
    return (
        "\n".join(
            widget.render_line(y).text
            for widget in (*app.screen.query(CasillaList), *app.screen.query(OptionList))
            for y in range(widget.size.height)
        )
        + "\n"
        + "\n".join(str(static.render()) for static in app.screen.query("Static"))
    )


def _editable(form: ModeloWorkForm) -> ModeloFormField:
    """The first box on the first page the filer may type into."""
    return next(
        field
        for field in form.fields()
        if isinstance(field.address, ModeloFormCasillaAddressV1)
        and field.editability is ModeloFormEditability.EDITABLE_VALUE
    )


def _technical_tokens(form: ModeloWorkForm, workbench: InstalledModeloWorkbench) -> set[str]:
    """Identifiers a filer must never read: slugs, binding ids and the declaration's identities."""
    tokens = {str(form.work_unit_id)}
    if form.calculation_revision_id is not None:
        tokens.add(str(form.calculation_revision_id))
    for field in form.fields():
        kind, identity = address_key(field.address)
        if kind == "binding" or not identity.isdigit():
            tokens.add(identity)
        tokens.update(str(binding.binding_id) for binding in field.bindings)
    return {token for token in tokens if len(token) > 3}


@pytest.mark.asyncio
@pytest.mark.parametrize("keys", _SURFACES)
@pytest.mark.parametrize("language", _LANGUAGES, ids=lambda language: language.value)
@pytest.mark.parametrize("size", _SIZES, ids=lambda size: f"{size[0]}x{size[1]}")
@pytest.mark.parametrize("theme", _THEMES)
async def test_no_transport_token_reaches_what_the_filer_reads(
    keys: tuple[str, ...],
    language: OutputLanguage,
    size: tuple[int, int],
    theme: str,
    workbench: InstalledModeloWorkbench,
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(workbench, actions=workbench)
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            form = await _opened(pilot, screen)
            if keys:
                await pilot.press(*keys)
                await pilot.pause()
                await pilot.pause()
            if keys == ("s",):
                assert isinstance(app.screen, WorkbenchSourcesScreen), "the sources view did not open"
            elif keys == ("f1",):
                assert screen.query_one("#wb-help", Static).has_class("-expanded"), "the help did not expand"
            text = _frame_text(app)
            app.exit(None)

    assert not _DIGEST.search(text), "a digest reached the screen"
    tokens = _technical_tokens(form, workbench)
    assert tokens, "the declaration named no technical identifier, so this check would pass on anything"
    leaked = sorted(token for token in tokens if token in text)
    assert not leaked, f"technical identifiers reached the screen: {leaked[:5]}"


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGUAGES, ids=lambda language: language.value)
@pytest.mark.parametrize("size", _SIZES, ids=lambda size: f"{size[0]}x{size[1]}")
@pytest.mark.parametrize("theme", _THEMES)
async def test_every_dialog_returns_the_focus_to_the_box_it_was_opened_from(
    tmp_path: Path, language: OutputLanguage, size: tuple[int, int], theme: str
) -> None:
    with real_workbench(tmp_path) as installed, override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(installed, actions=installed)
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            form = await _opened(pilot, screen)
            casilla_list = screen.query_one(CasillaList)
            casilla_list.focus_address(address_key(_editable(form).address))
            await pilot.pause()
            origin = casilla_list.highlighted
            assert origin is not None
            returns: dict[str, bool] = {}
            for name, opening, closing in (
                ("editor", ("enter",), ("escape",)),
                ("sources", ("s",), ("escape",)),
            ):
                await pilot.press(*opening)
                await pilot.pause()
                assert app.screen is not screen or await _panel_opened(pilot), f"{name} did not open"
                await pilot.press(*closing)
                await pilot.pause()
                await pilot.pause()
                highlighted = casilla_list.highlighted
                returns[name] = (
                    app.screen is screen
                    and not screen.query(CasillaEditorPanel)
                    and screen.focused is casilla_list
                    and highlighted is not None
                    and highlighted.key == origin.key
                )
            app.exit(None)

    assert returns == {"editor": True, "sources": True}


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGUAGES, ids=lambda language: language.value)
@pytest.mark.parametrize("size", _SIZES, ids=lambda size: f"{size[0]}x{size[1]}")
@pytest.mark.parametrize("theme", _THEMES)
async def test_a_typed_value_is_kept_nowhere_once_abandoned(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    language: OutputLanguage,
    size: tuple[int, int],
    theme: str,
) -> None:
    caplog.set_level(logging.DEBUG)
    typed = "987654.32" if language is OutputLanguage.EN else "987654,32"
    with real_workbench(tmp_path) as installed, override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(installed, actions=installed)
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            form = await _opened(pilot, screen)
            casilla_list = screen.query_one(CasillaList)
            casilla_list.focus_address(address_key(_editable(form).address))
            await pilot.press("enter")
            assert await _panel_opened(pilot)
            await pilot.press(*typed, "escape")
            await pilot.pause()
            after_cancel = [change.text for change in screen.staged_changes]
            await pilot.press("enter")
            assert await _panel_opened(pilot)
            # Keep and stay, so the panel closes on this box rather than refilling for the next.
            await pilot.press(*typed, "ctrl+enter")
            await pilot.pause()
            staged = len(screen.staged_changes)
            await pilot.press("R")
            await pilot.pause()
            await pilot.click("#review-discard")
            await pilot.pause()
            await pilot.pause()
            after_discard = len(screen.staged_changes)
            app.exit(None)
        stored = installed.load(language).form
        assert stored.calculation_revision_id == form.calculation_revision_id
        assert {address_key(field.address): field.value for field in stored.fields()} == {
            address_key(field.address): field.value for field in form.fields()
        }

    assert after_cancel == []
    assert staged == 1
    assert after_discard == 0
    digits = typed.replace(",", "").replace(".", "")
    assert not [record for record in caplog.records if digits in record.getMessage().replace(",", "").replace(".", "")]
