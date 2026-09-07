"""Every external constant is applied by the product or adjudicated in the ledger.

``core/external_constants.py`` is the place a reader trusts for what the product
applies. Its entries carry a binding provision and a figure, and a legally
grounded figure sitting among enforced ones reads as enforced. The art. 108
escaso-valor threshold sat there unapplied: nothing compared a good against it,
because the bienes-de-inversión register takes eligibility as an operator
boolean and stores no acquisition value, and a reader had no way to learn that
short of grepping for callers.

So the rule is a disjunction, and both halves are honest outcomes. A constant is
either REFERENCED by shipped code -- the product applies it -- or it carries an
entry in the reachability ledger saying why it does not yet. What is refused is
the third state: a figure with neither, which asserts an enforcement nobody
performs and which no other gate sees, because the constant imports fine and
every test of the file passes.

Reference counting binds BOTH names an import can introduce. ``from x import
RATE as _RATE`` binds ``_RATE`` while referencing ``RATE``, and recording only
the bound name hides every aliased consumer -- a first draft of this scan
reported fourteen unapplied constants where there are eight, and six of the
false ones were aliased at their single call site.
"""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path
from typing import Final

import pytest

from ..._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CONSTANTS: Final[Path] = REPO_ROOT / "src" / "cadrumo" / "core" / "external_constants.py"
_LEDGER: Final[Path] = REPO_ROOT / "dev" / "audit" / "reachability_classification.toml"
_SOURCE_ROOT: Final[Path] = REPO_ROOT / "src" / "cadrumo"


def declared_constants(path: Path) -> list[str]:
    """Return every module-level upper-case constant the file declares."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id.isupper():
            names.append(node.target.id)
        elif isinstance(node, ast.Assign):
            names.extend(t.id for t in node.targets if isinstance(t, ast.Name) and t.id.isupper())
    return names


def referenced_names(root: Path, *, exclude: Path) -> set[str]:
    """Return every name shipped code mentions, counting both halves of an alias."""
    seen: set[str] = set()
    swept = sorted(root.rglob("*.py"))
    assert swept, (
        f"the sweep of {root} matched no module; a walk that reads nothing reports every "
        "external constant as unreferenced with exactly the confidence of a real finding"
    )
    for path in swept:
        if "tests" in path.parts or "__pycache__" in path.parts or path.name.startswith("test_"):
            continue
        if path == exclude:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.alias):
                seen.add(node.name.rsplit(".", 1)[-1])
                if node.asname:
                    seen.add(node.asname)
            elif isinstance(node, ast.Name):
                seen.add(node.id)
            elif isinstance(node, ast.Attribute):
                seen.add(node.attr)
    return seen


def adjudicated_symbols(ledger: Path) -> set[str]:
    """Return every symbol the reachability ledger carries a decision for."""
    data = tomllib.loads(ledger.read_text(encoding="utf-8"))
    return {str(s) for cluster in data.get("symbol_cluster", ()) for s in cluster.get("symbols", ())}


def unaccounted(constants: list[str], referenced: set[str], adjudicated: set[str]) -> list[str]:
    """Return constants that are neither applied nor adjudicated."""
    return sorted(name for name in constants if name not in referenced and name not in adjudicated)


def test_the_scan_reaches_the_constants_file() -> None:
    """A population floor: an empty parse would make the check vacuous."""
    assert len(declared_constants(_CONSTANTS)) >= 40


def test_every_constant_is_applied_or_adjudicated() -> None:
    """The direction the gate exists for."""
    broken = unaccounted(
        declared_constants(_CONSTANTS),
        referenced_names(_SOURCE_ROOT, exclude=_CONSTANTS),
        adjudicated_symbols(_LEDGER),
    )

    assert broken == [], (
        "these external constants are referenced by no shipped code and carry no ledger "
        "entry, so each asserts an enforcement nothing performs: " + ", ".join(broken)
    )


def test_an_unreferenced_unadjudicated_constant_is_reported() -> None:
    """Detector teeth: the shape the escaso-valor threshold carried."""
    assert unaccounted(["RATE"], set(), set()) == ["RATE"]


def test_a_referenced_constant_is_accepted() -> None:
    assert unaccounted(["RATE"], {"RATE"}, set()) == []


def test_a_constant_reached_only_under_an_alias_is_accepted() -> None:
    """``from x import RATE as _RATE`` applies RATE; the bound name is not the reference."""
    assert unaccounted(["RATE"], {"RATE", "_RATE"}, set()) == []


def test_an_adjudicated_constant_is_accepted() -> None:
    assert unaccounted(["RATE"], set(), {"RATE"}) == []
