"""Export fields known to carry another page's casilla, held red until the registry gives each its own identity.

The readback compares a stated casilla with the fields of the fichero that carry its identity, and it accepts the
casilla when any one of them agrees. A field the map binds to another page's bare casilla identity therefore reads
back as that casilla, and the page that owns the identity masks it. The registry writes and parses through the same
map, so a round trip cannot see the mislabelling. The design prints these fields as their own cells; this module is
the independent expectation that no listed field of the written fichero carries the identity named for it.

A field is named by its design cell (page record and field number) without the edition, so the expectation holds for
every edition whose map keeps the binding and goes green when the registry rebinds the field.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.export_parse_models import ParsedExportFieldValue


@dataclass(frozen=True, slots=True)
class ForeignCarrier:
    """A design cell whose export field must not carry the casilla identity of another page's field."""

    modelo: str
    cell: str
    casilla: str
    owner_cell: str


KNOWN_FOREIGN_CARRIERS: tuple[ForeignCarrier, ...] = (
    ForeignCarrier(modelo="200", cell="dp200032.f0092", casilla="DP200010:00524", owner_cell="dp200010.f0080"),
    ForeignCarrier(modelo="200", cell="dp200043.f0054", casilla="DP200010:00524", owner_cell="dp200010.f0080"),
    ForeignCarrier(modelo="200", cell="dp200043.f0055", casilla="DP200010:00525", owner_cell="dp200010.f0081"),
    ForeignCarrier(modelo="200", cell="dp200043.f0056", casilla="DP200010:00526", owner_cell="dp200010.f0082"),
)
"""The cells found carrying DP200010's casillas, each with the page-qualified identity its owner cell holds."""


def _cell(field: ParsedExportFieldValue) -> str:
    """The design cell of a parsed field: its id without the leading edition token."""
    _edition, _, cell = str(field.field_id).partition(".")
    return cell


def _label(cell: str) -> str:
    page, _, number = cell.partition(".f")
    return f"{page.upper()} f{int(number)}"


def foreign_carrier_mismatches(modelo: str, parsed: Iterable[ParsedExportFieldValue]) -> list[str]:
    """Each listed field of the fichero that carries another page's casilla, worded for the export reason."""
    watched = {(item.cell, item.casilla): item for item in KNOWN_FOREIGN_CARRIERS if item.modelo == modelo}
    if not watched:
        return []
    found: list[str] = []
    for field in parsed:
        if field.casilla_id is None:
            continue
        item = watched.get((_cell(field), str(field.casilla_id)))
        if item is not None:
            found.append(f"{_label(item.cell)} carries casilla {item.casilla} of {_label(item.owner_cell)}")
    return found


def cross_page_reuse_mismatches(
    unadjudicated: Iterable[CasillaId], parsed: Iterable[ParsedExportFieldValue]
) -> list[str]:
    """The casilla identities the registry leaves unadjudicated that the fichero binds on more than one page.

    The registry owns which cross-page reuse is a declared repeat of one box (a segment on the casilla, a split value
    policy, or an echo cell); this check only reports an identity the registry itself leaves without a declared
    relation, read from the written fichero, as one counted reason.
    """
    wanted = {str(casilla) for casilla in unadjudicated}
    if not wanted:
        return []
    pages: dict[str, set[str]] = {}
    for field in parsed:
        if field.casilla_id is not None and str(field.casilla_id) in wanted:
            pages.setdefault(str(field.casilla_id), set()).add(_cell(field).partition(".")[0])
    reused = sorted(casilla for casilla, sheets in pages.items() if len(sheets) > 1)
    if not reused:
        return []
    first = ", ".join(reused[:3])
    return [
        f"{len(reused)} casilla identities are bound on more than one page (first {first}), "
        "not declared as repeats by the registry"
    ]
