"""The sources view over a real declaration: every box mapped once, and no binding named.

The declaration is seeded in real encrypted storage and read through the
production reader against the bundled registry, so the grouping meets the
origins and sources a real form carries rather than a fixture's.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from textual.pilot import Pilot
from textual.widgets import OptionList, Static

from ......application.modelo.work_form_models import address_key
from ......core.config import override_settings
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
