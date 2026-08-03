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
from pydantic import BaseModel
from textual.containers import ScrollableContainer
from textual.widgets import Button, Input

from .....application.flows import CopyRef, FlowDefinition, FlowPage, FlowSection
from .....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from .. import (
    FlowTuiApp,
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


class _VisualAnswers(BaseModel):
    """Trivial answers model; only its type identity is consumed."""


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


def _question() -> FlowTuiApp:
    """The wizard question screen, carrying more content than a short terminal holds.

    Enrolled here because it is the surface the operator sees on every page
    of every flow, and it was the one full-screen surface these gates did
    not cover: it had collapsed the scroll host and the bordered panel into
    a single auto-height ``VerticalScroll``, which cannot scroll, so the
    overflow fell through to the Screen and the host sat in the tab order
    as a dead stop — the exact two defects the gates below already pin on
    every other surface.
    """
    copy = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="wizard.setup.title")
    page = FlowPage(
        id="p0",
        widget=FlowWidgetKind.TEXT,
        prompt=copy,
        help=copy,
        failure_modes=tuple(copy for _ in range(14)),
        answer_type=str,
    )
    definition = FlowDefinition(
        id="flows.test.visual",
        title=copy,
        description=copy,
        sections=(FlowSection(id="s1", title=copy, items=(page,)),),
        answers_model=_VisualAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )
    return FlowTuiApp(definition, mode=FlowMode.MODIFY, registered_values={})


def _many_page_flow() -> FlowTuiApp:
    """A flow long enough that both the question page and the review table
    overflow their container at every size in ``_SIZES``.

    Sixty optional pages put the review table's row count past the
    viewport at every size. That alone says nothing about the question
    page: only the cursor's current page is rendered there, so each page
    also carries enough failure-mode lines to overflow the question
    panel's own scroll host — forty lines clears the widest fixture
    size (200x50) with margin, measured directly against
    ``ContentScroll.virtual_size`` vs ``container_size``.
    """
    copy = CopyRef(kind=CopyRefKind.LOCALE_KEY, ref="wizard.setup.title")
    pages = tuple(
        FlowPage(
            id=f"p{index}",
            widget=FlowWidgetKind.TEXT,
            prompt=copy,
            help=copy,
            failure_modes=tuple(copy for _ in range(40)),
            answer_type=str,
            required=False,
        )
        for index in range(60)
    )
    definition = FlowDefinition(
        id="flows.test.visual.long",
        title=copy,
        description=copy,
        sections=(FlowSection(id="s1", title=copy, items=pages),),
        answers_model=_VisualAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
    )
    return FlowTuiApp(definition, mode=FlowMode.MODIFY, registered_values={})


_SURFACES = [
    pytest.param(_registration, id="registration"),
    pytest.param(_form, id="form"),
    pytest.param(_status, id="status"),
    pytest.param(_question, id="question"),
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
        buttons = list(app.screen.query(Button))
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


@pytest.mark.asyncio
@pytest.mark.parametrize(("width", "height"), _SIZES)
@pytest.mark.parametrize("review", [False, True], ids=["question", "review"])
async def test_the_screen_itself_never_scrolls_on_a_flow_surface(
    width: int,
    height: int,
    review: bool,
) -> None:
    """Scrolling belongs to one designated host, never to the Screen.

    A Screen that scrolls is the signature of a surface whose own scroll
    container cannot: an ``auto`` height grows to fit its content, so the
    overflow falls through to the Screen and the operator sees a second
    vertical scrollbar stacked outside the first. Both flow surfaces hit
    this — the question page had collapsed its scroll host into its
    bordered panel, and the review table grew to its full row count beside
    the Screen's own bar.

    The definition carries many pages deliberately. A short flow cannot
    overflow the review table at any terminal size, so a small fixture
    would pass with the defect present and prove nothing; the precondition
    is asserted below rather than assumed.
    """
    app = _many_page_flow()
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        if review:
            await pilot.press("f2")
            await pilot.pause()
        screen = app.screen

        # Positive control: the surface must actually have more content
        # than the viewport, or "the Screen does not scroll" is vacuous.
        # ScrollableContainer is the common base of both designated scroll
        # hosts on these surfaces: the question page's ContentScroll and
        # the review table's DataTable (a DataTable is its own scroll
        # container, never wrapped in a ContentScroll — see #review-table's
        # CSS comment).
        overflowing = [
            widget
            for widget in screen.walk_children()
            if isinstance(widget, ScrollableContainer)
            and widget.display
            and widget.virtual_size.height > widget.container_size.height
        ]
        assert overflowing, (
            f"fixture cannot detect the defect at {width}x{height}: nothing overflows its "
            f"container, so a non-scrolling Screen proves nothing"
        )

        assert not screen.show_vertical_scrollbar, (
            f"{type(screen).__name__} is scrolling at {width}x{height}: its content overflows a "
            f"container that cannot scroll, so the operator sees two stacked vertical scrollbars"
        )
        app.exit(None)
