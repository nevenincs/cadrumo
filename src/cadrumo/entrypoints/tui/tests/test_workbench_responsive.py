"""Home and every principal workspace, proven to fit the terminals we support.

The sibling responsive suite covers the Modelo workspace destinations. This one
covers what the operator actually lands on: Home and the routed Ledger,
Declarations, AEAT Sync and Profile destinations composed by the installed
session. Nothing here declares a terminal size of its own — the shared
declaration is the single authority on which sizes matter.

Assertions are geometric, not textual. Vertical overflow is ordinary and
scrollable; horizontal overflow silently removes information, and a screen that
resolves to nothing at the floor has failed rather than adapted. Both are read
from the mounted regions rather than a rendered frame, because a frame is
clipped at the edge and looks identical either way.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from textual.widget import Widget

from ....tests.terminal_sizes import (
    SUPPORTED_TERMINAL_SIZE_IDS,
    SUPPORTED_TERMINAL_SIZES,
    TERMINAL_ORDINARY,
)
from ..components.host import ScreenHostApp
from ..components.theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME
from ..home import HomeScreen
from ..navigation import TuiScreenContextV1
from .workbench_session import installed_workbench_root

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_THEMES = (CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME)


@pytest.mark.asyncio
async def test_no_workbench_destination_pushes_content_past_the_right_edge(tmp_path: Path) -> None:
    """Columns past the right edge are unreachable, so none may exist."""
    async with installed_workbench_root(tmp_path) as root:
        for route in root.destination_catalogue.routes:
            if route.factory is None:
                continue
            destination = route.descriptor.destination
            for size in SUPPORTED_TERMINAL_SIZES:
                width, _height = size
                app = ScreenHostApp(route.factory(TuiScreenContextV1(destination=destination)))
                async with app.run_test(size=size) as pilot:
                    await pilot.pause()
                    overflowing = [
                        widget for widget in app.screen.query(Widget) if widget.display and widget.region.right > width
                    ]
                    assert not overflowing, (
                        f"{destination} at {width} columns pushes "
                        + ", ".join(
                            f"{type(widget).__name__}(id={widget.id!r}) to x={widget.region.right}"
                            for widget in overflowing[:5]
                        )
                        + " past the right edge, where the operator cannot reach it"
                    )
                    app.exit(None)


@pytest.mark.asyncio
async def test_every_workbench_destination_paints_content_at_every_supported_size(tmp_path: Path) -> None:
    """A destination that mounts blank at the floor has failed, not adapted."""
    async with installed_workbench_root(tmp_path) as root:
        for route in root.destination_catalogue.routes:
            if route.factory is None:
                continue
            destination = route.descriptor.destination
            for size in SUPPORTED_TERMINAL_SIZES:
                app = ScreenHostApp(route.factory(TuiScreenContextV1(destination=destination)))
                async with app.run_test(size=size) as pilot:
                    await pilot.pause()
                    painted = [
                        widget
                        for widget in app.screen.query(Widget)
                        if widget.display and widget.region.height > 0 and widget.region.width > 0
                    ]
                    assert painted, f"{destination} rendered nothing at {size}"
                    app.exit(None)


@pytest.mark.asyncio
async def test_home_keeps_one_scrollable_owner_rather_than_nesting_them(tmp_path: Path) -> None:
    """Two nested scrollers make a keyboard operator guess which one moves.

    Asserted on structure AND capacity, not on how many scrollbars happen to be
    visible at once. The visibility form was proven weak: an inner scroller
    absorbs its own overflow, so the outer one never shows a bar at the same
    time and the count stays at one while a genuine second scroll owner sits
    inside the first.

    Nesting alone is not the defect. Every Home table is a ContentDataTable,
    which IS a scrollable container and legitimately sits inside the page
    scroller -- it sizes its height to its rows so it never competes. What
    competes is a nested container that can still scroll on its own axis, and
    that is what this rejects.

    Home is the surface this matters most on -- it is the return point from
    every journey, so a scroll position that lands in the wrong container is
    met again after every child dismissal.
    """
    from textual.containers import ScrollableContainer

    async with installed_workbench_root(tmp_path) as root:
        home = root.destination_catalogue.resolve("workbench.home")
        assert home.factory is not None
        for size in SUPPORTED_TERMINAL_SIZES:
            app = ScreenHostApp(home.factory(TuiScreenContextV1(destination="workbench.home")))
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                nested = [
                    widget
                    for widget in app.screen.query(ScrollableContainer)
                    if widget.max_scroll_y > 0
                    and any(
                        isinstance(parent, ScrollableContainer) and parent.max_scroll_y > 0
                        for parent in widget.ancestors
                    )
                ]
                app.exit(None)

            assert not nested, (
                f"Home nests {len(nested)} competing scroll owner(s) inside another at {size}: "
                + ", ".join(f"{type(widget).__name__}(id={widget.id!r})" for widget in nested[:3])
            )


@pytest.mark.asyncio
async def test_home_renders_under_both_appearances(tmp_path: Path) -> None:
    """Appearance is a palette swap, never a change to what is on the page."""
    async with installed_workbench_root(tmp_path) as root:
        home = root.destination_catalogue.resolve("workbench.home")
        assert home.factory is not None
        painted: dict[str, int] = {}
        for theme in _THEMES:
            app = ScreenHostApp(home.factory(TuiScreenContextV1(destination="workbench.home")))
            async with app.run_test(size=SUPPORTED_TERMINAL_SIZES[-1]) as pilot:
                app.theme = theme
                await pilot.pause()
                painted[theme] = len([widget for widget in app.screen.query(Widget) if widget.display])
                app.exit(None)

        assert len(set(painted.values())) == 1, f"appearance changed the mounted content: {painted}"


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [s for s in SUPPORTED_TERMINAL_SIZES if s[0] >= 120])
@pytest.mark.parametrize("scenario", ["ready", "blocked"])
async def test_home_keeps_a_gutter_between_its_two_columns(scenario: str, size: tuple[int, int]) -> None:
    """Wrapped left-column text must never abut the sidebar.

    Two touching columns produce rows like "...En todosAEAT: no observada",
    where a reader cannot tell where one fact ends and the next begins. An
    overflow check cannot see it -- nothing leaves the screen -- so this reads
    the painted cells either side of the column boundary instead.

    It runs over the POPULATED fixtures rather than a live session, and that
    is the whole point: a fresh profile's Home has no action rows long enough
    to reach the boundary, so a live-session version of this proof passes
    whether or not the gutter exists. Verified by removing the gutter: the
    live-session form still passed, these fail.
    """
    from ..devtools.frame import screen_text
    from ..devtools.home_fixtures import HomeFixtureScenario, build_home_projection_fixture

    width, height = size
    screen = HomeScreen(build_home_projection_fixture(HomeFixtureScenario(scenario)))
    app = ScreenHostApp(screen)
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        sidebar = app.screen.query("#home-sidebar")
        assert sidebar, f"Home is not in its two-column layout at {size}"
        boundary = sidebar.first().region.x
        rows = screen_text(app, width, height).splitlines()
        collisions = [row for row in rows if len(row) > boundary and row[boundary - 1] != " " and row[boundary] != " "]
        app.exit(None)

    assert not collisions, "Home paints left-column text against the sidebar:\n" + "\n".join(collisions[:3])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "surface",
    ["aeat-sync-overview--ready", "aeat-sync-filed-declarations--ready", "declarations-calendar--ready"],
)
async def test_no_table_header_is_clipped_while_the_row_has_width_to_spare(surface: str) -> None:
    """A clipped header stops the operator knowing what a column is.

    NO OTHER GATE CAN SEE THIS. The overflow check asserts nothing crosses the
    right edge, and nothing does -- truncation inside a table with room beside
    it paints exactly like a table that fits. So this reads the painted header
    row and compares it against the labels the screen actually declared.

    Measured before the fix: `Disponibilidad` painted as `Disponibilid` while
    the row stopped near column 78 of 120.
    """
    from textual.widgets import DataTable

    from ..devtools.frame import screen_text
    from ..devtools.workbench_fixtures import resolve_workbench_fixture

    width, height = TERMINAL_ORDINARY
    app = resolve_workbench_fixture(surface).build()
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        declared: list[str] = []
        for table in app.screen.query(DataTable):
            declared.extend(str(column.label).strip() for column in table.columns.values())
        painted = screen_text(app, width, height)
        app.exit(None)

    missing = [label for label in declared if label and label not in painted]
    assert not missing, f"{surface} clips these column headers out of the painted frame: {missing}"


@pytest.mark.asyncio
@pytest.mark.parametrize("size", SUPPORTED_TERMINAL_SIZES, ids=SUPPORTED_TERMINAL_SIZE_IDS)
@pytest.mark.parametrize("surface", ["home--ready", "aeat-sync-overview--ready"])
async def test_every_section_heading_is_separated_from_the_content_it_owns(surface: str, size: tuple[int, int]) -> None:
    """A heading fused to its rows makes the operator parse structure line by line.

    Read from the PAINTED frame, not the stylesheet. A margin declaration
    proves only that someone wrote it: the rule can be overridden, the widget
    can carry the wrong class, or a container can collapse the gap, and every
    one of those paints as the continuous run of data the operator reported
    while the declaration still reads correctly.

    Swept across every supported terminal, because the defect that prompted
    this gate was invisible at the ordinary size: Home mounted with the page
    already scrolled two rows down, so its opening heading was absent at 100
    and 80 columns while 120 looked perfect. A single-size rhythm gate reports
    green over a heading the operator never sees.

    The rhythm is deliberately asymmetric -- a wider gap above binds the
    heading away from the previous group, a narrower one below binds it to its
    own rows -- so this asserts BOTH: at least one blank line under the
    heading, and strictly more above it. Equal gaps leave the heading floating
    between the two groups, which is the defect in its subtler form.

    Blankness is measured inside the heading's OWN column span, not across the
    full painted line. Home is two columns, so a full-width test reports the
    gap above a left-column heading as occupied whenever the right column
    happens to paint on that row -- which says nothing about the rhythm the
    operator sees in that column.
    """
    from ..devtools.frame import screen_text
    from ..devtools.workbench_fixtures import resolve_workbench_fixture

    width, height = size
    app = resolve_workbench_fixture(surface).build()
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        headings = [
            (str(node.render()).strip(), node.region, node.has_class("cadrumo-heading-lead"))
            for node in app.screen.query(".cadrumo-heading")
            if str(node.render()).strip()
        ]
        painted = screen_text(app, width, height).splitlines()
        app.exit(None)

    assert headings, f"{surface} declares no .cadrumo-heading to check"

    checked = 0

    for heading, region, leads in headings:
        left, right = region.x, region.x + region.width
        column = [line[left:right] for line in painted]

        def blanks_after(index: int, column: list[str] = column) -> int:
            count = 0
            for line in column[index + 1 :]:
                if line.strip():
                    break
                count += 1
            return count

        def blanks_before(index: int, column: list[str] = column) -> int:
            count = 0
            for line in reversed(column[:index]):
                if line.strip():
                    break
                count += 1
            return count

        rows = [i for i, line in enumerate(column) if heading in line]
        if not rows:
            # A heading that OPENS its region is different in kind: it sits at
            # the top of the page, so the only way it can be missing is that
            # the operator was landed somewhere below it. That is the defect
            # this gate was built for -- Home mounted pre-scrolled and hid its
            # first heading at three of four supported sizes -- so it is never
            # excused, and treating it as below-the-fold made the gate blind
            # to exactly the regression it was written to catch.
            assert not leads, (
                f"{surface} at {width}x{height}: the region-opening heading "
                f"{heading!r} is not painted on arrival; the page is scrolled "
                f"past its own top"
            )
            # Any other heading may legitimately be below the fold: vertical
            # overflow is ordinary and scrollable, and the horizontal gates own
            # what must never be pushed out of sight.
            continue
        checked += 1
        row = rows[0]
        below, above = blanks_after(row), blanks_before(row)
        assert below >= 1, f"{surface}: {heading!r} is fused to its content (0 blank rows below)"
        # A heading that OPENS its region has no previous group to be separated
        # from, so the asymmetry has nothing to express there and equal gaps are
        # correct. The gap BELOW is still required of it: that one binds the
        # heading to its own rows and is the half the operator actually reported
        # missing. Keyed on the declared class, not on position, so a heading
        # that merely happens to sort first cannot claim the exemption.
        if leads:
            continue
        assert above > below, (
            f"{surface}: {heading!r} floats between groups "
            f"({above} blank rows above, {below} below); the gap above must be larger"
        )

    # Without this the below-the-fold skip above could quietly consume every
    # heading and leave the test asserting nothing at all.
    assert checked, f"{surface} at {width}x{height}: no heading was in view to check"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "surface",
    ["aeat-sync-overview--ready", "declarations-calendar--ready", "ledger-entries--ready"],
)
async def test_no_cell_is_truncated_while_its_row_still_has_room(surface: str) -> None:
    """Spare width beside a shortened value means the width was misallocated.

    Read from the painted frame and keyed on the ellipsis Textual writes when
    it shortens a cell, so this is independent of the sizing policy rather than
    a restatement of it -- a test that recomputed the policy would agree with
    any bug the policy contained.

    The header gate next to this one cannot see it: a clipped VALUE beside an
    empty right-hand margin paints exactly like a value that fits, and the
    overflow gates pass because nothing crosses the edge. That combination --
    invisible to every existing gate -- is how `Modelo 130 · 202` and
    `Declaraciones pr` survived in a suite that was green.

    A trailing margin is required before failing: at the narrow sizes a table
    legitimately fills its row, and shortening is then the correct behaviour
    rather than a misallocation.
    """
    from ..devtools.frame import screen_text
    from ..devtools.workbench_fixtures import resolve_workbench_fixture

    width, height = TERMINAL_ORDINARY
    app = resolve_workbench_fixture(surface).build()
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        painted = screen_text(app, width, height).splitlines()
        app.exit(None)

    offenders = [line for line in painted if "…" in line and len(line.rstrip()) < width - 2]
    assert not offenders, f"{surface} shortens a value while its row still has room:\n" + "\n".join(offenders)
