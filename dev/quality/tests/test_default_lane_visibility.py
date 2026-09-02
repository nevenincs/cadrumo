"""Real-behaviour tests for the default-lane visibility screen.

The condition this screen exists to catch does not occur in the corpus, which
is the good outcome and also the reason it must be constructed. A screen that
has never emitted its sharpest finding has not been shown able to.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..default_lane_visibility import (
    _REPO_ROOT,
    default_lane_predicate,
    visibility_census,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(root: Path, name: str, marker_line: str, *, body: str = "def test_x() -> None:\n    assert True\n") -> None:
    (root / name).write_text(f"import pytest\n\n{marker_line}\n\n{body}", encoding="utf-8")


@pytest.fixture
def lane() -> tuple[str, frozenset[str]]:
    return default_lane_predicate(_REPO_ROOT / "pyproject.toml")


def test_the_lane_predicate_is_read_from_the_project_configuration(lane: tuple[str, frozenset[str]]) -> None:
    """The screen describes the lane that actually runs, not a copy of it."""
    required, excluded = lane
    assert required == "unit"
    assert {"external_tool", "os_keychain"} <= excluded


def test_a_module_carrying_no_execution_marker_is_caught(tmp_path: Path, lane: tuple[str, frozenset[str]]) -> None:
    """The sharpest condition: a module no lane selects, so its tests run nowhere.

    Constructed, because the corpus contains none. Without this the screen's
    most important row would be unproven.
    """
    required, excluded = lane
    _write(tmp_path, "test_orphan.py", "pytestmark = [pytest.mark.hex_core]")
    findings = visibility_census((tmp_path,), required=required, excluded=excluded)
    assert [item.kind for item in findings] == ["no_execution_marker"]


def test_a_module_in_another_execution_lane_is_not_called_invisible(
    tmp_path: Path, lane: tuple[str, frozenset[str]]
) -> None:
    """An integration module runs, in its own lane, and must not be reported as unrun.

    This distinction was wrong in the screen's first version, which reported 99
    modules as carrying no execution marker when every one of them carried
    ``integration``.
    """
    required, excluded = lane
    _write(tmp_path, "test_integration.py", "pytestmark = [pytest.mark.integration, pytest.mark.hex_core]")
    findings = visibility_census((tmp_path,), required=required, excluded=excluded)
    assert [item.kind for item in findings] == ["other_execution_lane"]
    assert findings[0].markers == ("integration",)


def test_a_module_held_out_by_an_excluded_marker_is_named_with_that_marker(
    tmp_path: Path, lane: tuple[str, frozenset[str]]
) -> None:
    """The condition that hid 24 tests behind a passing exit code."""
    required, excluded = lane
    _write(tmp_path, "test_heavy.py", "pytestmark = [pytest.mark.unit, pytest.mark.external_tool]")
    findings = visibility_census((tmp_path,), required=required, excluded=excluded)
    assert [item.kind for item in findings] == ["held_out_by_marker"]
    assert findings[0].markers == ("external_tool",)


def test_a_default_lane_module_yields_no_row(tmp_path: Path, lane: tuple[str, frozenset[str]]) -> None:
    """A module the default lane selects is not reported, so the census cannot inflate."""
    required, excluded = lane
    _write(tmp_path, "test_plain.py", "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]")
    assert visibility_census((tmp_path,), required=required, excluded=excluded) == ()


def test_a_file_with_no_test_functions_is_not_reported(tmp_path: Path, lane: tuple[str, frozenset[str]]) -> None:
    """A helper module named like a test carries no tests and owes no marker."""
    required, excluded = lane
    (tmp_path / "test_support.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert visibility_census((tmp_path,), required=required, excluded=excluded) == ()
