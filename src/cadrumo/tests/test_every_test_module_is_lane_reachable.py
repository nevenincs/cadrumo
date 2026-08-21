"""Every test module under ``src/`` is selected by some declared lane.

The package lanes name no paths: ``just test-unit`` and ``just test-integration``
run the whole tree and select by MARKER. That is a good design -- a new module is
covered the moment it lands -- but it has one hole. A module that carries only
architectural markers (``hex_application`` and friends) and no EXECUTION marker
is selected by no lane at all. It is not skipped and not reported; it simply
never runs, and a suite that never runs it is green forever.

``dev/`` already has this gate: ``dev/tests/test_lane_reachability.py`` proves
the union of the `dev/` recipes reaches every tracked ``dev/**/test_*.py``, and
the Justfile calls itself the sole declaration site so a lane is declared there
or nowhere. The same argument applies to ``src/``, where the check is simpler
because no lane names a path -- only marker selection can fail.

The execution markers below are the ones a lane actually selects on. They are
listed rather than derived because the Justfile's expressions are prose to this
test; if a lane's marker changes, this list is where the change is noticed, and
a module reachable by nothing fails here naming itself.
"""

from __future__ import annotations

import ast

import pytest

from ._inventory import SRC_CADRUMO, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Markers a declared lane selects on.
#:
#: ``unit`` and ``integration`` are the two default lanes; ``aeat_live`` is
#: enrolled by ``just test-live`` and is the reason the live-AEAT modules are
#: reachable despite carrying neither of the other two.
_EXECUTION_MARKERS = frozenset({"unit", "integration", "aeat_live"})

#: A module that would never run: architectural markers only.
_ORPHAN_SAMPLE = (
    "import pytest\n"
    "pytestmark = [pytest.mark.hex_application]\n"
    "def test_something():\n"
    "    assert True\n"
)

#: The same module with an execution marker, reachable by the unit lane.
_REACHABLE_SAMPLE = (
    "import pytest\n"
    "pytestmark = [pytest.mark.unit, pytest.mark.hex_application]\n"
    "def test_something():\n"
    "    assert True\n"
)


def _declared_markers(tree: ast.AST) -> set[str]:
    """Return every ``pytest.mark.<name>`` referenced anywhere in a module.

    Collected across the whole module rather than from ``pytestmark`` alone,
    because a marker applied per function is just as good for reachability --
    the lane selects tests, not modules.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not isinstance(node.value, ast.Attribute):
            continue
        if getattr(node.value.value, "id", None) == "pytest" and node.value.attr == "mark":
            found.add(node.attr)
    return found


def _test_modules() -> list:
    """Return every test module shipped under the package."""
    return [path for path in SRC_CADRUMO.rglob("test_*.py") if "tests" in path.parts]


def _unreachable(tree: ast.AST) -> bool:
    """Report whether a module carries no marker any lane selects."""
    return not (_declared_markers(tree) & _EXECUTION_MARKERS)


def test_no_test_module_is_reachable_by_no_lane() -> None:
    """DISCRIMINATING: a module no lane selects never runs and never reports."""
    orphans = [
        f"{repo_relative(path)}: markers={sorted(_declared_markers(ast.parse(path.read_text(encoding='utf-8'))))}"
        for path in _test_modules()
        if _unreachable(ast.parse(path.read_text(encoding="utf-8")))
    ]

    assert not orphans, (
        "these test modules carry no marker any lane selects, so nothing ever runs them:\n  "
        + "\n  ".join(sorted(orphans))
        + f"\nAdd one of {sorted(_EXECUTION_MARKERS)}, or declare a lane that enrols the marker "
        "they do carry."
    )


def test_the_scan_reaches_the_package_test_surface() -> None:
    """ANTI-VACUITY: an empty module list produces an empty orphan list.

    The gate's content is the emptiness of that list, and a scan that walked
    nothing would deliver it for free.
    """
    assert len(_test_modules()) > 2000


def test_the_detector_reports_an_unreachable_module() -> None:
    """ANTI-TAUTOLOGY: proven on source carrying the shape, no tracked file touched."""
    assert _unreachable(ast.parse(_ORPHAN_SAMPLE)) is True


def test_the_detector_accepts_a_lane_reachable_module() -> None:
    """The other direction: an execution marker must clear the module.

    A detector that flagged everything would fail the tree immediately, so this
    pins that carrying a lane marker is what makes a module reachable.
    """
    assert _unreachable(ast.parse(_REACHABLE_SAMPLE)) is False


def test_the_live_only_modules_are_reachable_through_their_own_lane() -> None:
    """The population that makes the third marker load-bearing.

    Seventeen modules carry neither ``unit`` nor ``integration`` and are
    reachable only because ``aeat_live`` has a lane of its own. Dropping that
    marker from the set above would fail the gate rather than silently narrow
    it, which is the point of listing the markers explicitly.
    """
    live_only = [
        path
        for path in _test_modules()
        if not ({"unit", "integration"} & _declared_markers(ast.parse(path.read_text(encoding="utf-8"))))
    ]

    assert live_only, "expected live-only modules; the marker set may have drifted"
    for path in live_only:
        markers = _declared_markers(ast.parse(path.read_text(encoding="utf-8")))
        assert "aeat_live" in markers, f"{repo_relative(path)} is reachable by no lane"
