"""Over real declarations the box panel says how a change travels to the result, in every language and host.

Driven through the production reader and actions over real encrypted storage
and the bundled registry. The chains are written from the official forms,
not read back from the workbench: on Modelo 130 box [05] is subtracted in
[07], which adds into [12], [12] less [13] is [14], [14] feeds [17] and [17]
feeds the result [19]; [14] also feeds [15], a longer way to [17], so one
more box changes off the chain. On Modelo 303 [66] adds into [69] and [71]
settles [69], while [59], additional information, changes no result. The
panel says it docked under the list and in the dialog a short terminal opens,
and names no casilla slug or binding identifier.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from textual.pilot import Pilot
from textual.widgets import Static

from ......application.modelo.work_form_models import ModeloFormCasillaAddressV1, ModeloWorkForm, address_key
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ....components.host import ScreenHostApp
from ....tests.modelo_workbench_session import real_workbench
from ..editor import CasillaEditorPanel, CasillaEditorScreen
from ..installed import InstalledModeloWorkbench
from ..screen import ModeloWorkbenchScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LANGUAGES = tuple(OutputLanguage)
_DOCKED = (160, 48)
_DIALOG = (120, 24)
"""Too short to dock the panel under the list, so it opens in the centred dialog."""


@pytest.fixture(scope="module")
def instalments(tmp_path_factory: pytest.TempPathFactory) -> Iterator[InstalledModeloWorkbench]:
    """One real first-quarter Modelo 130."""
    with real_workbench(tmp_path_factory.mktemp("affects-130"), modelo="130") as installed:
        yield installed


@pytest.fixture(scope="module")
def vat(tmp_path_factory: pytest.TempPathFactory) -> Iterator[InstalledModeloWorkbench]:
    """One real first-quarter Modelo 303."""
    with real_workbench(tmp_path_factory.mktemp("affects-303"), modelo="303") as installed:
        yield installed


async def _opened(pilot: Pilot[None], screen: ModeloWorkbenchScreen) -> ModeloWorkForm:
    for _ in range(200):
        await pilot.pause()
        if screen.form is not None:
            return screen.form
    raise AssertionError("the workbench never finished reading its declaration")


async def _affects(pilot: Pilot[None], box: str) -> str:
    """Open the panel on ``box`` and read its "Affects" answer, once the box's help has been read."""
    await pilot.press("g", *box, "enter")
    await pilot.pause()
    await pilot.press("enter")
    for _ in range(200):
        await pilot.pause()
        panels = list(pilot.app.screen.query(CasillaEditorPanel))
        if panels and panels[0].query("#editor-affects-text"):
            return str(panels[0].query_one("#editor-affects-text", Static).render())
    raise AssertionError(f"the panel on [{box}] never said what it affects")


def _label(form: ModeloWorkForm, box: str) -> str:
    return next(field.label.text for field in form.fields() if field.box == box)


def _technical_tokens(form: ModeloWorkForm) -> set[str]:
    """Identifiers a filer must never read: casilla slugs and binding ids."""
    tokens: set[str] = set()
    for field in form.fields():
        kind, identity = address_key(field.address)
        if kind == "binding" or not identity.isdigit():
            tokens.add(identity)
        tokens.update(str(binding.binding_id) for binding in field.bindings)
    return {token for token in tokens if len(token) > 3}


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [_DOCKED, _DIALOG], ids=["docked", "dialog"])
@pytest.mark.parametrize("language", _LANGUAGES, ids=lambda language: language.value)
async def test_a_130_box_names_its_chain_to_the_result(
    language: OutputLanguage, size: tuple[int, int], instalments: InstalledModeloWorkbench
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(instalments, actions=instalments)
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            form = await _opened(pilot, screen)
            said = await _affects(pilot, "05")
            in_dialog = isinstance(app.screen, CasillaEditorScreen)
            others = tr("tui.modelo.workbench.editor.affects.others", count="[15]")
            app.exit(None)

    assert in_dialog is (size == _DIALOG)
    chain, *rest = said.split("\n")
    assert chain.startswith(f"[07] {_label(form, '07')} → [12] → [14] → [17] → [19]"), chain
    assert rest == [others]
    tokens = _technical_tokens(form)
    assert tokens, "the declaration named no technical identifier, so this check would pass on anything"
    assert not [token for token in tokens if token in said]


@pytest.mark.asyncio
@pytest.mark.parametrize("language", _LANGUAGES, ids=lambda language: language.value)
async def test_a_303_box_reaches_the_result_and_an_informative_one_says_it_does_not(
    language: OutputLanguage, vat: InstalledModeloWorkbench
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(vat, actions=vat)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_DOCKED) as pilot:
            form = await _opened(pilot, screen)
            general = await _affects(pilot, "66")
            await pilot.press("escape")
            await pilot.pause()
            informative = await _affects(pilot, "59")
            not_result = tr("tui.modelo.workbench.editor.affects.not_result")
            app.exit(None)

    assert general.startswith(f"[69] {_label(form, '69')} → [71]"), general
    assert informative.split("\n")[0] == not_result
    tokens = _technical_tokens(form)
    assert not [token for token in tokens if token in general or token in informative]


def test_the_witness_boxes_are_casillas_of_the_real_forms(
    instalments: InstalledModeloWorkbench, vat: InstalledModeloWorkbench
) -> None:
    """The boxes the panel tests open are casilla rows the filer can select, not inputs no box owns."""
    for workbench, boxes in ((instalments, ("05", "07")), (vat, ("59", "66", "69"))):
        form = workbench.load(OutputLanguage.EN).form
        for box in boxes:
            field = next(field for field in form.fields() if field.box == box)
            assert isinstance(field.address, ModeloFormCasillaAddressV1)
