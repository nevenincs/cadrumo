"""The home-office family grouping is declared once, in this package.

Four modules had each restated the pair of home-office families -- two as tuples
and two as frozensets -- and two of them had also each written their own function
unioning the pair's members. A fifth restatement was added and removed in the same
session that wrote this test, which is what makes the point: the grouping is easy
to re-derive locally and nothing objected.

Restating it is not merely untidy. LIRPF art. 30.2.5.b applies the statutory thirty
per cent to SUMINISTROS only, while the OWNERSHIP costs deduct at the raw proportion
under art. 29.2. A copy that drifts by one member moves a category across that line
and changes what a taxpayer deducts, in whichever direction the drift happens to go.

This gate reads the source rather than the imported values, because a module that
imports the canonical name and one that rebuilds an identical set are indistinguishable
at runtime and only the second is the defect.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from .. import HOME_OFFICE_FAMILIES, SpendingCategoryFamily, home_office_categories

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The module allowed to name both families together: the canonical declaration.
_CANONICAL_MODULE = "_spending_category.py"

#: Package root of the shipped application source.
_SOURCE_ROOT = Path(__file__).resolve().parents[3]


def _family_attributes_referenced(tree: ast.AST) -> set[str]:
    """Return the home-office family members this module references AS CODE.

    Read through the AST rather than the raw text, so a docstring that explains
    the difference between the two families -- which several modules legitimately
    do, since the statutory multiplier applies to one and not the other -- is not
    mistaken for the grouping being rebuilt. Prose about a rule is not a copy of it.
    """
    return {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr.startswith("HOME_OFFICE_")
    } | {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id.startswith("HOME_OFFICE_") and node.id != "HOME_OFFICE_FAMILIES"
    }


def _modules_naming_both_families() -> list[Path]:
    """Return every module that references both home-office family members in code.

    Referencing one is ordinary -- a call site legitimately asks whether a category
    is a suministro. Naming BOTH is the grouping being rebuilt.
    """
    found: list[Path] = []
    for path in _SOURCE_ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        referenced = _family_attributes_referenced(ast.parse(path.read_text(encoding="utf-8")))
        if {"HOME_OFFICE_SUMINISTROS", "HOME_OFFICE_OWNERSHIP"} <= referenced:
            found.append(path)
    return found


def test_only_the_canonical_module_declares_the_grouping() -> None:
    """DISCRIMINATING. The defect this centralisation removed."""
    offenders = [
        path.relative_to(_SOURCE_ROOT).as_posix()
        for path in _modules_naming_both_families()
        if path.name != _CANONICAL_MODULE
    ]

    assert not offenders, (
        "these modules name both home-office families and so rebuild a grouping that "
        "already exists; import HOME_OFFICE_FAMILIES or home_office_categories from "
        f"domain.categories instead: {offenders}"
    )


def test_the_canonical_declaration_is_actually_there() -> None:
    """SUPPORTING. Without this the test above passes if the grouping is deleted."""
    canonical = [path for path in _modules_naming_both_families() if path.name == _CANONICAL_MODULE]

    assert canonical, "no module declares the home-office grouping at all"
    tree = ast.parse(canonical[0].read_text(encoding="utf-8"))
    assigned = {
        target.id
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign | ast.Assign)
        for target in ([node.target] if isinstance(node, ast.AnnAssign) else node.targets)
        if isinstance(target, ast.Name)
    }

    assert "HOME_OFFICE_FAMILIES" in assigned


def test_the_grouping_holds_exactly_the_two_dwelling_families() -> None:
    """DISCRIMINATING on content, not on a tally.

    Named rather than counted: a count of two would still pass if one member were
    swapped for an unrelated family, and the whole risk here is membership drift.
    """
    assert frozenset(
        {
            SpendingCategoryFamily.HOME_OFFICE_SUMINISTROS,
            SpendingCategoryFamily.HOME_OFFICE_OWNERSHIP,
        },
    ) == HOME_OFFICE_FAMILIES


def test_the_category_set_is_the_union_of_both_families_members() -> None:
    """SUPPORTING. The derived helper must stay derived, not become a second list."""
    from .._spending_category import categories_for_family

    expected = {category for family in HOME_OFFICE_FAMILIES for category in categories_for_family(family)}

    assert home_office_categories() == expected
    assert home_office_categories(), "the home-office families have no members at all"
