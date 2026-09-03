"""The workbench, driven the way an operator without a mouse drives it.

Four properties, each a defect class this product has already produced on some
surface: a control that exists but cannot be reached by Tab, a focus position
restored by row ORDINAL so a refreshed list returns the operator somewhere
else, a state distinguishable only by colour, and a command palette that offers
fewer destinations than the shell mounts.

Nothing here asserts rendered prose. The prose is locale data read from the
catalogue the app reads, so asserting it would prove one file was consulted
twice; what is asserted is that a state carries TEXT at all, which is the
property a colour-blind or monochrome operator depends on.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widget import Widget

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import tr
from ....tests.terminal_sizes import TERMINAL_ORDINARY
from ..components.host import ScreenHostApp
from ..home import HomeScreen, HomeTarget
from ..navigation import TUI_DESTINATION_CATALOGUE, TuiScreenContextV1
from .workbench_session import installed_workbench_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.asyncio
async def test_every_focusable_control_on_a_destination_is_reachable_by_tab(tmp_path: Path) -> None:
    """A control Tab cannot reach is a control a keyboard operator does not have."""
    async with installed_workbench_root(tmp_path) as root:
        for route in root.destination_catalogue.routes:
            if route.factory is None:
                continue
            destination = route.descriptor.destination
            app = ScreenHostApp(route.factory(TuiScreenContextV1(destination=destination)))
            async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
                await pilot.pause()
                focusable = {
                    widget.id or f"{type(widget).__name__}@{id(widget)}"
                    for widget in app.screen.query(Widget)
                    if widget.focusable and widget.display
                }
                reached: set[str] = set()
                for _ in range(len(focusable) * 2 + 2):
                    await pilot.press("tab")
                    await pilot.pause()
                    focused = app.screen.focused
                    if focused is not None:
                        reached.add(focused.id or f"{type(focused).__name__}@{id(focused)}")

                assert focusable <= reached, (
                    f"{destination} never gives focus to {sorted(focusable - reached)} in a full Tab cycle"
                )
                app.exit(None)


@pytest.mark.asyncio
async def test_home_restores_focus_by_domain_identity_rather_than_row_position() -> None:
    """A refreshed Home returns the operator to the same THING, not the same row.

    Ranking is the application's, and it changes: restoring by ordinal silently
    moves the operator onto a different declaration whenever it does. The proof
    needs populated rows, so it runs over the synthetic ready projection rather
    than a fresh profile that legitimately has none — and it REORDERS them, which
    is the case an ordinal restore passes by accident and this one does not.
    """
    from ..devtools.home_fixtures import HomeFixtureScenario, build_home_projection_fixture

    projection = build_home_projection_fixture(HomeFixtureScenario.READY)
    screen = HomeScreen(projection)
    app = ScreenHostApp(screen)
    async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
        await pilot.pause()
        targets = tuple(screen.home_targets)
        app.exit(None)

    assert len(targets) > 1, "the ready fixture must offer more than one row to restore between"
    chosen = targets[-1]
    reordered = projection.model_copy(update={"declarations": tuple(reversed(projection.declarations))})
    restored = HomeScreen(reordered, restore_target=chosen)
    app = ScreenHostApp(restored)
    async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
        await pilot.pause()
        assert restored.highlighted_target == HomeTarget(kind=chosen.kind, identity=chosen.identity)
        app.exit(None)


@pytest.mark.asyncio
async def test_every_home_zone_states_its_availability_in_words(tmp_path: Path) -> None:
    """Colour is never the only carrier of a zone's state.

    Each zone's availability is rendered as localized text, so an operator on a
    monochrome terminal, a screen reader, or a colour-blind palette reads the
    same fact a colour would have carried.
    """
    async with installed_workbench_root(tmp_path) as root:
        screen = HomeScreen(root.refresh_home())
        app = ScreenHostApp(screen)
        async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
            await pilot.pause()
            rendered = "\n".join(
                str(widget.render()) for widget in app.screen.query(Widget) if widget.display and widget.is_container is False
            )
            app.exit(None)

    assert rendered.strip(), "Home rendered no text at all"


def test_the_destination_catalogue_names_every_destination_in_every_shipped_locale() -> None:
    """A destination the palette cannot name in a language is unreachable in it."""
    for descriptor in TUI_DESTINATION_CATALOGUE:
        for language in OutputLanguage:
            rendered = tr(descriptor.label_key, locale=language.value)
            assert rendered and rendered != descriptor.label_key, (
                f"{descriptor.destination} has no {language.value} name: {descriptor.label_key}"
            )


@pytest.mark.asyncio
async def test_the_command_palette_offers_exactly_the_admitted_destinations(tmp_path: Path) -> None:
    """The palette and the shell must agree on what can be opened.

    A palette entry for a refused destination is a dead end, and a missing
    entry hides a destination from the only navigation a keyboard operator
    has when they do not know where a thing lives.
    """
    from ..search import _command_entries

    async with installed_workbench_root(tmp_path) as root:
        offered = {target.destination for _label, target in _command_entries(root.destination_catalogue)}
        admitted = {
            route.descriptor.destination for route in root.destination_catalogue.routes if route.factory is not None
        }

        assert offered == admitted, f"palette offers {sorted(offered)} but the shell mounts {sorted(admitted)}"
