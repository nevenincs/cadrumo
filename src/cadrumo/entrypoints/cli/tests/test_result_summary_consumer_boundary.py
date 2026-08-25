"""Localized result-summary rows stay inside the display layer.

``CalculationResultSummary`` rows carry a label resolved for the AMBIENT output
language: localization happens once, in the application layer, and the CLI
renderer passes ``row.label`` straight through. That is correct for an operator
display surface, which is the only thing that consumes them today.

It would be wrong for an export. A regulatory or filing consumer must receive
the official Spanish form, and the strict channel for that is an explicit
``get_label("es")`` request -- so a module that reads these rows under a
Catalan session and writes them to a fichero-BOE, a workbook, or a filing
artefact would emit a localized label into an official record, silently and in
a way no calculation test would observe.

Nothing else detects that. The behavioural tests exercise the summary and the
renderer, so a NEW consumer in an export module is invisible to every one of
them -- they never import export code. This gate is structural for that reason:
it fails on the commit that wires the consumer, not on the filing that leaks.

Scanning is by SYMBOL NAME across every ``from ... import`` in the tree, not by
importers of the defining module. That distinction is the whole design. The
project mandates importing through a package facade
(``aeat-architecture-boundaries``), and the one real consumer obeys
it -- ``_modelo_rendering`` reaches the payload type through ``_modelo_payloads``
and the application types through ``application.modelo``, never through a
definer. A gate keyed on the definers' importers would therefore score exactly
ZERO, report clean, and certify its own blindness as the baseline. Symbol-name
scanning is immune to that by construction: a facade re-export changes the path,
never the name.

This half covers the CLI payload row. The application-layer types
(``calculation_result_summary`` and the row it returns) are the same hazard by
the same mechanism and are guarded on the ``application/modelo`` side; the two
families are asserted separately because their permitted consumer sets differ,
and collapsing them would allowlist each against the other's surface.

The known limit: an ``import module`` plus attribute access would not be seen.
No consumer uses that form, and the project's import discipline pushes against
it, but the gate does not cover it.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory
from ....tests import REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PACKAGE_ROOT = REPO_ROOT / "src" / "cadrumo"

#: The CLI payload row. Localization has already happened by the time a value of
#: this type exists, so reaching it from an export leaks the ambient label just
#: as surely as reaching the application row does.
_PAYLOAD_SYMBOL = "ResultSummaryRowPayload"

#: The display layer, DERIVED from package location rather than enumerated: a new
#: rendering module needs no change here, while a consumer anywhere else fails the
#: gate. Hand-listing the permitted modules would decay on the next CLI surface.
_DISPLAY_LAYER = _PACKAGE_ROOT / "entrypoints" / "cli"

#: A FLOOR, not an exact count. It exists to refuse a silently-empty scan -- a
#: moved package root or a renamed symbol would otherwise report an empty
#: violation list and read as "no leak". It deliberately does NOT pin the exact
#: number: a legitimate new display-layer consumer would red an exact pin, the
#: repair for that is to bump the number, and a number people routinely bump has
#: stopped being a guard. The real invariant -- no consumer outside the display
#: layer -- is asserted directly and catches the hazard regardless of the count.
_MINIMUM_PAYLOAD_IMPORTERS = 2

#: EXACT, unlike the importer floor above, and the asymmetry is deliberate. A new
#: re-export point genuinely widens the symbol's reachable surface, which is the
#: thing this assertion exists to surface for review; here a bump IS the review
#: action rather than a way around one.
_EXPECTED_PAYLOAD_REEXPORTERS = 2


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


def _scan(symbol: str) -> tuple[list[Path], list[Path]]:
    """Return the modules importing ``symbol`` and those re-exporting it."""
    importers: list[Path] = []
    reexporters: list[Path] = []
    for path in _production_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _imports_symbol(tree, symbol):
            importers.append(path)
        if _reexports_symbol(tree, symbol):
            reexporters.append(path)
    return importers, reexporters


def _outside_display_layer(paths: Iterable[Path]) -> list[str]:
    """Return the offending paths, repo-relative where possible.

    A path outside the repository still reports rather than raising, so the
    formatter cannot turn a genuine finding into a crash that reads as an error
    in the gate instead of a violation in the tree.
    """
    offenders: list[str] = []
    for path in paths:
        if path.is_relative_to(_DISPLAY_LAYER):
            continue
        shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        offenders.append(str(shown).replace("\\", "/"))
    return sorted(offenders)


def test_no_module_outside_the_display_layer_consumes_the_summary_payload() -> None:
    """Only the CLI display layer may reach the localized payload row."""
    importers, _ = _scan(_PAYLOAD_SYMBOL)
    assert len(importers) >= _MINIMUM_PAYLOAD_IMPORTERS, (
        f"found only {len(importers)} importers of {_PAYLOAD_SYMBOL}; the scan matched fewer "
        "modules than the known consumers, so an empty violation list below would mean "
        "'nothing was checked' rather than 'nothing is wrong'"
    )
    offenders = _outside_display_layer(importers)
    assert offenders == [], (
        f"{_PAYLOAD_SYMBOL} carries a label already resolved for the ambient output language; "
        f"these modules sit outside the CLI display layer and would leak it: {offenders}"
    )


def test_the_payload_reexport_surface_is_the_one_we_think_it_is() -> None:
    """The re-export closure is COMPUTED, so a facade promotion is visible.

    The reachable paths for the symbol are what a naive definer-keyed gate got
    wrong. Pinning the computed set means a promotion that widens reach shows up
    as a failure to review rather than silently enlarging the surface -- and
    ``aeat-architecture-boundaries`` actively encourages exactly such
    promotions, so an assumed depth would be correct today and wrong later.
    """
    _, reexporters = _scan(_PAYLOAD_SYMBOL)
    assert len(reexporters) == _EXPECTED_PAYLOAD_REEXPORTERS, (
        f"the {_PAYLOAD_SYMBOL} re-export surface changed: {sorted(str(p.relative_to(REPO_ROOT)) for p in reexporters)}"
    )
    assert _outside_display_layer(reexporters) == []


def test_the_scan_flags_a_planted_export_consumer(tmp_path: Path) -> None:
    """Anti-tautology: the predicates fire on a module that would leak.

    Every real importer is a display surface, so the violation list is empty on
    live data and its teeth cannot be shown from the tree. Drive the same two
    predicates over planted source instead.
    """
    leaking = tmp_path / "_fichero_boe_writer.py"
    leaking.write_text(
        f"from ..cli._modelo_payloads import {_PAYLOAD_SYMBOL}\n__all__ = [{_PAYLOAD_SYMBOL!r}]\n",
        encoding="utf-8",
    )
    tree = ast.parse(leaking.read_text(encoding="utf-8"), filename=str(leaking))
    assert _imports_symbol(tree, _PAYLOAD_SYMBOL), "an export-side import must be detected"
    assert _reexports_symbol(tree, _PAYLOAD_SYMBOL), "an export-side re-export must be detected"
    assert _outside_display_layer([leaking]) == [str(leaking).replace("\\", "/")]

    # ...and a module touching neither is not flagged, so the predicates are not
    # simply returning True.
    inert = tmp_path / "_unrelated.py"
    inert.write_text("from decimal import Decimal\n__all__ = ['Decimal']\n", encoding="utf-8")
    inert_tree = ast.parse(inert.read_text(encoding="utf-8"), filename=str(inert))
    assert not _imports_symbol(inert_tree, _PAYLOAD_SYMBOL)
    assert not _reexports_symbol(inert_tree, _PAYLOAD_SYMBOL)


def test_the_scan_corpus_did_not_collapse() -> None:
    """A scan over an empty tree would report no violations and read as clean."""
    modules = list(_production_modules())
    assert len(modules) > 500, (
        f"scanned only {len(modules)} production modules under {_PACKAGE_ROOT}; the corpus "
        "collapsed, so an empty violation list would mean 'nothing was checked'"
    )
