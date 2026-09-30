"""Sequence scenarios render the Modelo pages over the declaration a documentation sequence built.

The table is checked against the documentation engine that owns the
sequences, and the capture is exercised end to end: the real sequence, the
real golden check, the installed workbench composed over the sandbox, and the
operator's walk to each page.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.entrypoints.tui.components.dialogs import ConfirmScreen
from cadrumo.entrypoints.tui.modelo.workbench.issues import WorkbenchIssuesScreen
from cadrumo.entrypoints.tui.modelo.workbench.review import EditReviewScreen
from cadrumo.entrypoints.tui.modelo.workbench.screen import ModeloWorkbenchScreen
from cadrumo.entrypoints.tui.modelo.workbench.sources import WorkbenchSourcesScreen
from dev.docs.sequences.checks import discover_sequences
from dev.docs.sequences.golden_store import golden_path, read_golden

from ... import _harness, _viewports
from ..._artifacts import ThemeName
from ..sequences import (
    DECLARATIONS_PAGE,
    ISSUES_PAGE,
    RECALCULATE_PAGE,
    REVIEW_PAGE,
    SEQUENCE_SCENARIOS,
    ScenarioError,
    SequenceScenario,
    Shot,
    capture_scenario,
    scenario_pages,
)

_FIRST_QUARTER = SEQUENCE_SCENARIOS["modelo-303-first-quarter"]
_INSTALMENT = SEQUENCE_SCENARIOS["modelo-130-first-quarter"]
_UNVERIFIED = SEQUENCE_SCENARIOS["verification-reports-incomplete"]
_FIRST_QUARTER_PAGES = ("workbench", "sources", "not-editable", ISSUES_PAGE)
_INSTALMENT_PAGES = ("workbench", "sources", "not-editable", REVIEW_PAGE, RECALCULATE_PAGE, ISSUES_PAGE)


def _qualname(screen: object) -> str:
    assert isinstance(screen, type)
    return f"{screen.__module__}.{screen.__qualname__}"


@pytest.mark.unit
@pytest.mark.hex_core
@pytest.mark.parametrize("scenario", SEQUENCE_SCENARIOS.values(), ids=lambda scenario: scenario.sequence_id)
def test_every_scenario_names_a_documented_sequence_that_works_its_modelo(scenario: SequenceScenario) -> None:
    discovered, problems = discover_sequences(sequence_id=scenario.sequence_id)

    assert not problems
    (item,) = discovered
    assert golden_path(item.page, item.sequence_id).is_file()
    golden = read_golden(item.page, item.sequence_id)
    worked = {
        frame.argv[frame.argv.index("--modelo") + 1]
        for frame in golden.frames
        if "--modelo" in frame.argv and frame.argv.index("--modelo") + 1 < len(frame.argv)
    }
    assert scenario.modelo in worked, f"{scenario.sequence_id} works modelo(s) {sorted(worked)}"


@pytest.mark.unit
@pytest.mark.hex_core
def test_a_page_no_route_builds_is_refused_before_any_sequence_runs(tmp_path: Path) -> None:
    with pytest.raises(ScenarioError, match="unknown page"):
        capture_scenario(_FIRST_QUARTER, (Shot("ledger", 80, 24, "dark", tmp_path / "ledger.svg"),))

    assert not any(tmp_path.iterdir())


@pytest.mark.unit
@pytest.mark.hex_core
def test_a_scenario_offers_only_the_pages_its_declaration_can_reach() -> None:
    assert scenario_pages(_INSTALMENT) == (DECLARATIONS_PAGE, *_INSTALMENT_PAGES)
    assert scenario_pages(_FIRST_QUARTER) == (DECLARATIONS_PAGE, *_FIRST_QUARTER_PAGES)
    assert ISSUES_PAGE not in scenario_pages(_UNVERIFIED)
    assert REVIEW_PAGE in scenario_pages(_UNVERIFIED)


@pytest.mark.unit
@pytest.mark.hex_core
@pytest.mark.parametrize(
    ("scenario", "page"),
    [(_UNVERIFIED, ISSUES_PAGE), (_FIRST_QUARTER, REVIEW_PAGE), (_FIRST_QUARTER, RECALCULATE_PAGE)],
    ids=["unverified-issues", "filed-review", "filed-recalculate"],
)
def test_a_page_the_scenario_does_not_offer_is_refused_before_its_sequence_runs(
    scenario: SequenceScenario, page: str, tmp_path: Path
) -> None:
    with pytest.raises(ScenarioError, match="unknown page"):
        capture_scenario(scenario, (Shot(page, 80, 24, "dark", tmp_path / f"{page}.svg"),))

    assert not any(tmp_path.iterdir())


@pytest.mark.integration
@pytest.mark.hex_core
def test_a_scenario_walks_to_every_page_over_the_declaration_its_sequence_built(tmp_path: Path) -> None:
    viewport = _viewports.resolve("small")

    provenance, captures = _harness.capture_scenario(
        _FIRST_QUARTER.sequence_id,
        (viewport,),
        themes=(ThemeName.DARK,),
        out_dir=tmp_path,
    )

    assert provenance.sequence_id == _FIRST_QUARTER.sequence_id
    assert provenance.matches_golden, provenance.golden_problems
    assert [item.page for item in captures] == list(scenario_pages(_FIRST_QUARTER))
    for item in captures:
        assert item.capture.svg_path.stat().st_size > 0
        assert item.capture.viewport == viewport
    workbench_pages = [item for item in captures if item.page != DECLARATIONS_PAGE]
    assert tuple(item.page for item in workbench_pages) == _FIRST_QUARTER_PAGES
    for item in workbench_pages[:2]:
        assert "303" in item.capture.frame_text, item.page


def _surface_text(frame_text: str) -> str:
    """The painted surface without the header line, which carries the capture's own timing."""
    return frame_text.split("\n", 1)[1].split("── focus:")[0]


@pytest.mark.integration
@pytest.mark.hex_core
def test_every_walk_lands_on_its_screen_and_none_changes_the_declaration(tmp_path: Path) -> None:
    """Every capture shares one sandbox, so a walk that saved anything would show on the workbench read after it."""
    shots = [
        Shot(page, 120, 40, "dark", tmp_path / f"{index}-{page}.svg")
        for index, page in enumerate((*_INSTALMENT_PAGES, "workbench"))
    ]

    _, frames = capture_scenario(_INSTALMENT, shots)

    painted = {frame.shot.page: frame.screen for frame in frames}
    assert painted == {
        "workbench": _qualname(ModeloWorkbenchScreen),
        "sources": _qualname(WorkbenchSourcesScreen),
        "not-editable": _qualname(ModeloWorkbenchScreen),
        REVIEW_PAGE: _qualname(EditReviewScreen),
        RECALCULATE_PAGE: _qualname(ConfirmScreen),
        ISSUES_PAGE: _qualname(WorkbenchIssuesScreen),
    }
    first, refused, last = (_surface_text(frames[index].frame_text) for index in (0, 2, -1))
    assert first == last
    assert refused != first, "the refused edit left the workbench saying nothing"


@pytest.mark.integration
@pytest.mark.hex_core
def test_a_scenario_whose_sequence_leaves_no_such_declaration_is_refused(tmp_path: Path) -> None:
    mismatched = SequenceScenario(_FIRST_QUARTER.sequence_id, "130", "a modelo this sequence never works")

    with pytest.raises(ScenarioError, match=r"0 declaration\(s\) of modelo 130.*303 2026 1T"):
        capture_scenario(mismatched, (Shot("workbench", 80, 24, "dark", tmp_path / "workbench.svg"),))

    assert not (tmp_path / "overview.svg").exists()


_DIGEST = re.compile(r"\b[0-9a-f]{64}\b")
_GEOMETRIES = ((80, 24), (120, 36), (160, 48))


@pytest.mark.integration
@pytest.mark.hex_core
def test_the_workbench_reads_cleanly_at_every_geometry_and_theme_through_the_production_root(tmp_path: Path) -> None:
    """Through the installed root over a documented declaration, every size and theme lands, fits and leaks nothing."""
    shots = [
        Shot(page, width, height, theme, tmp_path / f"{page}-{width}x{height}-{theme}.svg")
        for page in ("workbench", "sources")
        for width, height in _GEOMETRIES
        for theme in ("light", "dark")
    ]

    _, frames = capture_scenario(_FIRST_QUARTER, shots)

    expected = {"workbench": _qualname(ModeloWorkbenchScreen), "sources": _qualname(WorkbenchSourcesScreen)}
    assert len(frames) == len(shots)
    for frame in frames:
        label = f"{frame.shot.page} {frame.shot.width}x{frame.shot.height} {frame.shot.theme}"
        surface = frame.frame_text.split("── focus:")[0]
        assert frame.screen == expected[frame.shot.page], label
        assert "painted past the side edges" not in frame.frame_text, label
        assert not _DIGEST.search(surface), label
        assert "303" in surface, label
