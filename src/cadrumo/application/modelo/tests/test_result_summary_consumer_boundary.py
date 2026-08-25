"""The localized result summary stays inside its owning package and the display layer.

``CalculationResultSummary`` rows carry a label already resolved for the ambient
output language. That is correct for a display surface and wrong for an export:
a filing, fichero-BOE or workbook consumer reading ``row.label`` under a Catalan
session would put a Catalan string into an artefact the regulatory channel
requires in official Spanish. No such consumer exists today, and no value-level
test can see one arrive -- a test that exercises the summary and the renderer
never imports export code, so a new export consumer satisfies every assertion it
makes. This gate fails on the commit that wires one instead.

Scanning is by SYMBOL NAME across every ``from ... import``, not by importers of
the defining module. That distinction is the whole design: a direct-defining
module migration changes the import path but not the protected symbol name, so
name scanning remains immune to it without a closure walk to keep in step.

The defining module is the sole re-export surface. The inert
``application.modelo`` namespace must never become a second publisher.

Known limit, stated rather than implied: ``import cadrumo.application.modelo``
followed by attribute access is not an ``ImportFrom`` and is not seen. No
consumer uses that form and the import discipline pushes against it, but the gate
does not cover it.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_REPO_ROOT = _PACKAGE_ROOT.parents[1]

#: The application-side result-summary types. Each carries, or produces, the
#: already-localized label; the CLI payload row is the other family and is
#: asserted separately by the CLI-side gate. Collapsing the two would allowlist
#: each against the other's permitted surface.
_APPLICATION_SYMBOLS: tuple[str, ...] = (
    "calculation_result_summary",
    "CalculationResultSummary",
    "ResultSummaryRow",
)

#: The two layers permitted to hold these types, DERIVED from package location
#: rather than enumerated: the owning package, and the display layer. A new
#: rendering module needs no edit here; a consumer anywhere else fails.
_OWNING_PACKAGE = _PACKAGE_ROOT / "application" / "modelo"
_DISPLAY_LAYER = _PACKAGE_ROOT / "entrypoints" / "cli"

#: Anti-vacuity floor for the module walk. A scan that silently matches nothing
#: -- a moved package root, a renamed symbol -- would otherwise report an empty
#: violation list, and an empty violation list reads as "no leak".
_MINIMUM_MODULES_SCANNED = 200

#: The defining module is the sole publisher; a package-facade re-export is a
#: duplicate authority after S170's inert-namespace convergence.
_EXPECTED_REEXPORTERS = 1


def _production_modules() -> Iterator[Path]:
    for path in scan_directory(_PACKAGE_ROOT, pattern="*.py", recursive=True):
        if "tests" in path.parts or path.name.startswith("test_"):
            continue
        yield path


def _imports_symbol(tree: ast.AST, symbol: str) -> bool:
    """Whether the module imports ``symbol`` by name, from any module path."""
    return any(
        isinstance(node, ast.ImportFrom) and any(alias.name == symbol for alias in node.names)
        for node in ast.walk(tree)
    )


def _reexports_symbol(tree: ast.AST, symbol: str) -> bool:
    """Whether the module re-publishes ``symbol`` through its ``__all__``."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            continue
        if isinstance(node.value, ast.List | ast.Tuple) and any(
            isinstance(item, ast.Constant) and item.value == symbol for item in node.value.elts
        ):
            return True
    return False


def _scan(symbol: str) -> tuple[list[Path], list[Path], int]:
    """Return modules importing ``symbol``, modules re-exporting it, and modules read."""
    importers: list[Path] = []
    reexporters: list[Path] = []
    scanned = 0
    for path in _production_modules():
        scanned += 1
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _imports_symbol(tree, symbol):
            importers.append(path)
        if _reexports_symbol(tree, symbol):
            reexporters.append(path)
    return importers, reexporters, scanned


def _outside_permitted_layers(paths: Iterable[Path]) -> list[str]:
    """Return offending paths, repo-relative where possible.

    A path outside the repository reports rather than raising, so a formatting
    problem cannot turn a genuine finding into a crash that reads as a broken
    gate instead of a violation in the tree.
    """
    offenders: list[str] = []
    for path in paths:
        if path.is_relative_to(_OWNING_PACKAGE) or path.is_relative_to(_DISPLAY_LAYER):
            continue
        try:
            offenders.append(str(path.relative_to(_REPO_ROOT)))
        except ValueError:
            offenders.append(str(path))
    return sorted(offenders)


@pytest.mark.parametrize("symbol", _APPLICATION_SYMBOLS)
def test_the_localized_summary_is_not_reached_from_outside_its_layers(symbol: str) -> None:
    """No module outside the owning package or the display layer imports the type."""
    importers, _reexporters, _scanned = _scan(symbol)
    offenders = _outside_permitted_layers(importers)

    assert offenders == [], (
        f"{symbol} carries a label already resolved for the ambient output language, and is "
        "reached from outside the owning package and the display layer. An export, filing or "
        "fichero-BOE consumer would put a non-Spanish label into an artefact the regulatory "
        f"channel requires in official Spanish. Offending modules: {offenders}"
    )


@pytest.mark.parametrize("symbol", _APPLICATION_SYMBOLS)
def test_the_scan_still_matches_the_symbol(symbol: str) -> None:
    """The gate measured a real corpus and the symbol still resolves.

    A lower bound rather than an exact count: an exact pin reds when a legitimate
    new display module imports the type, which trains a reader to bump the number,
    and a number people routinely bump has stopped being a guard. The floor still
    refuses the silently-empty scan this design exists to prevent.
    """
    importers, _reexporters, scanned = _scan(symbol)

    assert scanned >= _MINIMUM_MODULES_SCANNED, (
        f"only {scanned} production modules scanned; the walk has stopped matching and an "
        "empty violation list would be meaningless"
    )
    assert importers, f"no module imports {symbol}; it was renamed or removed and this gate is now inert"


@pytest.mark.parametrize("symbol", _APPLICATION_SYMBOLS)
def test_the_defining_module_is_the_sole_reexport_surface(symbol: str) -> None:
    """A facade promotion is duplicate authority and must fail the fixed point.

    The re-export set is computed rather than inferred from module depth. Name
    scanning independently covers importers; this inventory prevents a second
    publisher from re-entering through the inert package namespace.
    """
    _importers, reexporters, _scanned = _scan(symbol)
    relative = sorted(str(path.relative_to(_REPO_ROOT)) for path in reexporters)

    assert all(path.is_relative_to(_OWNING_PACKAGE) for path in reexporters), (
        f"{symbol} is re-exported from outside its owning package, widening the surface a "
        f"consumer can reach it through: {relative}"
    )
    assert len(reexporters) == _EXPECTED_REEXPORTERS, (
        f"the {symbol} re-export surface has {len(reexporters)} publishers: {relative}. "
        "The defining module is the sole permitted publisher; delete any facade re-export."
    )


def test_the_boundary_predicates_can_fail() -> None:
    """Drive planted source through the real predicates so both are known to discriminate.

    Every real importer is inside a permitted layer, so the live violation list is
    empty and the assertions above pass without ever exercising their failing
    branch. A gate whose teeth are never shown is indistinguishable from one that
    cannot bite.
    """
    leaking = ast.parse("from ...application.modelo import ResultSummaryRow\n")
    inert = ast.parse("from ...application.modelo import work_unit_for_revision\n")

    assert _imports_symbol(leaking, "ResultSummaryRow")
    assert not _imports_symbol(inert, "ResultSummaryRow")

    # The prefix collision, pinned in the direction that can actually fail.
    # ``ResultSummaryRow`` is a strict prefix of ``ResultSummaryRowPayload``, so a
    # substring matcher scanning the SHORTER name would match the LONGER import and
    # silently merge the two families -- each allowlisted against the other's
    # permitted surface, which is the failure the split exists to prevent. The
    # reverse direction cannot fail under either matcher and asserting it would
    # prove nothing.
    payload_import = ast.parse("from ....entrypoints.cli import ResultSummaryRowPayload\n")

    assert not _imports_symbol(payload_import, "ResultSummaryRow"), (
        "scanning the application row matched a CLI payload import: the matcher is not "
        "exact and the two families have merged"
    )

    republishing = ast.parse('__all__ = ["ResultSummaryRow"]\n')
    silent = ast.parse('__all__ = ["work_unit_for_revision"]\n')

    assert _reexports_symbol(republishing, "ResultSummaryRow")
    assert not _reexports_symbol(silent, "ResultSummaryRow")

    export_module = _PACKAGE_ROOT / "application" / "filing" / "_calculate.py"
    assert _outside_permitted_layers([export_module]) == [
        str(export_module.relative_to(_REPO_ROOT)),
    ], "a module outside both permitted layers must be reported as an offender"
