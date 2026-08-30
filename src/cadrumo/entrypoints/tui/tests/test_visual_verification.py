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
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, Input, Static

from ....application.flows.definition import CopyRef, FlowDefinition, FlowPage, FlowSection
from ....application.user_profile.fact_write import apply_manager_profile_field_mutation
from ....application.user_profile.login_session import login_profile
from ....application.user_profile.overview import build_profile_overview
from ....application.user_profile.registration import register_profile_with_credentials
from ....application.user_profile.status_projection import StatusFactRow, StatusPageData
from ....core.bucket_pointer import require_active_bucket_id
from ....core.flows import CheckpointAvailability, CopyRefKind, FlowMode, FlowWidgetKind
from ....core.presentation import FormField, FormPage
from ....entrypoints.tui.modelo.view.work_review import ModeloWorkReviewApp
from ....entrypoints.tui.profile.overview import ProfileManagerScreen
from ....entrypoints.tui.profile.status import StatusScreen
from ....entrypoints.tui.secret.login import LoginScreen
from ....entrypoints.tui.secret.registration import RegistrationScreen
from ....tests.modelo_work_review import build_real_modelo_work_review
from ....tests.profile_capsule import load_test_profile_record
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.terminal_sizes import SUPPORTED_TERMINAL_SIZES, TERMINAL_ORDINARY
from ..components.form_screen import FormApp
from ..components.host import ScreenHostApp
from ..components.theme import (
    CADRUMO_DARK_THEME_NAME,
    CADRUMO_LIGHT_THEME_NAME,
)
from ..components.widgets import ContentScroll
from ..devtools.frame import geometry_band, key_band
from ..flows.app import FlowScreen

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
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


_SIZES = SUPPORTED_TERMINAL_SIZES
"""The shared supported set; each size's reason lives with the declaration."""

_THEMES = [CADRUMO_LIGHT_THEME_NAME, CADRUMO_DARK_THEME_NAME]


@contextmanager
def _registration(tmp_path: Path) -> Iterator[ScreenHostApp[None]]:
    from ....core.credentials import assess_profile_password
    from ..devtools.fixture import registration_attempt

    del tmp_path  # unused: this surface writes nothing until a real submit, which no gate here does
    yield ScreenHostApp(RegistrationScreen(assess=assess_profile_password, register=registration_attempt))


@contextmanager
def _form(tmp_path: Path) -> Iterator[FormApp]:
    del tmp_path  # unused: FormApp holds no storage of its own
    yield FormApp(
        FormPage(
            title="TITLE",
            section="SECTION",
            fields=(FormField(key="a", label="A"), FormField(key="b", label="B")),
        ),
        translate=lambda key: key,
    )


@contextmanager
def _status(tmp_path: Path) -> Iterator[ScreenHostApp[None]]:
    del tmp_path  # unused: the projection is hand-built, matching this file's existing status fixture
    yield ScreenHostApp(
        StatusScreen(
            StatusPageData(
                active_profile_label="Subject",
                facts=(StatusFactRow(label="Field", value="Value"),),
            ),
        )
    )


@contextmanager
def _manager(tmp_path: Path) -> Iterator[ScreenHostApp[None]]:
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

    """
    from ....application.user_profile.registration import register_profile_with_credentials
    from ....tests.secure_sql import isolated_profile_storage_root

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=_VISUAL_LABEL,
            passphrase=_VISUAL_PASSWORD,
        )
        # Registration closes its own session, leaving the profile LOCKED. The
        # custody capsule is the sole profile authority, so the overview builder
        # and the write door below both need an authenticated one; logging in
        # derives the same DEK the capsule was sealed under.
        login_profile(name=_VISUAL_LABEL, passphrase_callback=lambda: _VISUAL_PASSWORD)
        profile_id = require_active_bucket_id()
        record = load_test_profile_record(profile_id)

        def persist(path: str, value: str):
            applied = apply_manager_profile_field_mutation(profile_id=profile_id, path=path, value=value)
            return build_profile_overview(applied, label=_VISUAL_LABEL)

        async def launch_source(source: object) -> None:  # pragma: no cover - not exercised by this gate
            del source

        yield ScreenHostApp(
            ProfileManagerScreen(
                build_profile_overview(record, label=_VISUAL_LABEL),
                persist=persist,
                launch_source=launch_source,
            )
        )


@contextmanager
def _login(tmp_path: Path) -> Iterator[ScreenHostApp[None]]:
    """The login screen, composed through the application interaction contract.

    Needs a real profile that exists but is LOCKED -- registration leaves it
    unlocked, so this logs back out before building the screen, matching
    the machine state ``login`` exists for. ``choices`` and ``preselected``
    come from the interaction module rather than being reproduced here,
    for the same reason the TUI reference-surface module now does: a hand-built
    choice list or a dropped preselection is the identical stand-in shape
    that bug was.
    """
    from ....application.user_profile.login_interaction import (
        attempt_profile_login,
        preselected_profile_login_id,
        profile_login_choices,
    )
    from ....application.user_profile.login_session import logout_active_profile
    from ....application.user_profile.registration import register_profile_with_credentials
    from ....tests.secure_sql import isolated_profile_storage_root

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=_VISUAL_LABEL,
            passphrase=_VISUAL_PASSWORD,
        )
        logout_active_profile()
        yield ScreenHostApp(
            LoginScreen(
                choices=profile_login_choices(),
                authenticate=attempt_profile_login,
                preselected=preselected_profile_login_id(None),
            )
        )


@contextmanager
def _status_populated(tmp_path: Path) -> Iterator[ScreenHostApp[None]]:
    """The status page with its NOTICES region genuinely populated.

    Built through the real production door, ``build_status_page_data()``,
    rather than a hand-built ``StatusPageData`` -- a freshly registered
    profile has zero AEAT-sourced calculation observations by construction,
    which is exactly the condition ``no_aeat_history_notice`` fires an INFO
    notice for, so this reaches a real notice without fabricating one.

    This is the fixture that would have caught the shipped defect:
    ``NoticeBand`` inherited Textual's ``Vertical`` default ``height: 1fr``,
    so once a notice was present it claimed the whole scroll column and the
    profile, profiles, auth and recovery panels beneath it did not paint at
    ANY terminal size. Every existing gate below builds ``status`` with no
    notices at all (:func:`_status`), so none of them could have seen it --
    a widget that eliminates its siblings passes edge, scroll, theme, tab
    and masking checks identically whether the siblings are there or not.
    """
    from ....application.user_profile.status_projection import build_status_page_data

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=_VISUAL_LABEL,
            passphrase=_VISUAL_PASSWORD,
        )
        yield ScreenHostApp(StatusScreen(build_status_page_data()))


@contextmanager
def _manager_populated(tmp_path: Path) -> Iterator[ScreenHostApp[None]]:
    """The manager with a REPEATABLE section's row count grown past one.

    ``manager`` (:func:`_manager`) always renders its full declared field
    set regardless of whether any field holds a value -- that is the
    surface's whole design, per its own module docstring -- so a bare
    profile and a fact-filled one have the IDENTICAL row set and would not
    exercise a region-eviction defect the way a populated status page does.
    What DOES change the structure is a repeatable section gaining a row,
    the same canonical application mutation ``add_row_action`` drives, added
    here directly rather than by pressing the button: the property under test
    is rendering, not the seam.

    ``activities`` is picked over ``attribution_entity_socios`` (used
    elsewhere in this package) because its only required field is
    ``description`` -- stable against the unrelated peer schema change that
    made a socio row require a ``clave`` this fixture would otherwise have
    to track.
    """
    from ....application.user_profile.section_rows import add_profile_repeatable_section_row

    with isolated_profile_storage_root(tmp_path=tmp_path):
        register_profile_with_credentials(
            recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
            label=_VISUAL_LABEL,
            passphrase=_VISUAL_PASSWORD,
        )
        # Same locked-capsule reason as the plain manager fixture: seeding facts
        # and building the overview both go through the capsule, which serves
        # neither without an authenticated session.
        login_profile(name=_VISUAL_LABEL, passphrase_callback=lambda: _VISUAL_PASSWORD)
        add_profile_repeatable_section_row(
            profile_id=require_active_bucket_id(),
            section_key="activities",
            values={"description": "Consultoria"},
        )
        profile_id = require_active_bucket_id()
        record = load_test_profile_record(profile_id)

        def persist(path: str, value: str):
            applied = apply_manager_profile_field_mutation(profile_id=profile_id, path=path, value=value)
            return build_profile_overview(applied, label=_VISUAL_LABEL)

        async def launch_source(source: object) -> None:  # pragma: no cover - not exercised by this gate
            del source

        yield ScreenHostApp(
            ProfileManagerScreen(
                build_profile_overview(record, label=_VISUAL_LABEL),
                persist=persist,
                launch_source=launch_source,
            )
        )


@contextmanager
def _question(tmp_path: Path) -> Iterator[ScreenHostApp[None]]:
    """The wizard question screen, carrying more content than a short terminal holds.

    Enrolled here because it is the surface the operator sees on every page
    of every flow, and it was the one full-screen surface these gates did
    not cover: it had collapsed the scroll host and the bordered panel into
    a single auto-height ``VerticalScroll``, which cannot scroll, so the
    overflow fell through to the Screen and the host sat in the tab order
    as a dead stop — the exact two defects the gates below already pin on
    every other surface.
    """
    del tmp_path  # unused: a bare flow screen holds no storage of its own
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
    yield ScreenHostApp(FlowScreen(definition, mode=FlowMode.MODIFY, registered_values={}))


def _many_page_flow() -> FlowScreen:
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
    return FlowScreen(definition, mode=FlowMode.MODIFY, registered_values={})


@contextmanager
def _modelo_review(tmp_path: Path) -> Iterator[ModeloWorkReviewApp]:
    """The real M100 review surface, built from genuine registry data.

    Enrolled because it was covered by NONE of these gates while carrying
    a live layout bound: its summary panel is capped as a fraction of the
    viewport so it cannot evict the casillas table at the 80-column floor,
    and nothing here or anywhere else was proving that bound holds.
    """
    yield ModeloWorkReviewApp(
        build_real_modelo_work_review(tmp_path, modelo="100", filing_year=2024, period_code="0A"),
    )


_SURFACES = [
    pytest.param(_registration, id="registration"),
    pytest.param(_form, id="form"),
    pytest.param(_status, id="status"),
    pytest.param(_status_populated, id="status-populated"),
    pytest.param(_question, id="question"),
    pytest.param(_manager, id="manager"),
    pytest.param(_manager_populated, id="manager-populated"),
    pytest.param(_login, id="login"),
    pytest.param(_modelo_review, id="modelo-review"),
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


_CONDITIONAL_REGION_SURFACES = [
    pytest.param(
        _status_populated,
        "panel-notices",
        ("panel-profile", "panel-profiles", "panel-auth", "panel-recovery"),
        id="status-populated",
    ),
    pytest.param(
        _manager_populated,
        "section-activities",
        ("section-identity", "section-preferences", "section-activities"),
        id="manager-populated",
    ),
]
"""Every surface audited for a REGION a populated state could evict, paired
with the id of the region that GROWS when populated and every region id
that must survive it growing.

This is the property that would have caught the shipped defect: ``NoticeBand``
inherited Textual's ``Vertical`` default ``height: 1fr``, so a populated
notices region silently claimed the whole scroll column. No existing gate in
this module could have seen it, because every one of them builds its surfaces
in their EMPTIEST reachable state (:func:`_status` carries no notices,
:func:`_manager` carries no extra rows).

Reproducing the exact original symptom -- the sibling panels' OWN
``region.height`` going to zero -- turned out not to be what actually
happens under a forced ``height: 1fr``, proven by driving it directly rather
than assumed: the siblings keep a nonzero region and ``display=True``, they
are simply pushed far down the SCROLLABLE column's virtual space (measured:
``panel-notices`` ballooned from 10 rows to 86, and ``panel-profile`` moved
from y=13 to y=89 on a 50-row viewport). A sibling-presence check alone is
therefore not sound here -- a widget that grows a hundredfold and one that
stays reasonable both leave every sibling ``display=True`` with a positive
height. The property that actually catches it is bounding the GROWING
region's own height against a fraction of the viewport: a region a couple of
notice lines or one added row justify never needs more than half the
terminal, so exceeding that is the growth this test exists to catch,
independent of exactly how far it then pushes anything below it.

Audited but NOT enrolled, with the reason stated rather than left silent:

- ``registration``/``login`` (:mod:`_credential_screen.py`): the refusal
  line is ``.credential-refusal``, a bare :class:`~textual.widgets.Static`,
  not a :class:`~textual.containers.Vertical` subclass with an unset
  height -- Static's own default height is ``auto``, so the specific
  Vertical-1fr defect shape this property targets does not apply to it.
  Driving either screen to a populated refusal needs a failed pilot
  submission on top of the storage fixture already required, which is
  disproportionate scaffolding for a region already structurally safe from
  this defect class.
- ``form`` (:mod:`_form_screen.py`): ``#form-refusal`` is the same bare
  Static shape. Its OTHER conditional region -- the summary table's row
  set growing as fields are edited -- is already exercised end to end by
  ``test_a_modal_secret_never_paints_its_value``, which drives every
  manager action's form through a row edit and re-render.
- ``question``: the flow engine's paged review table overflowing the
  question panel is a real conditional-region concern, but it is already
  covered on its own terms by ``test_the_screen_itself_never_scrolls_on_a_flow_surface``
  below, built for exactly that overflow rather than a bare presence check.
"""


_VIEWPORT = (100, 50)


@pytest.mark.asyncio
@pytest.mark.parametrize(("build", "growing_region_id", "region_ids"), _CONDITIONAL_REGION_SURFACES)
async def test_populating_a_conditional_region_does_not_evict_its_siblings(
    build,
    growing_region_id: str,
    region_ids: tuple[str, ...],
    tmp_path: Path,
) -> None:
    """A populated region stays proportionate, and every sibling stays painted.

    Two assertions, because the mutation-proof for this gate showed either
    ALONE is unsound. Bare presence (``display`` and a positive
    ``region.height``) is not enough: driving the shipped defect directly
    showed every sibling KEEPS a positive height and ``display=True`` even
    when the notices region balloons to 86 rows on a 50-row screen -- they
    are pushed far down the scrollable column's virtual space rather than
    zeroed out, so presence alone would have passed the broken code. What
    actually catches it is bounding the region that GROWS: content
    justifying a couple of lines or one added row never needs more than
    half the viewport, so a region claiming more than that is exactly the
    unconstrained-``fr``-in-an-``auto``-container shape that shipped.
    """
    with build(tmp_path) as app:
        async with app.run_test(size=_VIEWPORT) as pilot:
            await pilot.pause()
            _, height = _VIEWPORT
            try:
                growing = app.query_one(f"#{growing_region_id}", Static)
            except NoMatches:
                pytest.fail(f"#{growing_region_id} was never mounted -- the fixture must populate it")
            assert growing.region.height <= height // 2, (
                f"#{growing_region_id} claimed {growing.region.height} rows of a {height}-row viewport -- "
                f"a populated region must stay proportionate to its content, not consume everything below it"
            )

            starved = []
            for region_id in region_ids:
                try:
                    widget = app.query_one(f"#{region_id}", Static)
                except NoMatches:
                    starved.append(f"#{region_id} (not mounted)")
                    continue
                if not widget.display or widget.region.height <= 0:
                    starved.append(f"#{region_id} (display={widget.display}, height={widget.region.height})")
            assert not starved, f"populating one region evicted its sibling(s): {starved}"
            app.exit(None)


_INTERACTIVE_SURFACES = [
    pytest.param(_registration, id="registration"),
    pytest.param(_form, id="form"),
    pytest.param(_manager, id="manager"),
    pytest.param(_manager_populated, id="manager-populated"),
    pytest.param(_login, id="login"),
    pytest.param(_modelo_review, id="modelo-review"),
]
"""Surfaces whose controls an operator reaches by tabbing.

THE PREDICATE, NOT A LIST OF INSTANCES: a surface belongs here when moving
between its controls is a tab cycle. Two shapes fall outside it. Read-only
chrome has nothing to tab through -- ``status`` and its populated variant
each expose a single table. And engine-paged navigation moves the flow's
own cursor between pages rather than a tab cycle between controls, which
is what ``question`` does.

Stated as a predicate deliberately, because the previous rationale named
the two surfaces excluded when it was written. Both its reasons still
held. But the enrolled set grew, and three further surfaces fell outside
the gate without anyone deciding they should: two populated variants and
the modelo review. A rationale that enumerates instances goes stale with
no edit, no failure and no signal, and a well-argued one is the worst
kind, because a reader who checks it finds sound reasons and stops.

Anything added to ``_SURFACES`` belongs here too unless it matches one of
the two shapes above; if the reason it does not fit cannot be stated in
those terms, that is evidence the exclusion is incidental."""


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

            # Identity, not type name: a stalled cycle lands on ONE widget
            # repeatedly, and repeated type names hide that behind what reads
            # like a short cycle.
            stalled = len({id(widget) for widget in visited}) == 1 and len(chain) > 1
            remedy = (
                " DO NOT RESOLVE THIS BY REMOVING THIS SURFACE FROM THE INTERACTIVE PREDICATE:"
                " the predicate is correct and the surface does have a tab cycle to prove."
                " The defect is the screen's focus routing, and un-enrolling it restores exactly"
                " the invisibility that let this survive."
            )
            assert not stalled, (
                f"focus never advances: every tab landed on the same widget, "
                f"{type(visited[0]).__name__}, while the chain holds "
                f"{[type(w).__name__ for w in chain]}. Nothing after the first focusable is "
                f"reachable by keyboard on this surface.{remedy}"
            )
            assert visited[-1] is chain[0], (
                f"tab did not close the cycle: {[type(w).__name__ for w in visited]}{remedy}"
            )
            assert set(visited) == set(chain), (
                f"tab skipped a control: chain={[type(w).__name__ for w in chain]} "
                f"visited={[type(w).__name__ for w in visited]}{remedy}"
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
            # Sample INSIDE the button. Buttons are one cell tall in this theme, so a
            # y + 1 probe reads the row BELOW the widget, which is unaffected by focus
            # and therefore identical in both states -- the assertion below would then
            # fail no matter how visible focus actually is.
            probe_x = target.region.x + min(1, max(target.region.width - 1, 0))
            probe_y = target.region.y + target.region.height // 2
            unfocused = app.screen.get_style_at(probe_x, probe_y)

            app.screen.set_focus(target)
            await pilot.pause()
            focused = app.screen.get_style_at(probe_x, probe_y)

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


@pytest.mark.asyncio
@pytest.mark.parametrize(("width", "height"), _SIZES)
@pytest.mark.parametrize("review", [False, True], ids=["question", "review"])
async def test_a_flow_surface_has_exactly_one_visible_vertical_scroll_owner(
    width: int,
    height: int,
    review: bool,
) -> None:
    """Scrolling belongs to one designated host, never competing hosts.

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
    flow = _many_page_flow()
    host = ScreenHostApp(flow)
    async with host.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        if review:
            await pilot.press("f2")
            await pilot.pause()
        screen = host.screen

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
        visible_owners = [
            widget
            for widget in screen.walk_children()
            if isinstance(widget, ScrollableContainer) and widget.display and widget.show_vertical_scrollbar
        ]
        assert len(visible_owners) == 1, (
            f"expected one visible vertical scroll owner at {width}x{height}, got "
            f"{[type(widget).__name__ for widget in visible_owners]}"
        )
        host.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("build", _SURFACES)
@pytest.mark.parametrize(("width", "height"), _SIZES)
async def test_every_surface_reports_no_geometry_findings(build, width: int, height: int, tmp_path: Path) -> None:
    """Drive the canonical geometry reader over every enrolled surface.

    ``devtools.frame.geometry_band`` already judges the three painted-layout
    properties, and until now nothing executed it: its only caller was the
    standalone replay tool, which runs when a human chooses to and never in
    CI. A reader with no gate is weaker than an orphan, because an unused-
    symbol sweep clears it and it looks covered.

    This is not a fourth copy of the gates above. Those prove side-edge
    overflow, scrollability and theme rendering per surface, and exactly one
    of them -- the flow surface's -- proves the single-scroll-owner property,
    with a bespoke fixture because that is where the defect was found. Here
    that property is proven for EVERY enrolled surface, which is what caught
    nothing when a summary panel gained ``overflow-y: auto`` inside an
    existing scroll host.

    Reported as a set rather than one finding at a time: a surface with two
    geometry defects should fail once naming both, not twice.
    """
    with build(tmp_path) as app:
        async with app.run_test(size=(width, height)) as pilot:
            await pilot.pause()
            findings = geometry_band(app, width)
            assert not findings, f"{width}x{height} painted geometry is defective: {findings}"
            app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("build", _SURFACES)
async def test_every_declared_binding_is_actually_offered(build, tmp_path: Path) -> None:
    """A key a surface declares must be a key the operator can press.

    Drives ``devtools.frame.key_band``, which reads ``active_bindings`` --
    what is offered on THIS screen in THIS state, not what the class
    declared. The two can disagree: a binding declared on a host whose
    content lives on sibling screens never resolves, because the host is
    never the active screen. That happened on the flow surface, and the
    workaround was to duplicate the binding onto both page screens.

    So this gate pins the workaround's EFFECT rather than its shape: if a
    redesign stops duplicating, the binding silently stops resolving and
    nothing else in this suite would notice. A declared-but-unreachable
    affordance is invisible to geometry, focus order and rendered text
    alike -- it is not painted, so no pixel changes.

    Not parametrised over sizes, deliberately: bindings do not vary with
    terminal geometry, and multiplying nine surfaces by four sizes would
    buy thirty-six cases proving one size-invariant property.
    """
    with build(tmp_path) as app:
        async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
            await pilot.pause()
            offered = key_band(app)
            declared = [binding.key for binding in getattr(type(app.screen), "BINDINGS", ())]
            unresolved = [key for key in declared if not any(entry.startswith(f"{key}=") for entry in offered)]

            assert declared, "a surface that declares no bindings makes this gate vacuous for it"
            assert not unresolved, (
                f"declared but never offered to the operator: {unresolved}; the surface offers {sorted(offered)}"
            )
            app.exit(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("build", _SURFACES)
async def test_every_surface_keeps_the_affordances_textual_gives_a_screen(build, tmp_path: Path) -> None:
    """Focus movement and copy belong to every screen, declared by none of them.

    ``Screen`` binds tab, shift+tab and copy for free, and a subclass's
    runtime table starts as a copy of the merged class table carrying
    them. A screen that REPLACES that table -- the obvious way to attach
    translated footer descriptions at mount -- keeps only the keys it
    named and drops the ones it never had to name. Four surfaces shipped
    that way: tab was not bound at all, so focus could not leave the
    first control on a page whose focus chain was healthy and whose
    widgets were all focusable.

    Nothing else here could see it. The sibling gate above checks that
    every DECLARED binding is offered, and these were never declared;
    focus order, geometry and rendered text were all clean, because an
    unbound key paints nothing.

    Read from Textual's own ``Screen.BINDINGS`` rather than a list
    repeated here, which would pass vacuously the day Textual adds a
    fourth.

    Asserted over KEYS rather than actions, because a focused widget may
    legitimately own a key the screen also binds: with a text cursor in
    an input, copy means copy the selection, so ``Input`` answers the
    copy key instead of the screen. The operator still has the
    affordance, which is what this gate is about. A key answered by the
    WRONG action is a different question; the tab-cycle gate asks it for
    the two focus keys, where the answer does have to be the screen's,
    on the surfaces carrying enough controls for a cycle to mean
    anything.
    """
    inherited = {key for binding in Screen.BINDINGS for key in binding.key.split(",")}
    with build(tmp_path) as app:
        async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
            await pilot.pause()
            offered = set(app.screen.active_bindings)
            missing = sorted(inherited - offered)

            assert inherited, "Textual stopped binding anything on Screen; this gate has nothing left to protect"
            assert not missing, (
                f"the surface dropped the bindings Textual gives every Screen: {missing}. "
                "Do not fix this by re-declaring them on the screen -- the cause is a runtime "
                "binding table replaced wholesale instead of re-described in place."
            )
            app.exit(None)
