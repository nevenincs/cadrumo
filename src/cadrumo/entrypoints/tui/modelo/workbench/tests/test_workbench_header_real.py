"""The header, the navigator, search and the legend over real declarations: plain words, no identifiers.

Each declaration is seeded in real encrypted storage and read through the
production reader against the bundled registry: a compact quarterly return
and the dense annual income tax return, whose layout still carries registry
identifiers as section names. Every surface this part of the workbench draws
(the header, the stepper, the navigator or its breadcrumb, the sorted list,
the search hits and the symbols panel) names no transport token and shows no
heading that reads like an identifier.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import Input, OptionList, Static

from ......application.modelo.work_form_models import ModeloWorkForm, address_key
from ......core.config import override_settings
from ....components.host import ScreenHostApp
from ....tests.modelo_workbench_session import real_workbench
from ..installed import InstalledModeloWorkbench
from ..navigator import looks_like_identifier
from ..screen import ModeloWorkbenchScreen
from ..search import WorkbenchSearchPanel

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_DIGEST = re.compile(r"\b[0-9a-f]{64}\b")
_ADDRESSES = [
    pytest.param({"modelo": "130", "filing_year": 2026, "period_code": "1T"}, id="compact"),
    pytest.param({"modelo": "100", "filing_year": 2024, "period_code": "0A"}, id="dense"),
]
_HEADER = ("#wb-header", "#wb-deadline", "#wb-result", "#wb-stale", "#wb-chips", "#wb-stepper", "#wb-next")


@pytest.fixture(scope="module", params=_ADDRESSES)
def workbench(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Iterator[object]:
    """One real declaration per address, read only for every assertion in this module."""
    root: Path = tmp_path_factory.mktemp("header-real")
    with real_workbench(root, **request.param) as installed:
        yield installed


async def _opened(pilot: Pilot[None], screen: ModeloWorkbenchScreen) -> ModeloWorkForm:
    for _ in range(200):
        await pilot.pause()
        if screen.form is not None:
            return screen.form
    raise AssertionError("the workbench never finished reading its declaration")


def _tokens(form: ModeloWorkForm) -> set[str]:
    tokens = {str(form.work_unit_id)}
    if form.calculation_revision_id is not None:
        tokens.add(str(form.calculation_revision_id))
    for field in form.fields():
        kind, identity = address_key(field.address)
        if kind == "binding" or not identity.isdigit():
            tokens.add(identity)
        tokens.update(str(binding.binding_id) for binding in field.bindings)
    for page in form.pages:
        tokens.update(section.id for section in page.sections)
    return {token for token in tokens if len(token) > 3}


def _drawn(screen: ModeloWorkbenchScreen) -> str:
    parts = [str(screen.query_one(selector, Static).render()) for selector in (*_HEADER, "#wb-crumb", "#wb-page")]
    navigator = screen.query_one("#wb-sections", OptionList)
    parts.extend(str(navigator.get_option_at_index(index).prompt) for index in range(navigator.option_count))
    return "\n".join(parts)


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [80, 140])
async def test_a_real_declaration_names_itself_its_result_and_its_sections_in_words(
    width: int, workbench: InstalledModeloWorkbench
) -> None:
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(workbench, actions=workbench)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(width, 40)) as pilot:
            form = await _opened(pilot, screen)
            await pilot.pause()
            header = {selector: str(screen.query_one(selector, Static).render()) for selector in _HEADER}
            screens = {"workbench": _drawn(screen)}
            await pilot.press("o")
            await pilot.pause()
            screens["sorted"] = _drawn(screen)
            await pilot.press("o", "o", "o", "slash", "1")
            await pilot.pause()
            await pilot.pause()
            hits = [hit.text() for hit in screen.query_one(WorkbenchSearchPanel).hits]
            screens["search"] = "\n".join(hits)
            screen.query_one("#wb-search-input", Input).value = ""
            await pilot.press("escape", "question_mark", "question_mark")
            await pilot.pause()
            screens["legend"] = str(screen.query_one("#wb-legend-text", Static).render())
            app.exit(None)

    assert header["#wb-header"].startswith(f"Modelo {form.modelo}")
    assert header["#wb-deadline"]
    assert header["#wb-result"]
    assert header["#wb-stepper"] and header["#wb-next"]
    assert hits, "searching for 1 found no box on a real declaration"
    tokens = _tokens(form)
    assert tokens, "the declaration named no technical identifier, so this check would pass on anything"
    assert not [surface for surface, text in screens.items() if _DIGEST.search(text)]
    leaked = {
        surface: [line for line in text.splitlines() if any(token in line for token in tokens)]
        for surface, text in screens.items()
    }
    assert not {surface: lines for surface, lines in leaked.items() if lines}
    headings = [section.heading.text for page in screen.pages_shown for section in page.sections]
    assert headings
    assert not [heading for heading in headings if looks_like_identifier(heading)]
