"""Years carry one written shape, declared once.

Which years exist is the registry's to say. A carrier checks only that a value
is written as a year, through :obj:`FourDigitYear` from :mod:`core.filing_year`.
A site spelling ``ge=`` or ``le=`` on a filing-year field restates that window
even when its bounds are names rather than numbers: the same axis once carried
four different windows at once, and nothing noticed because each site was
locally consistent. A year written as a number anywhere in the repository is
the year gate's (``just check-year-literals``) to refuse.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

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
