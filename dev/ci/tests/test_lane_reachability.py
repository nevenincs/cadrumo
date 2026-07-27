"""Hard gate: no test file may sit outside every declared pytest lane.

An unreachable test is worse than a missing one. It reports nothing while
looking like coverage, so its rot is invisible until somebody happens to read
it. That state is not hypothetical here: the fourteen channel-generator tests
sat in it long enough for two independent breakages to accumulate, and the
author of the second had no signal at all.

No stored baseline and no allowlist. The worklist is recomputed from the tree on
every run, so coverage can only ratchet up: a new test directory outside every
lane fails immediately rather than being absorbed into an accepted set that
nobody revisits.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev.ci.lane_reachability import (
    Lane,
    declared_lanes,
    discover_test_files,
    expression_selects,
    markers_in,
    unreachable_test_files,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT: Path = Path(__file__).resolve().parents[3]


def test_every_test_file_is_selected_by_some_declared_lane() -> None:
    """The gate itself. Hard-cut: no baseline, no allowlist, no exceptions."""
    unreachable = unreachable_test_files(_ROOT)
    assert unreachable == (), (
        "these test files are selected by no declared lane, so nothing runs them:\n  " + "\n  ".join(unreachable)
    )


def test_the_repository_declares_lanes_at_all() -> None:
    """A parser that found nothing would report perfect coverage.

    This is the gate's own failure mode: zero lanes means every file is
    unreachable, but zero *files* would make the gate pass vacuously. Both sides
    are pinned so a broken parser cannot read as a clean tree.
    """
    lanes = declared_lanes(_ROOT)
    assert len(lanes) > 10, "lane discovery collapsed; the gate would be measuring nothing"
    assert len(discover_test_files(_ROOT)) > 100, "test discovery collapsed; the gate would pass vacuously"


def test_marker_and_path_are_both_required() -> None:
    """Reachability needs both halves, which is why the real hole survived.

    The generator tests were excluded twice over: lanes reaching their path
    rejected their marker, and lanes accepting their marker did not reach their
    path. A model checking only one half calls them reachable.
    """
    right_path_wrong_marker = Lane(source="t", paths=("packaging/homebrew/tests",), marker_expression="unit")
    right_marker_wrong_path = Lane(source="t", paths=("dev/ci/tests",), marker_expression="serial")
    target = "packaging/homebrew/tests/test_homebrew_generate.py"
    markers = frozenset({"integration", "serial"})

    assert right_path_wrong_marker.covers(target)
    assert not expression_selects(right_path_wrong_marker.marker_expression, markers)
    assert expression_selects(right_marker_wrong_path.marker_expression, markers)
    assert not right_marker_wrong_path.covers(target)


@pytest.mark.parametrize(
    ("expression", "markers", "selected"),
    [
        pytest.param("unit or (integration and not serial)", {"integration", "serial"}, False, id="serial-excluded"),
        pytest.param("unit or (integration and not serial)", {"integration"}, True, id="integration-included"),
        pytest.param("unit or (integration and not serial)", {"unit"}, True, id="unit-included"),
        pytest.param("serial", {"integration", "serial"}, True, id="serial-selected"),
        pytest.param("docs", {"unit", "hex_core"}, False, id="docs-lane-rejects-unit"),
        pytest.param("not integration", {"unit"}, True, id="negation"),
        pytest.param(None, {"anything"}, True, id="no-expression-selects-all"),
        pytest.param("((((", {"unit"}, False, id="unparseable-is-not-selection"),
    ],
)
def test_expression_evaluation_is_structural_not_substring(
    expression: str | None,
    markers: set[str],
    selected: bool,
) -> None:
    """``and``/``or``/``not`` and precedence decide, not string containment.

    ``unit or (integration and not serial)`` contains the substring "serial"
    while rejecting serial-marked files, so a containment check would invert the
    answer on the exact case this gate exists to catch.
    """
    assert expression_selects(expression, frozenset(markers)) is selected


def test_markers_are_collected_from_decorators_as_well_as_pytestmark(tmp_path: Path) -> None:
    """A file with only per-test decorators is not an unmarked file."""
    module = tmp_path / "test_decorated.py"
    module.write_text(
        "import pytest\n\n\n@pytest.mark.integration\ndef test_thing() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    assert "integration" in markers_in(module)


def test_a_planted_orphan_reds_the_gate(tmp_path: Path) -> None:
    """Anti-tautology, against an injectable root rather than the real tree.

    Without this the gate could pass because its discovery is broken rather than
    because the tree is clean, and those two outcomes look identical.
    """
    (tmp_path / "pyproject.toml").write_text('testpaths = ["src"]\n', encoding="utf-8")
    (tmp_path / "justfile").write_text("check:\n    pytest -q src -m unit\n", encoding="utf-8")

    covered = tmp_path / "src" / "tests"
    covered.mkdir(parents=True)
    (covered / "test_covered.py").write_text(
        "import pytest\n\npytestmark = [pytest.mark.unit]\n",
        encoding="utf-8",
    )
    assert unreachable_test_files(tmp_path) == ()

    orphan = tmp_path / "outside" / "tests"
    orphan.mkdir(parents=True)
    (orphan / "test_orphan.py").write_text(
        "import pytest\n\npytestmark = [pytest.mark.unit]\n",
        encoding="utf-8",
    )
    assert unreachable_test_files(tmp_path) == ("outside/tests/test_orphan.py",)


def test_a_marker_only_exclusion_also_reds_the_gate(tmp_path: Path) -> None:
    """The half a path-only model would miss, proven separately."""
    (tmp_path / "pyproject.toml").write_text('testpaths = ["src"]\n', encoding="utf-8")
    (tmp_path / "justfile").write_text("check:\n    pytest -q src -m unit\n", encoding="utf-8")

    covered = tmp_path / "src" / "tests"
    covered.mkdir(parents=True)
    # In the lane's path, but carrying a marker the lane's expression rejects.
    (covered / "test_serial_only.py").write_text(
        "import pytest\n\npytestmark = [pytest.mark.integration, pytest.mark.serial]\n",
        encoding="utf-8",
    )
    assert unreachable_test_files(tmp_path) == ("src/tests/test_serial_only.py",)
