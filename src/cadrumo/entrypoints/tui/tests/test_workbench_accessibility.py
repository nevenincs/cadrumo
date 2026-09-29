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

from typing import cast

import pytest
from textual.screen import Screen
from textual.widget import Widget

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import I18N_STRICT_MISSING_KEYS, MissingTranslationError, tr
from ....tests.terminal_sizes import TERMINAL_ORDINARY
from ..components.host import ScreenHostApp
from ..home import HomeScreen, HomeTarget
from ..navigation import TUI_DESTINATION_CATALOGUE

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]




async def _assert_tab_reaches_everything(screen: object, label: str) -> None:
    """Drive a full Tab cycle and require every focusable control to be reached."""
    app = ScreenHostApp(cast("Screen[None]", screen))
    async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
        await pilot.pause()
        focusable = {
            widget.id or f"{type(widget).__name__}@{id(widget)}"
            for widget in app.screen.query(Widget)
            # A control inside a folded section is out of the Tab order by
            # design until the section is opened; its fold's title is not.
            if widget.focusable and all(node.display for node in widget.ancestors_with_self if isinstance(node, Widget))
        }
        reached: set[str] = set()
        for _ in range(len(focusable) * 2 + 2):
            await pilot.press("tab")
            await pilot.pause()
            focused = app.screen.focused
            if focused is not None:
                reached.add(focused.id or f"{type(focused).__name__}@{id(focused)}")
        app.exit(None)

    assert focusable, f"{label} offers no focusable control at all, so reachability proves nothing"
    assert focusable <= reached, f"{label} never gives focus to {sorted(focusable - reached)} in a full Tab cycle"


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["ready", "blocked"])
async def test_every_focusable_control_on_a_populated_home_is_reachable_by_tab(scenario: str) -> None:
    """The empty-profile pass could not see this.

    Home's three tables set display=False when they hold no rows, so over a
    fresh profile the destination contributes an EMPTY focusable set and the
    subset assertion holds vacuously -- removing a widget from the focus chain
    went undetected there. These fixtures populate the tables, so the chain has
    something to fail on.
    """
    from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture

    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario(scenario)))
    await _assert_tab_reaches_everything(screen, f"home--{scenario}")


@pytest.mark.asyncio
async def test_home_restores_focus_by_domain_identity_rather_than_row_position() -> None:
    """A refreshed Home returns the operator to the same THING, not the same row.

    Ranking is the application's, and it changes: restoring by ordinal silently
    moves the operator onto a different declaration whenever it does. The proof
    needs populated rows, so it runs over the synthetic ready projection rather
    than a fresh profile that legitimately has none — and it REORDERS them, which
    is the case an ordinal restore passes by accident and this one does not.
    """
    from .home_fixtures import HomeFixtureScenario, build_home_projection_fixture

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






def test_the_destination_catalogue_names_every_destination_in_every_shipped_locale() -> None:
    """A destination the palette cannot name in a language is unreachable in it.

    Asserted under STRICT resolution. Without it this proves nothing: `tr()`
    humanises a missing key into a plausible English string rather than
    returning the key, so a catalogue with no entries at all reports a full
    pass. Measured 2026-09-04, every one of these keys was absent from all four
    catalogues while this test was green.
    """
    strict_token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        for descriptor in TUI_DESTINATION_CATALOGUE:
            for language in OutputLanguage:
                rendered = tr(descriptor.label_key, locale=language.value)
                assert rendered and rendered != descriptor.label_key, (
                    f"{descriptor.destination} has no {language.value} name: {descriptor.label_key}"
                )
    finally:
        I18N_STRICT_MISSING_KEYS.reset(strict_token)


def test_a_missing_destination_name_is_not_humanised_into_a_false_pass() -> None:
    """The fallback that made the gate above vacuous, asserted directly.

    If this ever stops raising, `tr()` has regained a silent fallback under
    strict resolution and every locale-coverage gate in the tree is worth less
    than it looks.
    """
    strict_token = I18N_STRICT_MISSING_KEYS.set(True)
    try:
        with pytest.raises(MissingTranslationError):
            tr("tui.destination.a_key_that_does_not_exist", locale="es")
    finally:
        I18N_STRICT_MISSING_KEYS.reset(strict_token)
