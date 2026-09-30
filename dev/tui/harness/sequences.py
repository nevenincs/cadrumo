"""Sequence-backed review scenarios: the Modelo pages over a real calculated declaration.

Every other harness surface opens over an in-memory fixture or a bare profile,
so none of them can show a Modelo workspace: those pages exist only for a
declaration that was created and calculated through the registry. The
documentation already builds exactly that state -- each ``cli-sequence`` runs
the real CLI chain in a hermetic sandbox and keeps the outcome as a committed
golden -- so a scenario names one of those sequences rather than restating its
steps.

A scenario runs its sequence once through the documentation engine, checks the
result against the committed golden, and composes the installed workbench over
the sandbox the sequence leaves behind, exactly as ``aeat app tui`` composes it.
Every capture then builds a fresh app at its own size and appearance and walks
the operator's path to its page: Declarations, the declaration's row, and the
keys the filer presses on the workbench.

Every capture shares the one sandbox, so no walk may change the declaration: a
walk stops at a question or a review and never answers it. The review page
stages a change in memory and checks it, which saves nothing; the recalculation
page is captured only where pressing ``c`` asks before it recalculates.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final, Protocol, cast

from pydantic import BaseModel, ConfigDict
from textual.app import App
from textual.pilot import Pilot
from textual.screen import Screen
from textual.widgets import Button, DataTable, Input
from textual.worker import WorkerCancelled

from cadrumo.application.modelo.work_form_models import ModeloFormOrigin
from cadrumo.application.user_profile.login_interaction import profile_login_choices
from cadrumo.core.config_support import TuiAppearance
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.tui.components.dialogs import ConfirmScreen
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.components.theme import resolve_theme_name
from cadrumo.entrypoints.tui.declarations.controller import DeclarationsWorkspaceScreen
from cadrumo.entrypoints.tui.installed_session import compose_authenticated_root_inputs_provider
from cadrumo.entrypoints.tui.launcher import (
    InstalledWorkbenchRootCompositionV1,
    compose_installed_workbench_root,
    operation_services_scope,
)
from cadrumo.entrypoints.tui.modelo.workbench.bulk_confirm import BulkConfirmScreen
from cadrumo.entrypoints.tui.modelo.workbench.casilla_list import CasillaList, CasillaListEntry
from cadrumo.entrypoints.tui.modelo.workbench.editor import CasillaEditorScreen
from cadrumo.entrypoints.tui.modelo.workbench.issues import WorkbenchIssuesScreen
from cadrumo.entrypoints.tui.modelo.workbench.review import EditReviewScreen
from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen
from cadrumo.entrypoints.tui.modelo.workbench.search import WorkbenchSearchPanel
from cadrumo.entrypoints.tui.modelo.workbench.sources import WorkbenchSourcesScreen
from cadrumo.entrypoints.tui.modelo.workbench.vocabulary import TYPED_EDITABILITIES
from cadrumo.entrypoints.tui.navigation import TuiScreenContextV1
from cadrumo.entrypoints.tui.tests.frame import capture
from dev.docs.sequences.checks import discover_sequences
from dev.docs.sequences.compare import check_transcript
from dev.docs.sequences.golden_store import golden_path, read_golden
from dev.docs.sequences.runner import SANDBOX_PROFILE_LABEL, SequenceSandbox, executed_sequence_sandbox

DECLARATIONS_PAGE: Final[str] = "declarations"
ISSUES_PAGE: Final[str] = "issues"
REVIEW_PAGE: Final[str] = "review"
RECALCULATE_PAGE: Final[str] = "recalculate"
EDITOR_PAGE: Final[str] = "editor"
BULK_CONFIRM_PAGE: Final[str] = "bulk-confirm"
_DECLARATIONS_DESTINATION: Final = "workbench.declarations"
_GOLDEN_PROBLEMS_KEPT: Final[int] = 5
_SETTLE_ROUNDS: Final[int] = 20
"""How many times settling waits again after an exclusive worker was replaced by a newer one."""
_PAGES_SEARCHED: Final[int] = 64
"""How many workbench pages the review walk turns through looking for a box it can stage."""
_TYPED_SAMPLES: Final[Mapping[str, str]] = {
    "money": "100",
    "decimal": "100",
    "integer": "1",
    "ratio": "50",
    "year": "2026",
    "text": "SINTETICO",
}
"""What the review walk types, by the box's value kind; a kind not listed is passed over."""

type _Walk = Callable[["SequenceScenario", Pilot[object]], Awaitable[None]]


class _WorkerCompletion(Protocol):
    async def wait_for_complete(self) -> None: ...


class ScenarioError(RuntimeError):
    """A scenario that cannot produce the pages it names."""


@dataclass(frozen=True)
class SequenceScenario:
    """One documentation sequence, and the declaration whose pages it shows."""

    sequence_id: str
    modelo: str
    summary: str
    period: str | None = None
    """Names the declaration when the sequence leaves more than one of this modelo."""
    verified: bool = True
    """Whether the sequence verifies the declaration, so its workbench lists what verification found."""
    filed: bool = False
    """Whether the sequence records the declaration as filed, so its workbench accepts no change."""
    assumes: bool = True
    """Whether the calculation leaves assumed values for the filer to confirm."""


SEQUENCE_SCENARIOS: Final[dict[str, SequenceScenario]] = {
    scenario.sequence_id: scenario
    for scenario in (
        SequenceScenario(
            "modelo-303-first-quarter", "303", "Modelo 303, first quarter, verified and filed", filed=True
        ),
        SequenceScenario(
            "verification-reports-incomplete", "303", "Modelo 303 calculated but not complete", verified=False
        ),
        SequenceScenario("modelo-130-first-quarter", "130", "Modelo 130, first quarter, verified"),
        SequenceScenario("modelo-100-renta-2025", "100", "Modelo 100, renta 2025, verified"),
        SequenceScenario("modelo-349-first-quarter", "349", "Modelo 349, first quarter, verified", assumes=False),
        SequenceScenario("modelo-390-annual-2025", "390", "Modelo 390, annual summary 2025, verified"),
    )
}
"""Every scenario, by the sequence id it runs. The sequence is the definition;
this only chooses which declaration of its outcome to show."""


def _workbench(scenario: SequenceScenario, app: App[object]) -> ModeloWorkbenchScreen:
    screen = app.screen
    if not isinstance(screen, ModeloWorkbenchScreen):
        raise ScenarioError(f"{scenario.sequence_id}: the declaration opened {type(screen).__qualname__}")
    return screen


async def _open_sources(_scenario: SequenceScenario, pilot: Pilot[object]) -> None:
    await pilot.press("s")
    await _settle(pilot)


type _BoxAction = Callable[[SequenceScenario, Pilot[object], CasillaList, CasillaListEntry], Awaitable[bool]]


async def _first_box(scenario: SequenceScenario, pilot: Pilot[object], act: _BoxAction, wanted: str) -> None:
    """Try ``act`` on each box, page by page, until one answers as ``wanted``."""
    workbench = _workbench(scenario, pilot.app)
    listed: tuple[object, ...] | None = None
    for _ in range(_PAGES_SEARCHED):
        casilla_list = workbench.query_one(CasillaList)
        items = casilla_list.items
        if items == listed:
            break
        listed = items
        for entry in items:
            if isinstance(entry, CasillaListEntry) and await act(scenario, pilot, casilla_list, entry):
                return
        await pilot.press("right_square_bracket")
        await _settle(pilot)
    raise ScenarioError(f"{scenario.sequence_id}: no box on the workbench {wanted}")


async def _open_review(scenario: SequenceScenario, pilot: Pilot[object]) -> None:
    """Stage one typed value the application reads cleanly, then ask for the review, which checks it first."""
    await _first_box(scenario, pilot, _stage, "accepted a typed value to review")
    await pilot.press("R")
    await _settle(pilot)


async def _open_panel(pilot: Pilot[object], casilla_list: CasillaList, entry: CasillaListEntry) -> Screen[object]:
    """Press Enter on one box, as a filer opens its panel, and return what is on top afterwards."""
    if casilla_list.focus_address(entry.key):
        casilla_list.focus()
        await pilot.press("enter")
        await _settle(pilot)
    return pilot.app.screen


async def _close_panel(pilot: Pilot[object], screen: Screen[object]) -> None:
    """Close a panel Enter opened; Escape on the workbench itself would leave it, so it is never pressed there."""
    if not isinstance(screen, ModeloWorkbenchScreen):
        await pilot.press("escape")
        await _settle(pilot)


async def _open_read_only_panel(scenario: SequenceScenario, pilot: Pilot[object]) -> None:
    """Open the panel of the first box a filer cannot type into, which says why and where to change it."""

    async def read_only(
        _scenario: SequenceScenario, pilot: Pilot[object], casilla_list: CasillaList, entry: CasillaListEntry
    ) -> bool:
        screen = await _open_panel(pilot, casilla_list, entry)
        if isinstance(screen, CasillaEditorScreen) and screen.read_only:
            return True
        await _close_panel(pilot, screen)
        return False

    await _first_box(scenario, pilot, read_only, "opened a panel without an input")


async def _open_assumed_panel(scenario: SequenceScenario, pilot: Pilot[object]) -> None:
    """Open the panel of the first assumed box, where the filer confirms or replaces the value."""

    async def assumed(
        _scenario: SequenceScenario, pilot: Pilot[object], casilla_list: CasillaList, entry: CasillaListEntry
    ) -> bool:
        if entry.field.origin is not ModeloFormOrigin.DEFAULT_TO_CONFIRM:
            return False
        screen = await _open_panel(pilot, casilla_list, entry)
        if isinstance(screen, CasillaEditorScreen) and not screen.read_only:
            return True
        await _close_panel(pilot, screen)
        return False

    await _first_box(scenario, pilot, assumed, "holds an assumed value the filer can confirm")


async def _open_legend(scenario: SequenceScenario, pilot: Pilot[object]) -> None:
    """Press ``?`` twice: the first widens the help band, the second opens the legend of every mark."""
    await pilot.press("question_mark", "question_mark")
    await _settle(pilot)
    if not _workbench(scenario, pilot.app).has_class("-legend"):
        raise ScenarioError(f"{scenario.sequence_id}: pressing ? twice did not open the legend")


async def _search_a_box(scenario: SequenceScenario, pilot: Pilot[object]) -> None:
    """Press ``/`` and type the number of the first numbered box, as a filer looks one up."""
    workbench = _workbench(scenario, pilot.app)
    box = next(
        (
            item.field.box
            for item in workbench.query_one(CasillaList).items
            if isinstance(item, CasillaListEntry) and item.field.box
        ),
        None,
    )
    if box is None:
        raise ScenarioError(f"{scenario.sequence_id}: the workbench's first page shows no numbered box to search for")
    await pilot.press("slash")
    await _settle(pilot)
    await pilot.press(*box)
    await _settle(pilot)
    if not workbench.has_class("-searching") or not workbench.query_one(WorkbenchSearchPanel).hits:
        raise ScenarioError(f"{scenario.sequence_id}: searching for box {box} found nothing")


async def _ask_to_confirm_assumed(scenario: SequenceScenario, pilot: Pilot[object]) -> None:
    """Press ``b`` only where the workbench lists the assumed values; the list is a question, not a change."""
    workbench = _workbench(scenario, pilot.app)
    form = workbench.form
    if (
        form is None
        or workbench.recorded
        or not form.edit_admitted
        or not any(field.origin is ModeloFormOrigin.DEFAULT_TO_CONFIRM for field in form.fields())
    ):
        raise ScenarioError(f"{scenario.sequence_id}: the declaration holds no assumed value a filer could confirm")
    await pilot.press("b")
    await _settle(pilot)


async def _stage(
    scenario: SequenceScenario, pilot: Pilot[object], casilla_list: CasillaList, entry: CasillaListEntry
) -> bool:
    """Put a sample into one box's panel and keep it, or close the panel when the box or the value is refused."""
    field = entry.field
    sample = _TYPED_SAMPLES.get(field.data_type)
    if sample is None or field.editability not in TYPED_EDITABILITIES:
        return False
    editor = await _open_panel(pilot, casilla_list, entry)
    if not isinstance(editor, CasillaEditorScreen) or editor.read_only:
        await _close_panel(pilot, editor)
        return False
    editor.query_one("#editor-input", Input).value = sample
    await _settle(pilot)
    if editor.query_one("#editor-save", Button).disabled:
        await _close_panel(pilot, editor)
        return False
    await pilot.press("enter")
    await _settle(pilot)
    return bool(_workbench(scenario, pilot.app).staged_changes)


async def _ask_to_recalculate(scenario: SequenceScenario, pilot: Pilot[object]) -> None:
    """Press ``c`` only where the workbench asks first; anywhere else it would recalculate the shared sandbox."""
    form = _workbench(scenario, pilot.app).form
    if form is None or not form.edit_admitted or form.calculation_revision_id is None or form.operator_entries_known:
        raise ScenarioError(
            f"{scenario.sequence_id}: the declaration does not both admit changes and leave unknown which values "
            "the filer typed, so pressing c would not stop at the question"
        )
    await pilot.press("c")
    await _settle(pilot)


async def _open_issues(scenario: SequenceScenario, pilot: Pilot[object]) -> None:
    form = _workbench(scenario, pilot.app).form
    if form is None or form.verification is None:
        raise ScenarioError(f"{scenario.sequence_id}: the declaration has not been verified, so it lists no findings")
    await pilot.press("i")
    await _settle(pilot)


async def _stay(_scenario: SequenceScenario, _pilot: Pilot[object]) -> None:
    return None


_PAGE_SCREENS: Final[dict[str, type[object]]] = {
    "workbench": ModeloWorkbenchScreen,
    "sources": WorkbenchSourcesScreen,
    "legend": ModeloWorkbenchScreen,
    "search": ModeloWorkbenchScreen,
    "not-editable": CasillaEditorScreen,
    EDITOR_PAGE: CasillaEditorScreen,
    BULK_CONFIRM_PAGE: BulkConfirmScreen,
    REVIEW_PAGE: EditReviewScreen,
    RECALCULATE_PAGE: ConfirmScreen,
    ISSUES_PAGE: WorkbenchIssuesScreen,
}
"""Each page past Declarations, by the short name a scenario uses, to the screen the filer lands on."""
_PAGE_WALKS: Final[dict[str, _Walk]] = {
    "workbench": _stay,
    "sources": _open_sources,
    "legend": _open_legend,
    "search": _search_a_box,
    "not-editable": _open_read_only_panel,
    EDITOR_PAGE: _open_assumed_panel,
    BULK_CONFIRM_PAGE: _ask_to_confirm_assumed,
    REVIEW_PAGE: _open_review,
    RECALCULATE_PAGE: _ask_to_recalculate,
    ISSUES_PAGE: _open_issues,
}
"""What the filer does on the workbench to reach each page."""
_CHANGING_PAGES: Final[frozenset[str]] = frozenset({EDITOR_PAGE, BULK_CONFIRM_PAGE, REVIEW_PAGE, RECALCULATE_PAGE})
"""Pages that start a change, which a filed declaration does not offer."""
_ASSUMED_PAGES: Final[frozenset[str]] = frozenset({EDITOR_PAGE, BULK_CONFIRM_PAGE})
"""Pages about assumed values, which a calculation that assumes nothing does not offer."""


def scenario_pages(scenario: SequenceScenario) -> tuple[str, ...]:
    """The Declarations list, then the declaration's workbench and the views it opens.

    The findings list is a page only of a declaration its sequence verified.
    A filed declaration accepts no change, so it offers none of the pages that
    start one, and the pages about assumed values need a calculation that
    assumed some.
    """

    def offered(page: str) -> bool:
        if page == ISSUES_PAGE:
            return scenario.verified
        if scenario.filed and page in _CHANGING_PAGES:
            return False
        return scenario.assumes or page not in _ASSUMED_PAGES

    return (DECLARATIONS_PAGE, *(page for page in _PAGE_SCREENS if offered(page)))


def scenario_surface(sequence_id: str, page: str) -> str:
    """The surface name one scenario page is reviewed under."""
    return f"seq-{sequence_id}--{page}"


def page_interfaces(page: str) -> tuple[str, ...]:
    """The interface class a scenario page paints.

    The Declarations page claims nothing: its screen is already covered by the
    fixture surfaces.
    """
    factory = _PAGE_SCREENS.get(page)
    if not isinstance(factory, type):
        return ()
    return (f"{factory.__module__}.{factory.__qualname__}",)


def resolve_scenario(name: str) -> SequenceScenario:
    """Return the named scenario, or refuse listing the accepted set."""
    try:
        return SEQUENCE_SCENARIOS[name]
    except KeyError:
        accepted = ", ".join(sorted(SEQUENCE_SCENARIOS))
        raise ScenarioError(f"unknown sequence scenario {name!r}; accepted: {accepted}") from None


class ScenarioProvenance(BaseModel):
    """Which documented state a scenario's frames show, and whether it still is that state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sequence_id: str
    docs_page: str
    golden_sha256: str
    matches_golden: bool
    golden_problems: tuple[str, ...] = ()
    """The first divergences from the committed golden, when there are any."""


@dataclass(frozen=True)
class Shot:
    """One page at one size under one appearance."""

    page: str
    width: int
    height: int
    theme: str
    svg: Path


@dataclass(frozen=True)
class ScenarioFrame:
    """One captured page: the SVG on disk and the harness's own reading of it."""

    shot: Shot
    surface: str
    frame_text: str
    screen: str
    """Qualified name of the screen actually on top when the frame was read."""


def capture_scenario(
    scenario: SequenceScenario,
    shots: Sequence[Shot],
) -> tuple[ScenarioProvenance, tuple[ScenarioFrame, ...]]:
    """Run a scenario's sequence once and capture every requested shot over its outcome."""
    pages = scenario_pages(scenario)
    unknown = sorted({shot.page for shot in shots} - set(pages))
    if unknown:
        raise ScenarioError(f"unknown page(s) {', '.join(unknown)}; accepted: {', '.join(pages)}")
    discovered, problems = discover_sequences(sequence_id=scenario.sequence_id)
    if problems or len(discovered) != 1:
        raise ScenarioError(f"sequence {scenario.sequence_id!r} could not be read: {'; '.join(problems)}")
    item = discovered[0]
    golden = read_golden(item.page, item.sequence_id)
    golden_digest = sha256(golden_path(item.page, item.sequence_id).read_bytes()).hexdigest()

    with (
        TemporaryDirectory(prefix="cadrumo-tui-scenario-", ignore_cleanup_errors=True) as scratch,
        executed_sequence_sandbox(item.sequence, sandbox_root=Path(scratch)) as (sandbox, transcript),
    ):
        divergences = check_transcript(item.sequence, transcript, golden, page=item.page)
        provenance = ScenarioProvenance(
            sequence_id=item.sequence_id,
            docs_page=item.page,
            golden_sha256=golden_digest,
            matches_golden=not divergences,
            golden_problems=tuple(divergences[:_GOLDEN_PROBLEMS_KEPT]),
        )
        # The installed session enters this composition before it builds the
        # root; the CLI frames above compose their own per invocation.
        with profile_adapter_composition():
            frames = asyncio.run(_capture_all(scenario, sandbox, tuple(shots)))
    return provenance, frames


async def _capture_all(
    scenario: SequenceScenario,
    sandbox: SequenceSandbox,
    shots: tuple[Shot, ...],
) -> tuple[ScenarioFrame, ...]:
    provider = compose_authenticated_root_inputs_provider(
        profile_id=sandbox.profile_id,
        profile_label=SANDBOX_PROFILE_LABEL,
        login_choices=profile_login_choices(),
    )
    async with operation_services_scope() as runtime:
        root = compose_installed_workbench_root(provider(runtime))
        return tuple([await _capture(scenario, root, shot) for shot in shots])


async def _capture(
    scenario: SequenceScenario,
    root: InstalledWorkbenchRootCompositionV1,
    shot: Shot,
) -> ScenarioFrame:
    route = root.destination_catalogue.resolve(_DECLARATIONS_DESTINATION)
    if route.factory is None:
        raise ScenarioError(f"Declarations is not available over the {scenario.sequence_id!r} sandbox")
    started = time.perf_counter()
    app = ScreenHostApp(route.factory(TuiScreenContextV1(destination=_DECLARATIONS_DESTINATION)))
    surface = scenario_surface(scenario.sequence_id, shot.page)
    async with app.run_test(size=(shot.width, shot.height)) as pilot:
        app.theme = resolve_theme_name(TuiAppearance(shot.theme))
        await _settle(pilot)
        if shot.page != DECLARATIONS_PAGE:
            await _select(pilot, "#declarations-list", _declaration_key(scenario, app))
            _workbench(scenario, app)
            await _PAGE_WALKS[shot.page](scenario, pilot)
            _require_page(scenario, app, shot.page)
        frame = capture(
            app,
            index=0,
            surface=surface,
            width=shot.width,
            height=shot.height,
            theme=shot.theme,
            locale="auto",
            elapsed_ms=(time.perf_counter() - started) * 1000,
        )
        shot.svg.parent.mkdir(parents=True, exist_ok=True)
        app.save_screenshot(str(shot.svg))
        painted = type(app.screen)
        app.exit(None)
    return ScenarioFrame(
        shot=shot,
        surface=surface,
        frame_text=frame.render(),
        screen=f"{painted.__module__}.{painted.__qualname__}",
    )


def _declaration_key(scenario: SequenceScenario, app: App[object]) -> str:
    """The work unit whose pages this scenario shows, refusing an ambiguous outcome."""
    screen = app.screen
    if not isinstance(screen, DeclarationsWorkspaceScreen):
        raise ScenarioError(f"Declarations opened {type(screen).__qualname__}, not the declarations workspace")
    matches = [
        item
        for item in screen.controller.projection.declarations
        if str(item.modelo) == scenario.modelo and (scenario.period is None or str(item.period.code) == scenario.period)
    ]
    if len(matches) != 1:
        listed = ", ".join(
            f"{item.modelo} {item.filing_year} {item.period.code}" for item in screen.controller.projection.declarations
        )
        raise ScenarioError(
            f"sequence {scenario.sequence_id!r} left {len(matches)} declaration(s) of modelo {scenario.modelo}"
            f"{'' if scenario.period is None else f' for {scenario.period}'}; it holds: {listed or 'none'}"
        )
    return str(matches[0].work_unit_id)


def _require_page(scenario: SequenceScenario, app: App[object], page: str) -> None:
    """Refuse a capture whose walk did not land on the page it is named for."""
    if type(app.screen) is not _PAGE_SCREENS.get(page):
        raise ScenarioError(
            f"{scenario.sequence_id}: the walk to {page!r} ended on {type(app.screen).__qualname__}; "
            "the declaration did not open that page"
        )


async def _select(pilot: Pilot[object], selector: str, key: str) -> None:
    """Pick one row by key and press Enter, as an operator does."""
    table = cast("DataTable[str]", pilot.app.screen.query_one(selector, DataTable))
    table.move_cursor(row=table.get_row_index(key))
    table.focus()
    await pilot.press("enter")
    await _settle(pilot)


async def _settle(pilot: Pilot[object]) -> None:
    """Wait until no worker is running; a worker superseded by an exclusive successor is not a failure."""
    await pilot.pause()
    for _ in range(_SETTLE_ROUNDS):
        try:
            await cast("_WorkerCompletion", pilot.app.workers).wait_for_complete()
        except WorkerCancelled:
            continue
        break
    else:
        raise ScenarioError(f"workers were still being replaced after {_SETTLE_ROUNDS} rounds of waiting")
    await pilot.pause()


__all__ = [
    "BULK_CONFIRM_PAGE",
    "DECLARATIONS_PAGE",
    "EDITOR_PAGE",
    "ISSUES_PAGE",
    "RECALCULATE_PAGE",
    "REVIEW_PAGE",
    "SEQUENCE_SCENARIOS",
    "ScenarioError",
    "ScenarioFrame",
    "ScenarioProvenance",
    "SequenceScenario",
    "Shot",
    "capture_scenario",
    "page_interfaces",
    "resolve_scenario",
    "scenario_pages",
    "scenario_surface",
]
