"""Years carry one written shape, and no production code names a year as a bound.

Which years exist is the registry's to say. A carrier checks only that a value
is written as a year, through :obj:`FourDigitYear` from :mod:`core.filing_year`.
A site spelling ``ge=`` or ``le=`` on a filing-year field restates that, and a
year literal used as a bound on a year-named value claims a coverage nothing
keeps true: the same axis once carried four different windows at once, and
nothing noticed because each site was locally consistent.

Machine capacities, codepoints and format epochs are numbers that only look like
years; the rule reads the name a number bounds, so they stay outside it.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from ..filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path(__file__).resolve().parent.parent.parent

#: Field names that address the filing-year axis. A field named here must carry
#: the canonical alias rather than spell its own window.
FILING_YEAR_FIELD_NAMES = frozenset(
    {
        "filing_year",
        "source_filing_year",
        "target_filing_year",
        "period_filing_year",
        "target_year",
        "generation_year",
        "rectified_year",
        "modelo_year",
        "profile_year",
        "tax_year",
        "as_of_year",
        "ejercicio",
        "año",
    }
)

_BOUND_KWARGS = frozenset({"ge", "le", "gt", "lt"})

#: Sites permitted to spell their own window on a filing-year-named field,
#: each with the reason the canonical alias does not fit.
EXEMPT_SITES: dict[str, str] = {}


def _spelled_bounds(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    found: set[str] = set()
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name not in {"Field", "conint", "StringConstraints"}:
            continue
        found.update(str(kw.arg) for kw in call.keywords if kw.arg in _BOUND_KWARGS)
    return found


def _production_modules() -> list[Path]:
    return [
        path
        for path in sorted(_SRC.rglob("*.py"))
        if "tests" not in path.relative_to(_SRC).parts and not path.name.startswith("test_")
    ]


def _annotated_names(tree: ast.AST, owner: str = "") -> list[tuple[str, ast.AnnAssign]]:
    """Return every annotated name with the dotted path of the classes enclosing it."""
    found: list[tuple[str, ast.AnnAssign]] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.append((owner, node))
        child_owner = f"{owner}{node.name}." if isinstance(node, ast.ClassDef) else owner
        found.extend(_annotated_names(node, child_owner))
    return found


def _restated_windows() -> dict[str, str]:
    findings: dict[str, str] = {}
    for path in _production_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # a peer's mid-edit file is not this gate's finding
            continue
        relative = path.relative_to(_SRC).as_posix()
        for owner, node in _annotated_names(tree):
            target = node.target
            if not isinstance(target, ast.Name):
                continue
            if target.id not in FILING_YEAR_FIELD_NAMES:
                continue
            spelled = _spelled_bounds(node.annotation) | _spelled_bounds(node.value)
            if spelled:
                # Keyed by owner and name, not line: a line key goes stale on
                # the next edit above it.
                site = f"{relative}::{owner}{target.id}"
                findings[site] = f"{target.id} spells {sorted(spelled)}"
    return findings


def test_no_filing_year_field_spells_its_own_window() -> None:
    """A filing-year field carries the canonical alias, never its own bounds."""
    restated = {site: detail for site, detail in _restated_windows().items() if site not in EXEMPT_SITES}
    assert not restated, (
        "these fields declare a second filing-year window; type them as "
        f"FilingYear from cadrumo.core.filing_year instead: {restated}"
    )


_YEAR_NAME = re.compile(r"(?:^|_)(?:year|years|ejercicio|anio)(?:_|$)", re.IGNORECASE)


def _is_year_value(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Constant)
        and type(node.value) is int
        and FOUR_DIGIT_YEAR_FIRST <= node.value <= FOUR_DIGIT_YEAR_LAST
    )


def _named(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call) and node.args:
        return _named(node.args[0])
    return ""


def _year_literal_bounds(source: str) -> list[str]:
    """Return each year literal that bounds a year-named value, in reading order."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            found.extend(
                f"{node.target.id}@{node.lineno}"
                for side in (node.annotation, node.value)
                if side is not None and _YEAR_NAME.search(node.target.id)
                for call in ast.walk(side)
                if isinstance(call, ast.Call)
                for keyword in call.keywords
                if keyword.arg in _BOUND_KWARGS and _is_year_value(keyword.value)
            )
            if node.value is not None and _YEAR_NAME.search(node.target.id) and _is_year_value(node.value):
                found.append(f"{node.target.id}@{node.lineno}")
        elif isinstance(node, ast.Assign) and _is_year_value(node.value):
            found.extend(
                f"{target.id}@{node.lineno}"
                for target in node.targets
                if isinstance(target, ast.Name) and _YEAR_NAME.search(target.id)
            )
        elif isinstance(node, ast.Compare):
            sides = (node.left, *node.comparators)
            if any(isinstance(side, ast.Constant) and side.value == FOUR_DIGIT_YEAR_LAST for side in sides) or (
                any(_is_year_value(side) for side in sides) and any(_YEAR_NAME.search(_named(side)) for side in sides)
            ):
                found.append(f"compare@{node.lineno}")
    return found


@pytest.mark.parametrize(
    "planted",
    (
        "filing_year: int = Field(ge=2000)",
        "class Row:\n    tax_year: Annotated[int, Field(le=2099)]",
        "MIN_YEAR = 2022",
        "if value < 1900 or value > 9999:" + chr(10) + "    raise ValueError",
        "LAST_YEAR: int = 2100",
        "if year < 2022:\n    raise ValueError",
        "if 2000 <= row.filing_year <= 2099:\n    pass",
    ),
)
def test_the_gate_catches_a_planted_year_literal(planted: str) -> None:
    assert _year_literal_bounds(planted)


@pytest.mark.parametrize(
    "innocent",
    (
        "filing_year: FilingYear",
        "_MAX_ROWS = 2000",
        "if len(rows) < 2048:\n    pass",
        "if year < support.floor:\n    pass",
        "_ARCHIVE_EPOCH = (1980, 1, 1)",
    ),
)
def test_the_gate_leaves_what_is_not_a_year_bound(innocent: str) -> None:
    assert not _year_literal_bounds(innocent)


def test_no_production_code_bounds_a_year_with_a_year_literal() -> None:
    findings = {
        path.relative_to(_SRC).as_posix(): bounds
        for path in _production_modules()
        if "/_data/" not in path.as_posix() and (bounds := _year_literal_bounds(path.read_text(encoding="utf-8")))
    }
    assert not findings, f"years belong to the registry; derive these from it: {findings}"


def test_the_canonical_window_is_declared_once() -> None:
    """The alias and its bounds live in exactly one module."""
    declaring = [
        path.relative_to(_SRC).as_posix()
        for path in _production_modules()
        if "FOUR_DIGIT_YEAR_FIRST: Final[int]" in path.read_text(encoding="utf-8")
    ]
    assert declaring == ["core/filing_year.py"], f"the filing-year window must be declared once, found: {declaring}"


def test_exempt_sites_still_exist_and_state_a_reason() -> None:
    """An exemption that stopped applying must be removed, not left standing."""
    restated = _restated_windows()
    stale = sorted(site for site in EXEMPT_SITES if site not in restated)
    assert not stale, f"these filing-year exemptions no longer apply: {stale}"
    unreasoned = sorted(site for site, reason in EXEMPT_SITES.items() if len(reason.strip()) < 20)
    assert not unreasoned, f"these filing-year exemptions state no reason: {unreasoned}"
