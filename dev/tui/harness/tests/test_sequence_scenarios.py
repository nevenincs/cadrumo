"""Sequence scenarios render the Modelo pages over the declaration a documentation sequence built.

The table is checked against the documentation engine that owns the
sequences, and the capture is exercised end to end: the real sequence, the
real golden check, the installed workbench composed over the sandbox, and the
operator's walk to each page.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.entrypoints.tui.modelo.routes import MODELO_WORKSPACE_DESTINATIONS
from dev.docs.sequences.checks import discover_sequences
from dev.docs.sequences.golden_store import golden_path, read_golden

from ... import _harness, _viewports
from ..._artifacts import ThemeName
from ..sequences import (
    DECLARATIONS_PAGE,
    SEQUENCE_SCENARIOS,
    ScenarioError,
    SequenceScenario,
    Shot,
    capture_scenario,
    scenario_pages,
)

_FIRST_QUARTER = SEQUENCE_SCENARIOS["modelo-303-first-quarter"]


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
    assert [item.page for item in captures] == list(scenario_pages())
    for item in captures:
        assert item.capture.svg_path.stat().st_size > 0
        assert item.capture.viewport == viewport
    workspace_pages = [item for item in captures if item.page != DECLARATIONS_PAGE]
    assert len(workspace_pages) == len(MODELO_WORKSPACE_DESTINATIONS)
    for item in workspace_pages:
        assert "modelo 303" in item.capture.frame_text, item.page


@pytest.mark.integration
@pytest.mark.hex_core
def test_the_walk_lands_on_the_screen_each_route_builds(tmp_path: Path) -> None:
    shots = [
        Shot(page, 100, 30, "light", tmp_path / f"{page}.svg") for page in scenario_pages() if page != DECLARATIONS_PAGE
    ]

    _, frames = capture_scenario(_FIRST_QUARTER, shots)

    painted = {frame.shot.page: frame.screen for frame in frames}
    assert painted == {
        destination.removeprefix("modelo.workspace."): _qualname(screen)
        for destination, screen in MODELO_WORKSPACE_DESTINATIONS.items()
    }


@pytest.mark.integration
@pytest.mark.hex_core
def test_a_scenario_whose_sequence_leaves_no_such_declaration_is_refused(tmp_path: Path) -> None:
    mismatched = SequenceScenario(_FIRST_QUARTER.sequence_id, "130", "a modelo this sequence never works")

    with pytest.raises(ScenarioError, match=r"0 declaration\(s\) of modelo 130.*303 2026 1T"):
        capture_scenario(mismatched, (Shot("overview", 80, 24, "dark", tmp_path / "overview.svg"),))

    assert not (tmp_path / "overview.svg").exists()
