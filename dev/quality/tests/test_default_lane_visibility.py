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
    declared_roots,
    default_lane_predicate,
    visibility_census,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _write(root: Path, name: str, marker_line: str, *, body: str = "def test_x() -> None:\n    assert True\n") -> None:
    (root / name).write_text(f"import pytest\n\n{marker_line}\n\n{body}", encoding="utf-8")


@pytest.fixture
def lane() -> tuple[str, frozenset[str]]:
    return default_lane_predicate(_REPO_ROOT / "pyproject.toml")


def test_the_screen_reads_a_real_population(lane: tuple[str, frozenset[str]]) -> None:
    """A scan reaching nothing would report a clean tree and an empty census alike."""
    required, excluded = lane
    roots = declared_roots(_REPO_ROOT)
    findings = visibility_census(roots, required=required, excluded=excluded)

    assert roots, "neither test root exists, so the census scanned nothing"
    assert len(findings) > 50, f"only {len(findings)} modules classified; the scan is not reaching the tree"


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


def test_a_module_level_mark_without_an_execution_marker_defers_to_its_tests(
    tmp_path: Path, lane: tuple[str, frozenset[str]]
) -> None:
    """A hexagonal-only `pytestmark` must not read as running nowhere.

    The screen asked about per-test decorators only when a module carried no
    module-level `pytestmark` at all. A module carrying one that names no
    EXECUTION marker fell straight through to the sharpest condition, so
    a module with hexagonal markers at module level and `unit` decorators on
    its tests was reported as running nowhere while those tests ran.

    Its sibling above is the discriminator: the same module-level line with
    UNDECORATED tests is still the sharpest condition, and must stay so.
    """
    required, excluded = lane
    _write(
        tmp_path,
        "test_decorated.py",
        "pytestmark = [pytest.mark.hex_core]",
        body="@pytest.mark.unit\ndef test_x() -> None:\n    assert True\n",
    )

    findings = visibility_census((tmp_path,), required=required, excluded=excluded)

    assert [item.kind for item in findings] == ["per_function_markers_only"]


def test_a_decorated_fixture_does_not_make_a_module_look_marker_bearing(
    tmp_path: Path, lane: tuple[str, frozenset[str]]
) -> None:
    """Only a decorated TEST defers the question; a decorated fixture does not.

    A fixture confers no marker on anything it serves, so counting any
    decorated function would report a module as marker-bearing when nothing
    it runs is -- moving it out of the sharpest channel for the wrong reason.
    """
    required, excluded = lane
    _write(
        tmp_path,
        "test_fixture_only.py",
        "pytestmark = [pytest.mark.hex_core]",
        body=(
            "@pytest.fixture\ndef thing() -> int:\n    return 1\n\ndef test_x(thing: int) -> None:\n    assert thing\n"
        ),
    )

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


def test_a_module_the_walk_listed_but_cannot_read_is_reported_not_dropped(
    tmp_path: Path, lane: tuple[str, frozenset[str]]
) -> None:
    """An unreadable module is a row, because silence here reads as full visibility."""
    required, excluded = lane
    _write(tmp_path, "test_seen.py", "pytestmark = [pytest.mark.unit, pytest.mark.hex_core]")
    # A directory named like a module: the walk lists it and the read refuses it,
    # which is the shape a file deleted between the walk and the read also takes.
    (tmp_path / "test_vanished.py").mkdir()
    findings = visibility_census((tmp_path,), required=required, excluded=excluded)
    assert [(item.module, item.kind) for item in findings] == [("test_vanished.py", "unread")]


def test_a_half_written_module_is_reported_not_dropped(tmp_path: Path, lane: tuple[str, frozenset[str]]) -> None:
    """A module that does not parse is the same condition: the screen could not decide."""
    required, excluded = lane
    (tmp_path / "test_half.py").write_text("def (:\n", encoding="utf-8")
    findings = visibility_census((tmp_path,), required=required, excluded=excluded)
    assert [(item.module, item.kind) for item in findings] == [("test_half.py", "unread")]


def test_a_declared_root_that_no_longer_exists_is_refused(tmp_path: Path) -> None:
    """A vanished root must stop the census, not quietly shrink it.

    This is the condition that already occurred: the roster named a
    top-level ``tests`` tree, that tree moved, and the ``is_dir()`` filter
    dropped it without a word. The surviving root still cleared the
    population floor, so nothing in the suite could see the loss.
    """
    with pytest.raises(FileNotFoundError, match="never reached"):
        declared_roots(tmp_path)


def test_every_declared_root_resolves_against_this_repository() -> None:
    """The other direction: the live roster must still describe the tree."""
    resolved = declared_roots(_REPO_ROOT)

    assert resolved, "the roster declares no test root at all"
    assert all(path.is_dir() for path in resolved)
