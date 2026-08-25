"""No shipped writer names a profile-fact path the schema does not declare.

A fact path absent from the schema was once written with nothing
complaining. The lifecycle service refuses one now - proven by probe
against the real store, and by the service's own ``unknown_field`` issue -
but that only binds a writer that goes through it, and the escape it was
found by was a literal path in source that no one had checked.

Enforcing the path on :class:`UserProfileFact` itself was the obvious
next move and is the wrong one: the value object has no schema in hand,
so it would have to reach for the bundled singleton, and that breaks
every test that injects a synthetic schema, wizard flow, or binding to
isolate what it is proving. Those tests are correct against the
definition they inject; only the bundled schema disagrees. So the
declared set is enforced here instead, over the source tree, where the
bundled schema genuinely is the authority and no injection is in play.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ..values import declared_field_paths, section_field_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _source_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _shipped_python_files() -> tuple[Path, ...]:
    root = _source_root()
    return tuple(path for path in scan_directory(root, pattern="*.py", recursive=True) if "tests" not in path.parts)


def _literal_fact_paths(tree: ast.Module) -> list[tuple[int, str]]:
    """Return every literal ``path=`` given to a ``UserProfileFact`` call."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "UserProfileFact":
            continue
        for keyword in node.keywords:
            if keyword.arg == "path" and isinstance(keyword.value, ast.Constant):
                literal = keyword.value.value
                if isinstance(literal, str):
                    found.append((node.lineno, literal))
    return found


def test_the_scan_finds_the_call_sites_it_claims_to_check() -> None:
    """A scan that matches nothing would pass while proving nothing.

    The gate below is a clean negative: it asserts an empty list. That is
    worthless unless the scan actually reaches ``UserProfileFact`` call
    sites, so this pins that it does, and that its parser agrees with the
    schema on a path everyone knows is declared.
    """

    files = _shipped_python_files()
    assert files, "the source scan found no shipped Python files"

    sites = [
        (path, lineno, literal)
        for path in files
        for lineno, literal in _literal_fact_paths(ast.parse(path.read_text(encoding="utf-8")))
    ]
    assert sites, "the scan found no literal UserProfileFact path arguments; the matcher has stopped matching"
    assert "identity.tax_id" in declared_field_paths()


def test_every_shipped_literal_fact_path_is_declared() -> None:
    """The gate the undeclared-path escape needed and did not have."""

    declared = declared_field_paths()
    violations = [
        f"{path.relative_to(_source_root())}:{lineno} path={literal!r}"
        for path in _shipped_python_files()
        for lineno, literal in _literal_fact_paths(ast.parse(path.read_text(encoding="utf-8")))
        if section_field_key(literal) not in declared
    ]

    assert not violations, (
        "shipped code writes profile-fact path(s) the schema does not declare:\n  "
        + "\n  ".join(violations)
        + "\nDeclare the field in the profile schema, or correct the path; do not widen the "
        "schema for a path that is simply wrong."
    )


def test_an_indexed_path_reduces_to_its_declared_field() -> None:
    """A repeatable section addresses rows by index.

    The schema declares such a field once rather than per row, so the
    reduction has to drop the index or the gate would flag every row of
    every repeatable section as undeclared.
    """

    assert section_field_key("activities.0.iae_epigraph") == "activities.iae_epigraph"
    assert section_field_key("identity.tax_id") == "identity.tax_id"


def test_an_undeclared_path_would_be_caught() -> None:
    """Anti-tautology proof for the gate above.

    The gate asserts an empty list, so it must be shown to be capable of
    a non-empty one: a synthetic module carrying an undeclared path has
    to be flagged by exactly the reduction and set the gate uses.
    """

    module = ast.parse('UserProfileFact(path="residency.municipality_code", value="28079")\n')
    found = _literal_fact_paths(module)

    assert [literal for _lineno, literal in found] == ["residency.municipality_code"]
    assert section_field_key("residency.municipality_code") not in declared_field_paths()
