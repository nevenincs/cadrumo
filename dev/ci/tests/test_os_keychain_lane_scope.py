"""Every ``os_keychain`` case must lie under a path the os-keychain lane names.

Every other lane EXCLUDES ``os_keychain``, so `just test-os-keychain` is the
only selector for these cases. That recipe scopes itself by PATH, which makes
lane membership a property of where a file sits rather than of how it is
marked -- and a marked case outside those paths is selected by nothing at all.

This is not hypothetical. The recipe once named
``test_profile_session_root_resume.py`` alone, and three ``os_keychain``
custody cases in two sibling files were therefore run by no lane, among them
the cross-process "custody survives logout and reopens on login" contract the
lane exists for. Widening it to directories fixed those three; it did not make
the scoping property self-enforcing, which is what this gate adds.

The gap this guards is one directory wide. The lane names
``entrypoints/cli/tests`` but not ``entrypoints/cli/_config/tests``, and both
hold custody-adjacent CLI cases, so a marked case added to the second is
invisible to every lane while looking exactly like covered work.

A note on what "selected by no lane" costs. These cases cannot PASS on a
headless or network logon -- the credential store holds no credentials there,
and they refuse at an explicit precondition. So an orphaned case is not
noticed by anyone's red build; it simply never runs, and its absence reads
identically to coverage.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MARKER: Final = "os_keychain"
_PACKAGE_ROOT: Final = REPO_ROOT / "src" / "cadrumo"


def _lane_paths() -> tuple[Path, ...]:
    """Return the path arguments the os-keychain recipe selects."""
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    selecting = [
        line
        for line in justfile.splitlines()
        if f"-m {_MARKER}" in line and "pytest" in line and not line.lstrip().startswith("#")
    ]
    assert selecting, "no recipe selects the os_keychain marker; this gate would measure nothing"
    assert len(selecting) == 1, f"expected exactly one os_keychain selector, found {len(selecting)}"
    tokens = [token for token in selecting[0].split() if token.startswith("src/")]
    assert tokens, f"the os_keychain selector names no paths: {selecting[0].strip()}"
    return tuple(REPO_ROOT / token for token in tokens)


def _marked_files() -> tuple[Path, ...]:
    """Return every package test module that applies the marker.

    Resolved through the AST rather than a text search: a module discussing
    ``os_keychain`` in prose is not marked by it, and a gate that cannot tell
    those apart reds on documentation.
    """
    marked: list[Path] = []
    for path in _PACKAGE_ROOT.rglob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == _MARKER:
                marked.append(path)
                break
    return tuple(marked)


def _orphans(marked: tuple[Path, ...], lane_paths: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return marked files no declared lane path contains."""
    return tuple(path for path in marked if not any(path == lane or lane in path.parents for lane in lane_paths))


def test_every_os_keychain_case_lies_inside_the_lane_scope() -> None:
    """DISCRIMINATING: a marked case outside the declared paths runs nowhere."""
    marked = _marked_files()

    assert marked, "no os_keychain cases found; the scan is not reaching the package"

    orphaned = _orphans(marked, _lane_paths())

    assert not orphaned, (
        "these os_keychain cases are selected by NO lane -- every other lane excludes the "
        "marker and the os-keychain recipe does not name a path containing them; add their "
        "directory to the `test-os-keychain` recipe: "
        + ", ".join(str(path.relative_to(REPO_ROOT)) for path in sorted(orphaned))
    )


def test_a_narrowed_lane_scope_is_reported() -> None:
    """ANTI-TAUTOLOGY: the check must be able to say "orphaned".

    The assertion above is an emptiness claim, which a scan that found nothing
    satisfies just as well as a correctly-scoped lane. This replays the real
    historical narrowing -- the recipe naming one module -- and requires the
    orphans to be named.
    """
    marked = _marked_files()
    narrowed = (_PACKAGE_ROOT / "entrypoints" / "cli" / "tests" / "test_profile_session_root_resume.py",)

    orphaned = _orphans(marked, narrowed)

    assert len(orphaned) >= len(marked) - 1
    assert all(path not in narrowed for path in orphaned)


def test_the_lane_scope_is_read_from_the_recipe_not_hardcoded() -> None:
    """The declared paths must come from the justfile, and must be real directories.

    A stale path silently shrinks the lane: pytest is given a target that
    matches nothing, collects nothing from it, and exits green.
    """
    lane_paths = _lane_paths()

    assert lane_paths
    for lane in lane_paths:
        assert lane.exists(), f"the os-keychain recipe names a path that does not exist: {lane}"
