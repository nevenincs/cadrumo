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

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic import BaseModel
from textual.containers import ScrollableContainer
from textual.widgets import Button, DataTable, Input

from .....application.flows import CopyRef, FlowDefinition, FlowPage, FlowSection
from .....application.user_profile import ProfileRepository, build_profile_overview, register_profile_with_credentials
from .....core import require_active_bucket_id
from .....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from .....tests.manager_pilot import wait_until_settled
from .....tests.secure_sql import isolated_profile_storage_root
from .. import (
    FlowTuiApp,
    FormApp,
    FormField,
    FormPage,
    FormScreen,
    LoginApp,
    ProfileManagerApp,
    RegistrationApp,
    StatusApp,
    StatusFactRow,
    StatusPageData,
)
from .._theme import CADRUMO_DARK_THEME_NAME, CADRUMO_LIGHT_THEME_NAME, ContentScroll

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_inbound_adapter,
]
"""``integration``, not ``unit``: a test carries EXACTLY ONE execution-lane
marker (``test_marker_integrity.py``), so a per-``pytest.param`` override
on only the ``manager``/``login`` entries would leave those items carrying
BOTH ``unit`` (from this module-level mark) and ``integration`` at once --
a real gate violation, not a style choice, and the shape that turned into a
collection-time crash the first time this was tried. ``manager`` and
``login`` drive a real encrypted profile through
``isolated_profile_storage_root`` -- real SQLite, real Argon2id key
derivation -- the same reason ``test_manager_screen.py`` is ``integration``
rather than ``unit``; the whole module moves with them rather than
duplicating every gate into a unit-only and an integration-only copy."""

_VISUAL_LABEL = "Visual Verification Subject"
_VISUAL_PASSWORD = "visual-verification-operator-secret"  # noqa: S105 - synthetic test fixture


class _VisualAnswers(BaseModel):
    """Trivial answers model; only its type identity is consumed."""


_SIZES = [(80, 24), (120, 40), (200, 50)]
"""A minimum-size terminal, an ordinary one, and a wide one.

80x24 is the floor a real terminal can be, and the size at which an
overflowing layout stops being cosmetic and starts hiding controls.
"""

_THEMES = [CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME]


@contextmanager
def _registration(tmp_path: Path) -> Iterator[RegistrationApp]:
    from .....application.user_profile import assess_passphrase
    from .....entrypoints.cli._config._manager_frontend import attempt_registration

    del tmp_path  # unused: this surface writes nothing until a real submit, which no gate here does
    yield RegistrationApp(assess=assess_passphrase, register=attempt_registration)


@contextmanager
def _form(tmp_path: Path) -> Iterator[FormApp]:
    del tmp_path  # unused: FormApp holds no storage of its own
    yield FormApp(
        FormPage(
            title="TITLE",
            section="SECTION",
            fields=(FormField(key="a", label="A"), FormField(key="b", label="B")),
        ),
    )


@contextmanager
def _status(tmp_path: Path) -> Iterator[StatusApp]:
    del tmp_path  # unused: the projection is hand-built, matching this file's existing status fixture
    yield StatusApp(
        StatusPageData(
            active_profile_label="Subject",
            facts=(StatusFactRow(label="Field", value="Value"),),
        ),
    )


@contextmanager
def _manager(tmp_path: Path) -> Iterator[ProfileManagerApp]:
    """The manager, composed the way ``present_profile_manager`` composes it.

    ``manager`` was absent from every gate in this module -- the geometry
    and reachability defects that shipped on it (a permanently-unreachable
    action row, a value column sitting off the right edge) were both found
    by hand, and neither would have been caught here. It was absent because
    it needs a real, unlocked profile, which none of the other builders
    require; a real profile is precisely what ``isolated_profile_storage_root``
    plus ``register_profile_with_credentials`` provide -- the same primitive
    ``test_manager_screen.py`` already uses, real Argon2id and real AEAD, no
    stand-in storage.

    ``manager_actions()`` is passed for the same reason it now is in
    ``dev/tui/_surfaces.py``: building the screen without it renders cleanly
    and shows a manager with zero buttons, which is exactly the bug this
    enrollment exists to catch on a real terminal render rather than by hand.
    """
    from .....application.user_profile import register_profile_with_credentials
    from .....entrypoints.cli._config._manager_actions import manager_actions
    from .....entrypoints.cli._config._manager_frontend import (
        build_active_profile_overview,
        persist_active_profile_field,
        profile_field_value_refusal,
    )
    from .....tests.secure_sql import isolated_profile_storage_root

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_VISUAL_LABEL, passphrase=_VISUAL_PASSWORD)
        yield ProfileManagerApp(
            build_active_profile_overview(),
            persist=persist_active_profile_field,
            actions=manager_actions(),
            validate=profile_field_value_refusal,
        )


@contextmanager
def _login(tmp_path: Path) -> Iterator[LoginApp]:
    """The login screen, composed the way ``present_login`` composes it.

    Needs a real profile that exists but is LOCKED -- registration leaves it
    unlocked, so this logs back out before building the screen, matching
    the machine state ``login`` exists for. ``choices`` and ``preselected``
    come from the real frontend functions rather than being reproduced here,
    for the same reason ``dev/tui/_surfaces.py`` now does: a hand-built
    choice list or a dropped preselection is the identical stand-in shape
    that bug was.
    """
    from .....application.user_profile import logout_active_profile, register_profile_with_credentials
    from .....entrypoints.cli._config._login_frontend import (
        _login_choices,
        attempt_login,
        preselected_profile_id,
    )
    from .....tests.secure_sql import isolated_profile_storage_root

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_VISUAL_LABEL, passphrase=_VISUAL_PASSWORD)
        logout_active_profile()
        yield LoginApp(
            choices=_login_choices(),
            authenticate=attempt_login,
            preselected=preselected_profile_id(None),
        )


@contextmanager
def _question(tmp_path: Path) -> Iterator[FlowTuiApp]:
    """The wizard question screen, carrying more content than a short terminal holds.

    Enrolled here because it is the surface the operator sees on every page
    of every flow, and it was the one full-screen surface these gates did
    not cover: it had collapsed the scroll host and the bordered panel into
    a single auto-height ``VerticalScroll``, which cannot scroll, so the
    overflow fell through to the Screen and the host sat in the tab order
    as a dead stop — the exact two defects the gates below already pin on
    every other surface.
    """
    del tmp_path  # unused: a bare FlowTuiApp holds no storage of its own
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
    yield FlowTuiApp(definition, mode=FlowMode.MODIFY, registered_values={})


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
    pytest.param(_manager, id="manager"),
    pytest.param(_login, id="login"),
]
"""Every builder here takes ``tmp_path`` and is a context manager, uniformly
-- ``manager`` and ``login`` need it live for the whole test body (their
persist/auth doors read storage at RUNTIME, not only at build time), and
the four that do not simply ignore the argument. A bare ``() -> App``
builder cannot express "this needs a resource alive for the test's
duration" at all, which is exactly the gap that let ``manager`` and
``login`` go unenrolled."""


@pytest.mark.asyncio
@pytest.mark.parametrize("build", _SURFACES)
@pytest.mark.parametrize(("width", "height"), _SIZES)
@pytest.mark.parametrize("theme", _THEMES)
async def test_nothing_is_painted_past_the_side_edges(
    build,
    width: int,
    height: int,
    theme: str,
    tmp_path: Path,
) -> None:
    """No widget may extend past the left or right edge of the screen.

    Horizontal only, deliberately. Content taller than the viewport is
    what a scroll container is for and is not a defect; content wider
    than the terminal is one, because these surfaces scroll vertically
    only, so anything past the right edge is a control the operator
    cannot reach and text they cannot read. Checked at 80 columns
    because that is where a layout that looks generous on a wide
    terminal starts truncating.

    This is the exact gate that would have caught the manager's value
    column sitting off the right edge, had ``manager`` been enrolled.
    """
    with build(tmp_path) as app:
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
async def test_content_taller_than_the_screen_stays_reachable(build, width: int, height: int, tmp_path: Path) -> None:
    """Overflowing content must be scrollable, not merely overflowing.

    On a 24-row terminal the registration form is taller than the screen,
    which is fine — as long as the operator can scroll to the rest of it.
    A scroll host that overflows without being able to scroll has simply
    hidden its own submit button.
    """
    with build(tmp_path) as app:
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
async def test_every_surface_actually_renders_under_both_appearances(build, theme: str, tmp_path: Path) -> None:
    """The compositor produces real output, not an empty frame.

    Exporting the screenshot forces a full render through the same path a
    terminal drives, so a theme token that fails to resolve surfaces here
    rather than on the operator's screen.
    """
    with build(tmp_path) as app:
        async with app.run_test(size=(100, 30)) as pilot:
            app.theme = theme
            await pilot.pause()
            rendered = app.export_screenshot()
            assert "<text" in rendered, "the surface rendered no text at all"
            assert len(rendered) > 1000, "the surface rendered a suspiciously empty frame"
            app.exit(None)


_INTERACTIVE_SURFACES = [
    pytest.param(_registration, id="registration"),
    pytest.param(_form, id="form"),
    pytest.param(_manager, id="manager"),
    pytest.param(_login, id="login"),
]
"""Surfaces with a real tab cycle. ``status`` and ``question`` are excluded
deliberately: ``status`` is read-only chrome with no operator input, and
``question`` is driven by the flow engine's own paged navigation rather
than a plain tab cycle -- neither is what this gate exists to pin."""


@pytest.mark.asyncio
@pytest.mark.parametrize("build", _INTERACTIVE_SURFACES)
async def test_tab_visits_every_control_and_comes_back(build, tmp_path: Path) -> None:
    """Every tab stop must be a real control, and the cycle must close.

    The defect this pins shipped: a scrollable container is focusable by
    default, so Tab landed on it, showed nothing, did nothing, and the
    form read as broken. Note that "the cycle closes" alone would NOT
    have caught it — a scroll host in the chain still gets visited and
    still closes the cycle. What discriminates is the membership check:
    no container may be a tab stop, only controls the operator can
    actually operate.
    """
    with build(tmp_path) as app:
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


_MULTI_BUTTON_SURFACES = [
    pytest.param(_form, id="form"),
    pytest.param(_manager, id="manager"),
    pytest.param(_login, id="login"),
]
"""Surfaces carrying at least two buttons to compare focus against. Bare
``registration`` is excluded -- it has exactly one (``btn-create``) -- and
the gate itself asserts the precondition rather than assuming it, so a
surface that stops qualifying reds here instead of passing vacuously."""


@pytest.mark.asyncio
@pytest.mark.parametrize("build", _MULTI_BUTTON_SURFACES)
@pytest.mark.parametrize("theme", _THEMES)
async def test_a_focused_button_is_painted_differently_from_an_unfocused_one(
    build,
    theme: str,
    tmp_path: Path,
) -> None:
    """Focus must be visible in the cells, not merely true in a property.

    Read off the rendered screen through ``get_style_at``: a rule that
    fails to apply leaves the property set and the pixels unchanged, and
    only the pixels are what the operator sees. Was pinned only against
    ``form``; ``manager`` and ``login`` are real buttoned surfaces this
    property is equally a claim about, and the manager's own button row
    was the site of the surface that went unenrolled entirely.
    """
    with build(tmp_path) as app:
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
@pytest.mark.parametrize("build", _SURFACES)
async def test_a_masked_field_never_paints_its_secret(build, tmp_path: Path) -> None:
    """No ``Input`` this application marks ``password=True`` may render its value.

    Expressed as a PROPERTY over every enrolled surface rather than naming
    ``registration`` specifically -- the prior shape of this gate. A
    name-enumerated gate only proves the names on its list; the export
    passphrase field went two weeks in clear on a surface (the manager's
    export action) this gate never looked at, because nothing generalised
    "collects a secret" past the one screen it was written against. This
    version walks every ``Input`` on whichever surface is under test and
    checks the ones the application itself declared masked, so a new
    masked field on any FUTURE surface is covered on arrival rather than
    needing its own name added here.

    Cannot see a secret collected inside a MODAL the base screen pushes only
    on a button press (the manager's certificate, passphrase and export
    forms) -- this renders the surface as built, once, and does not drive
    navigation into a nested screen. That boundary is closed separately by
    ``test_a_modal_secret_never_paints_its_value`` below, which drives every
    manager action that opens one.

    Asserting ``password=True`` on the widget proves the flag, not the
    output. This reads the exported render and requires the secret to be
    absent from it, which is the property that matters on a shared screen
    or in a captured session log.
    """
    with build(tmp_path) as app:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            masked = [widget for widget in app.screen.query(Input) if widget.password]
            for index, field in enumerate(masked):
                field.value = f"SENTINEL-SECRET-VALUE-{index}"
            await pilot.pause()
            rendered = app.export_screenshot()
            leaked = [
                f"#{field.id}" for index, field in enumerate(masked) if f"SENTINEL-SECRET-VALUE-{index}" in rendered
            ]
            assert not leaked, f"masked field(s) painted their secret in clear: {leaked}"
            app.exit(None)


def _open_form(app: ProfileManagerApp) -> FormScreen | None:
    """The topmost pushed :class:`FormScreen`, or ``None`` if none is open.

    Duplicated from ``test_manager_action_seam.py`` rather than imported:
    that module is a sibling test file, not a shared fixture home, and this
    is the smallest of its handful of pilot-driving helpers.
    """
    return next((screen for screen in reversed(app.screen_stack) if isinstance(screen, FormScreen)), None)


async def _wait_for_form(pilot, app: ProfileManagerApp) -> FormScreen | None:
    """Wait for a pressed action to either open a page or conclude without one.

    A race between two endings, not a settle-wait: an action mid-form is
    blocked on its worker thread waiting for THIS test's own dismissal, so
    waiting for quiescence here would deadlock against the very answer only
    the pilot can give.
    """
    for _ in range(80):
        await pilot.pause()
        form = _open_form(app)
        if form is not None:
            return form
        if app._pending_action is None:
            return None
    return _open_form(app)


@pytest.mark.asyncio
async def test_a_modal_secret_never_paints_its_value(tmp_path: Path) -> None:
    """No form a manager action opens may paint a ``secret`` field's value.

    Closes the boundary the surface-level sweep above states rather than
    silently assumes. Expressed as a property over EVERY shipped manager
    action and EVERY field its own ``FormPage`` declares ``secret=True`` --
    never as a check against the two dialogs (export, passphrase) known to
    carry one today, so a future action introducing its own secret field is
    covered on arrival rather than needing its own name added here.

    Checked two ways at once, because the second is the one that matters:
    ``#edit-input`` is the small per-row dialog, already proven masked by
    the surface-level sweep once a form is open on it, but a committed
    value is not painted there -- it is painted in the FORM'S OWN SUMMARY
    TABLE, which ``FormScreen._render_rows`` fills from
    ``self._values.get(form_field.key, "")`` unconditionally, with no read
    of ``form_field.secret`` at all. That is read directly off the table
    cell rather than sniffed out of the exported screenshot: a screenshot
    substring match is exactly as reliable as the column happens to be wide
    relative to the sentinel, proven by hand against this very cell before
    writing this assertion -- a longer sentinel came back truncated to 5
    characters in the rendered SVG while the cell's own stored value still
    held all 18, which would have been a false-negative width accident
    dressed up as a passing gate. Reading ``table.get_cell`` is not subject
    to viewport width at all.
    """
    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(label=_VISUAL_LABEL, passphrase=_VISUAL_PASSWORD)
        aggregate = ProfileRepository().load(require_active_bucket_id())
        from .....entrypoints.cli._config._manager_actions import manager_actions
        from .....entrypoints.cli._config._manager_frontend import persist_active_profile_field

        app = ProfileManagerApp(
            build_profile_overview(aggregate.record, label=_VISUAL_LABEL),
            persist=lambda path, value: persist_active_profile_field(path, value, label=_VISUAL_LABEL),
            actions=manager_actions(),
        )
        secret_checks_run = 0
        async with app.run_test(size=(160, 60)) as pilot:
            await pilot.pause()
            for action in manager_actions():
                await pilot.click(f"#action-{action.key}")
                form = await _wait_for_form(pilot, app)
                if form is None:
                    # No modal opened -- a refusal (censal-pull with no
                    # provider configured) or an action with nothing to
                    # collect. Nothing to check, and correctly so: this
                    # loop must not require every action to open a form,
                    # only that the ones that do are checked.
                    continue
                secret_fields = [field for field in form._page.fields if field.secret]
                table = form.query_one("#form-table", DataTable)
                for field in secret_fields:
                    secret_checks_run += 1
                    sentinel = f"LEAK-{action.key}-{field.key}"
                    table.move_cursor(row=[str(row.value) for row in table.rows].index(field.key))
                    table.action_select_cursor()
                    await pilot.pause()
                    edit_input = app.screen.query_one("#edit-input", Input)
                    assert edit_input.password, (
                        f"{action.key}.{field.key} is declared secret but its own edit dialog does not mask it"
                    )
                    edit_input.value = sentinel
                    await pilot.click("#btn-edit-save")
                    await pilot.pause()
                    # The property under test: read the SUMMARY TABLE's own
                    # cell, not the edit dialog that already closed and not
                    # a screenshot substring search (see the docstring's
                    # width-truncation proof for why the latter is unsound).
                    cell = table.get_cell(field.key, list(table.columns)[1])
                    rendered_cell = str(cell)
                    assert sentinel not in rendered_cell, (
                        f"{action.key}.{field.key} is declared secret but its committed value is painted in "
                        f"clear in the form's own summary table: {rendered_cell!r}"
                    )
                await pilot.click("#btn-form-cancel")
                await wait_until_settled(app, pilot)
            app.exit(None)
        assert secret_checks_run >= 2, (
            "the fixture must exercise at least the export and passphrase dialogs' secret fields, or this test "
            "proves nothing -- got 0 or 1, which means a shipped action lost its secret field or its own gate"
        )


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
