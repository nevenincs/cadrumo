"""What the surfaces LOOK like, not merely which widgets they contain.

Every earlier proof in this package asserts structure: a widget exists, a
row is present, a value came back. All of it passed while the page sat off
the terminal midline, buttons showed no focus, and Tab stopped dead on a
scroll container. Structure is not appearance, and the defects that reached
the operator were all appearance.

So these render through Textual's real compositor at real terminal sizes
and interrogate the result: does anything fall outside the screen, does
every control take focus in a closed cycle, and does a focused control
actually look different from an unfocused one. A style property set on a
widget is not evidence — the cells it paints are, and
``Screen.get_style_at`` reads exactly those.

This is not a human at a terminal, and does not pretend to be. It is the
same rendering path a terminal drives, checked for the properties a human
would have caught by looking.
"""

from __future__ import annotations

import pytest
from textual.widgets import Button, Input

from .. import (
    FormApp,
    FormField,
    FormPage,
    RegistrationApp,
    StatusApp,
    StatusFactRow,
    StatusPageData,
)
from .._theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME, ContentScroll

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_inbound_adapter,
]

_SIZES = [(80, 24), (120, 40), (200, 50)]
"""A minimum-size terminal, an ordinary one, and a wide one.

80x24 is the floor a real terminal can be, and the size at which an
overflowing layout stops being cosmetic and starts hiding controls.
"""

_THEMES = [CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME]


def _registration() -> RegistrationApp:
    from .....application.user_profile import assess_passphrase
    from .....entrypoints.cli._config._manager_frontend import attempt_registration

    return RegistrationApp(assess=assess_passphrase, register=attempt_registration)


def _form() -> FormApp:
    return FormApp(
        FormPage(
            title="TITLE",
            section="SECTION",
            fields=(FormField(key="a", label="A"), FormField(key="b", label="B")),
        ),
    )


def _status() -> StatusApp:
    return StatusApp(
        StatusPageData(
            active_profile_label="Subject",
            facts=(StatusFactRow(label="Field", value="Value"),),
        ),
    )


_SURFACES = [
    pytest.param(_registration, id="registration"),
    pytest.param(_form, id="form"),
    pytest.param(_status, id="status"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("build", _SURFACES)
@pytest.mark.parametrize(("width", "height"), _SIZES)
@pytest.mark.parametrize("theme", _THEMES)
async def test_nothing_is_painted_past_the_side_edges(build, width: int, height: int, theme: str) -> None:
    """No widget may extend past the left or right edge of the screen.

    Horizontal only, deliberately. Content taller than the viewport is
    what a scroll container is for and is not a defect; content wider
    than the terminal is one, because these surfaces scroll vertically
    only, so anything past the right edge is a control the operator
    cannot reach and text they cannot read. Checked at 80 columns
    because that is where a layout that looks generous on a wide
    terminal starts truncating.
    """
    app = build()
    async with app.run_test(size=(width, height)) as pilot:
        app.theme = theme
        await pilot.pause()
        offenders = [
            f"{type(widget).__name__}{widget.region}"
            for widget in app.screen.walk_children()
            if widget.display and (widget.region.x < 0 or widget.region.right > width)
        ]
        assert not offenders, f"painted past the side edges of a {width}-column terminal: {offenders}"
        app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("build", _SURFACES)
@pytest.mark.parametrize(("width", "height"), _SIZES)
async def test_content_taller_than_the_screen_stays_reachable(build, width: int, height: int) -> None:
    """Overflowing content must be scrollable, not merely overflowing.

    On a 24-row terminal the registration form is taller than the screen,
    which is fine — as long as the operator can scroll to the rest of it.
    A scroll host that overflows without being able to scroll has simply
    hidden its own submit button.
    """
    app = build()
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        for host in app.query(ContentScroll):
            if host.virtual_size.height > host.container_size.height:
                assert host.max_scroll_y > 0, (
                    f"content is {host.virtual_size.height} rows in a {host.container_size.height}-row "
                    f"viewport at {width}x{height} but cannot be scrolled"
                )
        app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("build", _SURFACES)
@pytest.mark.parametrize("theme", _THEMES)
async def test_every_surface_actually_renders_under_both_appearances(build, theme: str) -> None:
    """The compositor produces real output, not an empty frame.

    Exporting the screenshot forces a full render through the same path a
    terminal drives, so a theme token that fails to resolve surfaces here
    rather than on the operator's screen.
    """
    app = build()
    async with app.run_test(size=(100, 30)) as pilot:
        app.theme = theme
        await pilot.pause()
        rendered = app.export_screenshot()
        assert "<text" in rendered, "the surface rendered no text at all"
        assert len(rendered) > 1000, "the surface rendered a suspiciously empty frame"
        app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("build", [pytest.param(_registration, id="registration"), pytest.param(_form, id="form")])
async def test_tab_visits_every_control_and_comes_back(build) -> None:
    """Every tab stop must be a real control, and the cycle must close.

    The defect this pins shipped: a scrollable container is focusable by
    default, so Tab landed on it, showed nothing, did nothing, and the
    form read as broken. Note that "the cycle closes" alone would NOT
    have caught it — a scroll host in the chain still gets visited and
    still closes the cycle. What discriminates is the membership check:
    no container may be a tab stop, only controls the operator can
    actually operate.
    """
    app = build()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        chain = app.screen.focus_chain
        assert chain, "an interactive surface must have focusable controls"

        # Specifically our own scroll host. A blanket ScrollableContainer
        # check would be wrong: DataTable is one too, and it is a real
        # control the operator drives with the arrow keys.
        hosts = [type(widget).__name__ for widget in chain if isinstance(widget, ContentScroll)]
        assert not hosts, f"the content scroll host is a dead tab stop: {hosts}"

        app.screen.set_focus(chain[0])
        await pilot.pause()
        visited = [app.focused]
        for _ in range(len(chain)):
            await pilot.press("tab")
            visited.append(app.focused)

        assert visited[-1] is chain[0], f"tab did not close the cycle: {[type(w).__name__ for w in visited]}"
        assert set(visited) == set(chain), (
            f"tab skipped a control: chain={[type(w).__name__ for w in chain]} "
            f"visited={[type(w).__name__ for w in visited]}"
        )
        app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("theme", _THEMES)
async def test_a_focused_button_is_painted_differently_from_an_unfocused_one(theme: str) -> None:
    """Focus must be visible in the cells, not merely true in a property.

    Read off the rendered screen through ``get_style_at``: a rule that
    fails to apply leaves the property set and the pixels unchanged, and
    only the pixels are what the operator sees.
    """
    app = _form()
    async with app.run_test(size=(120, 40)) as pilot:
        app.theme = theme
        await pilot.pause()
        buttons = list(app.query(Button))
        assert len(buttons) >= 2, "this surface needs two buttons to compare"

        target, other = buttons[0], buttons[1]
        app.screen.set_focus(other)
        await pilot.pause()
        unfocused = app.screen.get_style_at(target.region.x + 1, target.region.y + 1)

        app.screen.set_focus(target)
        await pilot.pause()
        focused = app.screen.get_style_at(target.region.x + 1, target.region.y + 1)

        assert (focused.bgcolor, focused.color, focused.bold) != (
            unfocused.bgcolor,
            unfocused.color,
            unfocused.bold,
        ), f"focus is invisible under {theme}: {focused!r} == {unfocused!r}"
        app.exit(None)


@pytest.mark.asyncio
async def test_a_password_field_never_paints_its_secret() -> None:
    """The typed passphrase must not appear in the rendered cells.

    Asserting ``password=True`` on the widget proves the flag, not the
    output. This reads the exported render and requires the secret to be
    absent from it, which is the property that matters on a shared screen
    or in a captured session log.
    """
    app = _registration()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app.query_one("#field-password", Input).value = "SENTINEL-SECRET-VALUE"
        await pilot.pause()
        assert "SENTINEL-SECRET-VALUE" not in app.export_screenshot()
        app.exit(None)
