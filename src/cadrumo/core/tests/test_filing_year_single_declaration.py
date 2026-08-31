"""The filing-year axis carries one window, declared in one place.

A filing year addresses a registry revision, so the value decides which year's
norms a calculation runs under. It was bounded per site, and the bounds did not
agree: the same ``filing_year`` field carried ``ge=2000, le=2099`` at most
sites, ``le=2100`` at others, and ``ge=1980, le=2200`` in the period model, so
:mod:`core.period` accepted a year the aggregation observation repositories
refused. Nothing detected the divergence, because each site was locally
consistent and no test compared them.

This gate refuses a year window spelled out on a field that names the
filing-year axis. Such a field must carry :obj:`FilingYear`, which declares the
window once; a site that spells ``ge=`` or ``le=`` in its own annotation is
declaring a second window, whether or not today's numbers happen to match.

Fields on OTHER year axes are deliberately outside the name set. A perceptor's
birth year, a devengo accrual year and a catastral revision year legitimately
reach back to 1900, and a manual review year runs to 2100; those are different
quantities that happen to be years, and sweeping them onto the filing-year
window would refuse values they must accept. The bare name ``year`` is
excluded for the same reason -- it is used for both axes.
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
EXEMPT_SITES: dict[str, str] = {
    "core/period.py:381": (
        "a period is a calendar span, not a claim that a revision exists for "
        "it; it must express a pre-1995 IVA regime year and a 1999 coordinate "
        "whose refusal is the behaviour under test, so the filing-year window "
        "would make those unrepresentable rather than refusable"
    ),
}


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


def _restated_windows() -> dict[str, str]:
    findings: dict[str, str] = {}
    for path in _production_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # a peer's mid-edit file is not this gate's finding
            continue
        relative = path.relative_to(_SRC).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if node.target.id not in FILING_YEAR_FIELD_NAMES:
                continue
            spelled = _spelled_bounds(node.annotation) | _spelled_bounds(node.value)
            if spelled:
                site = f"{relative}:{node.lineno}"
                findings[site] = f"{node.target.id} spells {sorted(spelled)}"
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
        if "FILING_YEAR_MIN: Final[int]" in path.read_text(encoding="utf-8")
    ]
    assert declaring == ["core/filing_year.py"], f"the filing-year window must be declared once, found: {declaring}"


def test_exempt_sites_still_exist_and_state_a_reason() -> None:
    """An exemption that stopped applying must be removed, not left standing."""
    restated = _restated_windows()
    stale = sorted(site for site in EXEMPT_SITES if site not in restated)
    assert not stale, f"these filing-year exemptions no longer apply: {stale}"
    unreasoned = sorted(site for site, reason in EXEMPT_SITES.items() if len(reason.strip()) < 20)
    assert not unreasoned, f"these filing-year exemptions state no reason: {unreasoned}"
