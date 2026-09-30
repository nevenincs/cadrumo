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
workspace page picked from the overview's list.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final, Protocol, cast

from pydantic import BaseModel, ConfigDict
from textual.app import App
from textual.pilot import Pilot
from textual.widgets import DataTable

from cadrumo.application.user_profile.login_interaction import profile_login_choices
from cadrumo.core.config_support import TuiAppearance
from cadrumo.entrypoints.adapter_composition import profile_adapter_composition
from cadrumo.entrypoints.tui.components.host import ScreenHostApp
from cadrumo.entrypoints.tui.components.theme import resolve_theme_name
from cadrumo.entrypoints.tui.declarations.controller import DeclarationsWorkspaceScreen
from cadrumo.entrypoints.tui.installed_session import compose_authenticated_root_inputs_provider
from cadrumo.entrypoints.tui.launcher import (
    InstalledWorkbenchRootCompositionV1,
    compose_installed_workbench_root,
    operation_services_scope,
)
from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen
from cadrumo.entrypoints.tui.modelo.workbench.sources import WorkbenchSourcesScreen
from cadrumo.entrypoints.tui.navigation import TuiScreenContextV1
from cadrumo.entrypoints.tui.tests.frame import capture
from dev.docs.sequences.checks import discover_sequences
from dev.docs.sequences.compare import check_transcript
from dev.docs.sequences.golden_store import golden_path, read_golden
from dev.docs.sequences.runner import SANDBOX_PROFILE_LABEL, SequenceSandbox, executed_sequence_sandbox

DECLARATIONS_PAGE: Final[str] = "declarations"
_DECLARATIONS_DESTINATION: Final = "workbench.declarations"
_GOLDEN_PROBLEMS_KEPT: Final[int] = 5

_PAGE_SCREENS: Final[dict[str, type[object]]] = {
    "workbench": ModeloWorkbenchScreen,
    "sources": WorkbenchSourcesScreen,
}
"""Each page past Declarations, by the short name a scenario uses, to the screen the filer lands on."""
_PAGE_KEYS: Final[dict[str, tuple[str, ...]]] = {"workbench": (), "sources": ("s",)}
"""The keys a filer presses on the workbench to reach each page."""


@dataclass(frozen=True)
class SequenceScenario:
    """One documentation sequence, and the declaration whose pages it shows."""

    sequence_id: str
    modelo: str
    summary: str
    period: str | None = None
    """Names the declaration when the sequence leaves more than one of this modelo."""


SEQUENCE_SCENARIOS: Final[dict[str, SequenceScenario]] = {
    scenario.sequence_id: scenario
    for scenario in (
        SequenceScenario("modelo-303-first-quarter", "303", "Modelo 303, first quarter, verified and filed"),
        SequenceScenario("verification-reports-incomplete", "303", "Modelo 303 calculated but not complete"),
        SequenceScenario("modelo-130-first-quarter", "130", "Modelo 130, first quarter, verified"),
        SequenceScenario("modelo-100-renta-2025", "100", "Modelo 100, renta 2025, verified"),
        SequenceScenario("modelo-349-first-quarter", "349", "Modelo 349, first quarter, verified"),
        SequenceScenario("modelo-390-annual-2025", "390", "Modelo 390, annual summary 2025, verified"),
    )
}
"""Every scenario, by the sequence id it runs. The sequence is the definition;
this only chooses which declaration of its outcome to show."""


def scenario_pages() -> tuple[str, ...]:
    """The Declarations list, then the declaration's workbench and the views it opens."""
    return (DECLARATIONS_PAGE, *_PAGE_SCREENS)


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


class ScenarioError(RuntimeError):
    """A scenario that cannot produce the pages it names."""


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


class _WorkerCompletion(Protocol):
    async def wait_for_complete(self) -> None: ...


def capture_scenario(
    scenario: SequenceScenario,
    shots: Sequence[Shot],
) -> tuple[ScenarioProvenance, tuple[ScenarioFrame, ...]]:
    """Run a scenario's sequence once and capture every requested shot over its outcome."""
    unknown = sorted({shot.page for shot in shots} - set(scenario_pages()))
    if unknown:
        raise ScenarioError(f"unknown page(s) {', '.join(unknown)}; accepted: {', '.join(scenario_pages())}")
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
            keys = _PAGE_KEYS[shot.page]
            if keys:
                await pilot.press(*keys)
                await _settle(pilot)
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
    await pilot.pause()
    await cast("_WorkerCompletion", pilot.app.workers).wait_for_complete()
    await pilot.pause()


__all__ = [
    "DECLARATIONS_PAGE",
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
