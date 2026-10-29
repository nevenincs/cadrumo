"""Validate explicit transport-only omissions from human workbook surfaces.

:class:`ModeloRevision` declares the form and its value contracts.
"""

import re
from typing import cast

from ....domain.calculations.registry.schema import ModeloRevision
from .errors import CalcSheetsEngineError
from .records import SheetCellAddress, SheetFormulaCell


def formula_may_read_transport_cell(formula: SheetFormulaCell, addresses: tuple[SheetCellAddress, ...]) -> bool:
    """Refuse ranges/dynamic reads without a stronger proof; detect local A1 reads."""
    if not addresses:
        return False
    text = formula.formula.replace("$", "")
    if ":" in text or re.search(r"\b(?:INDIRECT|OFFSET)\s*\(", text, re.I):
        return True
    for address in addresses:
        if re.search(re.escape(address.qualified()) + r"(?![0-9])", text, re.I):
            return True
        if re.search(re.escape(address.tab.value + "!" + address.a1) + r"(?![0-9])", text, re.I):
            return True
        if address.tab is formula.address.tab and re.search(
            r"(?<![A-Za-z0-9_!])" + re.escape(address.a1) + r"(?![0-9])", text, re.I
        ):
            return True
    return False


def _references_excluded(value: object, excluded: frozenset[str]) -> bool:
    # Conservative exact identity matching also covers less common typed
    # expression/binding arms. A coincident identifier refuses omission.
    if isinstance(value, str):
        return value in excluded
    if isinstance(value, dict):
        return any(_references_excluded(v, excluded) for v in cast(dict[object, object], value).values())
    if isinstance(value, (list, tuple)):
        return any(_references_excluded(v, excluded) for v in cast(list[object] | tuple[object, ...], value))
    return False


def _transport_exclusion_ids(revision: ModeloRevision) -> frozenset[str]:
    return frozenset(
        p.casilla_id
        for layout in revision.form_layouts
        for p in layout.placements
        if p.workbook_exclusion == "transport_control"
    )


def workbook_transport_controls(revision: ModeloRevision) -> frozenset[str]:
    """Return authored transport controls, refusing calculation dependencies.

    This is a workbook presentation policy, not deletion from the registry or
    the filing export. Unknown or unplaced financial values cannot opt out.

    The ``revision`` parameter uses :class:`ModeloRevision`, which declares the form and its value contracts.
    """
    excluded = _transport_exclusion_ids(revision)
    if not excluded:
        return excluded

    casillas = {c.id: c for c in revision.casillas}
    if not excluded <= casillas.keys():
        raise CalcSheetsEngineError("workbook transport exclusion names an unknown casilla")
    for identifier in excluded:
        casilla = casillas[identifier]
        if casilla.data_type != "text" or casilla.formula is not None or casilla.binding is not None:
            raise CalcSheetsEngineError("workbook transport exclusion cannot remove a financial or bound value")
    _require_unreferenced_exclusions(revision, excluded)
    return excluded


def _require_unreferenced_exclusions(revision: ModeloRevision, excluded: frozenset[str]) -> None:
    if any(_references_excluded(f.model_dump(mode="json"), excluded) for f in revision.formulas) or any(
        _references_excluded(b.model_dump(mode="json"), excluded) for b in revision.bindings
    ):
        raise CalcSheetsEngineError("workbook transport exclusion is referenced by a calculation or binding")
    if any(page.condition_casilla_id in excluded for layout in revision.form_layouts for page in layout.pages):
        raise CalcSheetsEngineError("workbook transport exclusion controls a form page")
