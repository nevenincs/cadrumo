"""Declarative Modelo workspace fixed point over the canonical authority scanner.

The cohort's authorities are declared once each: the destination table, the
action dispatch table, and the action denominator. This gate asserts that each
is defined in exactly one module, reached by its canonical name everywhere, and
carries no alias, re-export, or retired twin.

Built on the SAME scanner the work-selection fixed point uses
(:func:`scan_canonical_authority`) rather than a second census. A parallel
scanner would be its own duplicate authority, in a gate whose whole subject is
duplicate authorities.

See Also:
    :mod:`dev.tests.test_modelo_work_selection_fixed_point`
        The sibling fixed point over the same scanner.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..quality.import_hygiene_scan import (
    CanonicalAuthoritySpec,
    CanonicalAuthorityTarget,
    scan_canonical_authority,
    tracked_live_files,
)
from ..quality.modelo_workspace_action_denominator import validate_modelo_workspace_action_denominator

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_ROOT = Path(__file__).resolve().parents[2]
_CADRUMO = _ROOT / "src/cadrumo"
_TUI_MODELO = _CADRUMO / "entrypoints/tui/modelo"

_ROUTES = _TUI_MODELO / "routes.py"
_ACTIONS = _TUI_MODELO / "actions.py"

_SPEC = CanonicalAuthoritySpec(
    targets=(
        CanonicalAuthorityTarget(
            module="cadrumo.entrypoints.tui.modelo.routes",
            path=_ROUTES,
            symbols=frozenset({"MODELO_WORKSPACE_DESTINATIONS", "resolve_destination", "declared_destination_ids"}),
        ),
        CanonicalAuthorityTarget(
            module="cadrumo.entrypoints.tui.modelo.actions",
            path=_ACTIONS,
            symbols=frozenset(
                {
                    "MODELO_ACTION_DISPATCH",
                    "MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS",
                    "ModeloActionView",
                    "ModeloActionPort",
                    "action_for_operation",
                }
            ),
        ),
    ),
)
"""The cohort's two shipped authorities: where a route goes, and what an action is.

The denominator is deliberately NOT a target here. It lives in `dev/quality`,
outside the shipped package, and `src` may not import it -- so its singularity
is asserted through its own validator below rather than through an import
census that would have nothing to census.
"""


def _scan_paths() -> tuple[Path, ...]:
    """Tracked files, plus the cohort's own declared authority modules.

    The scanner is built on `git ls-files`, so a module that is not yet staged
    is invisible to it and every symbol the spec declares canonical reads as
    MISSING. That is a property of the corpus, not a defect in the module.

    The union is scoped to THIS COHORT'S tree rather than to untracked files
    generally: absorbing whatever is untracked would pull a peer's in-flight
    work into this gate's denominator, which is the contaminated-artefact
    hazard the architecture lane records against regenerating inventories mid
    churn.
    """
    cohort = tuple(sorted(path for path in _TUI_MODELO.rglob("*.py") if "tests" not in path.parts))
    return tuple(dict.fromkeys((*tracked_live_files(), *cohort)))


def test_the_scan_sees_a_real_corpus() -> None:
    """Anti-vacuity: every assertion below is empty over an empty file set."""
    files = tracked_live_files()

    assert len(files) > 500, f"only {len(files)} tracked files scanned; the fixed point would be vacuous"
    assert _ROUTES.is_file() and _ACTIONS.is_file(), "a declared authority module is missing from the tree"


def test_each_cohort_authority_is_defined_in_exactly_one_module() -> None:
    """Two definitions of one authority is the defect this row exists to refuse.

    Reported with the scanner's own violation detail so a failure names the
    duplicate site rather than only its existence.
    """
    violations = scan_canonical_authority(_SPEC, paths=_scan_paths())

    assert not violations, "\n".join(f"  {violation}" for violation in violations)


def test_no_action_or_route_symbol_is_re_exported_by_a_namespace() -> None:
    """A namespace re-export is an alias by another name.

    Checked directly on the package `__init__` files rather than through the
    scanner's alias rule, because an inert namespace that binds nothing has no
    import edge for a census to find -- its emptiness is the property.
    """
    offenders: list[str] = []
    for package in (_TUI_MODELO, _TUI_MODELO / "action"):
        init = package / "__init__.py"
        if not init.is_file():
            continue
        tree = ast.parse(init.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                # A `from __future__` directive binds no project symbol; it is a
                # compiler instruction. Counting it would make every inert
                # namespace in the tree fail its own inertness check.
                continue
            if isinstance(node, ast.ImportFrom | ast.Import):
                offenders.append(f"{init.relative_to(_ROOT)}:{node.lineno} binds an import")

    assert not offenders, f"cohort namespaces must stay inert: {offenders}"


def test_the_action_denominator_reports_no_unclassified_candidate() -> None:
    """Reused, not restated: the retained validator is the authority on this.

    Re-implementing the classification comparison here would create the second
    denominator this gate exists to forbid.
    """
    errors = validate_modelo_workspace_action_denominator()

    assert not errors, "\n".join(f"  {error}" for error in errors)


def _cohort_name(path: Path) -> str:
    """Name a walked module, repository-relative where it can be.

    Absolute otherwise: a reporting path must never be more fragile than the
    walk it reports on, and relative_to raises for anything outside the tree.
    """
    if path.is_relative_to(_ROOT):
        return path.relative_to(_ROOT).as_posix()
    return path.as_posix()


#: Below this the cohort walk has stopped covering the shipped surface. A
#: floor, not a pinned count: twenty-eight modules ship today.
_MINIMUM_COHORT_MODULES = 10


def test_no_shipped_cohort_module_carries_a_transitional_marker() -> None:
    """Transitional rows are process state, and process state does not ship.

    A shipped surface describing itself as pending, provisional or
    to-be-replaced is a plan leaking into production, and it stays true only
    until the plan moves.
    """
    assert _TUI_MODELO.is_dir(), (
        f"no cohort tree at {_TUI_MODELO}; a relocated root walks nothing and this gate "
        "would report every shipped module marker-free"
    )

    markers = ("TODO", "FIXME", "XXX", "TRANSITIONAL", "PROVISIONAL", "for now")
    offenders: list[str] = []
    undecodable: list[str] = []
    read = 0
    for path in sorted(_TUI_MODELO.rglob("*.py")):
        if "tests" in path.parts:
            continue
        try:
            # Strict. With errors="ignore" a dropped byte takes any marker
            # straddling it with it, and the module then reads as clean.
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as refusal:
            undecodable.append(f"{_cohort_name(path)}: {refusal}")
            continue
        read += 1
        offenders.extend(f"{_cohort_name(path)}: {marker}" for marker in markers if marker in text)

    assert not undecodable, (
        "these shipped cohort modules could not be decoded, so a transitional marker inside "
        f"one was never searched for: {undecodable}"
    )
    assert read >= _MINIMUM_COHORT_MODULES, (
        f"only {read} shipped cohort module(s) were read; below this an empty offender list "
        "says nothing about whether process state is leaking into production"
    )
    assert not offenders, f"transitional markers in shipped cohort modules: {offenders}"


def test_the_transitional_sweep_can_see_a_marker_it_is_given() -> None:
    """Anti-tautology for the MATCHER, which is all an in-memory probe can prove.

    This case builds its subject as a string, so it shows the marker comparison
    works and nothing about whether any file was opened - the claim its wording
    carried before. That half is now the sweep's own corpus floor, which fails
    when the walk stops reading the shipped modules.
    """
    markers = ("TODO", "TRANSITIONAL")
    probe = "\n".join(("# TRANSITIONAL: a marker planted in memory", "value = 1"))

    found = [marker for marker in markers if marker in probe]

    assert found == ["TRANSITIONAL"], "the marker match itself does not work"
