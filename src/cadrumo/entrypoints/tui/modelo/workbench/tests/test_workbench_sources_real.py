"""The sources view over a real declaration: every box mapped once, no binding named, earlier ones named.

The declaration is seeded in real encrypted storage and read through the
production reader against the bundled registry, so the grouping meets the
origins and sources a real form carries rather than a fixture's. A second
quarter carries a value from the first, and the map names that declaration
rather than the generic name of its source.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import OptionList, Static

from ......application.modelo.source_policy import SourceFamily, source_policy
from ......application.modelo.work_form_models import address_key
from ......core.aggregation import BindingSourceKind
from ......core.config import override_settings
from ......core.i18n.render import tr
from ....components.host import ScreenHostApp
from ....tests.modelo_workbench_session import real_workbench
from ..screen import ModeloWorkbenchScreen
from ..sources import WorkbenchSourcesScreen, source_groups

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SIZE = (140, 40)


async def _settle(pilot: Pilot[None], times: int = 3) -> None:
    for _ in range(times):
        await pilot.pause()


@pytest.mark.asyncio
async def test_a_real_declaration_maps_every_box_once_and_names_no_binding(tmp_path: Path) -> None:
    with real_workbench(tmp_path) as installed, override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(installed, actions=installed)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            for _ in range(200):
                await pilot.pause()
                if screen.form is not None:
                    break
            form = screen.form
            assert form is not None
            await pilot.press("s")
            await _settle(pilot)
            sources = app.screen
            assert isinstance(sources, WorkbenchSourcesScreen)
            groups = sources.query_one("#sources-groups", OptionList)
            prompts = [str(groups.render_line(y).text) for y in range(groups.size.height)]
            title = str(sources.query_one("#sources-title", Static).render())
            app.exit(None)

    mapped = source_groups(form)
    placed = Counter(address_key(field.address) for group in mapped for field in group.fields)
    assert placed == Counter(address_key(field.address) for field in form.fields())
    assert set(placed.values()) == {1}
    assert title.endswith(f"Boxes: {len(form.fields())}")
    assert groups.option_count == len(mapped)
    binding_ids = {str(binding.binding_id) for field in form.fields() for binding in field.bindings}
    assert binding_ids, "the real declaration carries no source, so the leak check would pass on anything"
    assert not [token for token in binding_ids if any(token in prompt for prompt in prompts)]


@pytest.mark.asyncio
async def test_a_real_second_quarter_names_the_declaration_it_carries_from(tmp_path: Path) -> None:
    with (
        real_workbench(tmp_path, modelo="130", filing_year=2026, period_code="2T") as installed,
        override_settings(cadrumo_output_language="en"),
    ):
        screen = ModeloWorkbenchScreen(installed, actions=installed)
        app = ScreenHostApp(screen)
        async with app.run_test(size=_SIZE) as pilot:
            for _ in range(200):
                await pilot.pause()
                if screen.form is not None:
                    break
            form = screen.form
            assert form is not None
            await pilot.press("s")
            await _settle(pilot)
            sources = app.screen
            assert isinstance(sources, WorkbenchSourcesScreen)
            groups = sources.query_one("#sources-groups", OptionList)
            prompts = [str(groups.render_line(y).text).strip() for y in range(groups.size.height)]
            generic = tr(source_policy(BindingSourceKind.PREVIOUS_FILING).label_key)
            app.exit(None)

    carried = [
        filing
        for field in form.fields()
        if field.source is not None and field.source.family is SourceFamily.EARLIER_FILINGS
        for filing in field.source.earlier_filings
    ]
    assert carried, "the real second quarter names no earlier declaration, so the naming check would pass on nothing"
    earlier = prompts.index(next(line for line in prompts if "« Earlier declarations" in line))
    assert prompts[earlier].startswith("▹ ")
    assert prompts[earlier + 1].startswith("Modelo 130 · 1st quarter 2026")
    assert not any(generic in prompt for prompt in prompts)
    toggles = [prompt[:1] for prompt in prompts if prompt[:1] in "▹▿▸▾"]
    assert toggles.count("▿") == 1
    assert set(toggles) <= {"▹", "▿"}
