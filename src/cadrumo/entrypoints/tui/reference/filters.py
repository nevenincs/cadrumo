"""The coordinates each reference read accepts, and the query a filled form makes.

A read takes exactly the coordinates its command takes: the same filters, with
the same ones required.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Final

from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.portals.categories import PortalCategory
from .reads import ReferenceQuery, ReferenceRead


class ReferenceFilterKind(StrEnum):
    """How one coordinate is asked for."""

    TEXT = "text"
    INTEGER = "integer"
    DATE = "date"
    CHOICE = "choice"
    FLAG = "flag"


@dataclass(frozen=True, slots=True)
class ReferenceFilter:
    """One coordinate of a read; ``name`` is the query member it fills."""

    name: str
    kind: ReferenceFilterKind = ReferenceFilterKind.TEXT
    required: bool = False
    choices: tuple[str, ...] = ()


class ReferenceFilterError(ValueError):
    """The form's values do not make a query; ``fields`` names the coordinates at fault."""

    def __init__(self, fields: tuple[str, ...]) -> None:
        """Retain the names of the coordinates to correct."""
        super().__init__("reference read coordinates are incomplete or malformed")
        self.fields = fields


_MODELO: Final = ReferenceFilter("modelo", required=True)
_SCOPE: Final = (
    ReferenceFilter("year", ReferenceFilterKind.INTEGER),
    ReferenceFilter("period"),
    ReferenceFilter("as_of", ReferenceFilterKind.DATE),
)

_FILTERS: Final[Mapping[ReferenceRead, tuple[ReferenceFilter, ...]]] = {
    ReferenceRead.MODELOS: (ReferenceFilter("year", ReferenceFilterKind.INTEGER), ReferenceFilter("domain")),
    ReferenceRead.SUPPORT_MATRIX: (),
    ReferenceRead.DESCRIBE: (_MODELO, *_SCOPE),
    ReferenceRead.CASILLAS: (
        _MODELO,
        *_SCOPE,
        ReferenceFilter("input_kind", ReferenceFilterKind.CHOICE, choices=tuple(kind.value for kind in InputKind)),
        ReferenceFilter("required", ReferenceFilterKind.FLAG),
        ReferenceFilter("form_number"),
        ReferenceFilter("casilla_number"),
    ),
    ReferenceRead.CASILLA: (_MODELO, ReferenceFilter("casilla", required=True), *_SCOPE),
    ReferenceRead.FORMULAS: (_MODELO, *_SCOPE),
    ReferenceRead.BINDINGS: (_MODELO, *_SCOPE),
    ReferenceRead.CATEGORIES: (),
    ReferenceRead.PORTALS: (
        ReferenceFilter(
            "category", ReferenceFilterKind.CHOICE, choices=tuple(category.value for category in PortalCategory)
        ),
        ReferenceFilter("modelo"),
    ),
    ReferenceRead.PORTAL: (ReferenceFilter("portal", required=True),),
    ReferenceRead.AUTH_PROVIDERS: (),
    ReferenceRead.APODERADO_SCOPES: (),
}

#: Reads whose filing year is composed with a period token, so a year alone is incomplete.
_YEAR_NEEDS_PERIOD: Final = frozenset(
    {ReferenceRead.DESCRIBE, ReferenceRead.CASILLAS, ReferenceRead.CASILLA, ReferenceRead.FORMULAS}
)


def filters_of(read: ReferenceRead) -> tuple[ReferenceFilter, ...]:
    """The coordinates one read accepts, in the order the form asks for them."""
    return _FILTERS[read]


def form_value(query: ReferenceQuery, reference_filter: ReferenceFilter) -> str | bool:
    """What the form shows for one coordinate of a query already made."""
    value = getattr(query, reference_filter.name)
    if reference_filter.kind is ReferenceFilterKind.FLAG:
        return bool(value)
    if value is None:
        return ""
    return value.isoformat() if isinstance(value, date) else str(value)


def _coordinate(reference_filter: ReferenceFilter, raw: object) -> object:
    if reference_filter.kind is ReferenceFilterKind.FLAG:
        return bool(raw)
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        return None
    if reference_filter.kind is ReferenceFilterKind.INTEGER:
        return int(text)
    if reference_filter.kind is ReferenceFilterKind.DATE:
        return date.fromisoformat(text)
    if reference_filter.kind is ReferenceFilterKind.CHOICE and text not in reference_filter.choices:
        raise ValueError(reference_filter.name)
    return text


def query_from_form(read: ReferenceRead, values: Mapping[str, object]) -> ReferenceQuery:
    """Build one read's query from the form's values.

    Raises:
        ReferenceFilterError: A coordinate is missing or does not fit its type.
    """
    coordinates: dict[str, object] = {}
    faults: list[str] = []
    for reference_filter in filters_of(read):
        try:
            value = _coordinate(reference_filter, values.get(reference_filter.name))
        except ValueError:
            faults.append(reference_filter.name)
            continue
        if value is None and reference_filter.required:
            faults.append(reference_filter.name)
        coordinates[reference_filter.name] = value
    if read in _YEAR_NEEDS_PERIOD and coordinates.get("year") is not None and coordinates.get("period") is None:
        faults.append("period")
    if faults:
        raise ReferenceFilterError(tuple(dict.fromkeys(faults)))

    def text(name: str) -> str | None:
        value = coordinates.get(name)
        return value if isinstance(value, str) else None

    year, as_of = coordinates.get("year"), coordinates.get("as_of")
    return ReferenceQuery(
        read=read,
        modelo=text("modelo"),
        year=year if isinstance(year, int) else None,
        period=text("period"),
        as_of=as_of if isinstance(as_of, date) else None,
        domain=text("domain"),
        input_kind=text("input_kind"),
        required=coordinates.get("required") is True,
        form_number=text("form_number"),
        casilla_number=text("casilla_number"),
        casilla=text("casilla"),
        category=text("category"),
        portal=text("portal"),
    )


def is_complete(query: ReferenceQuery) -> bool:
    """Whether a query already carries every coordinate its read cannot do without."""
    return all(
        getattr(query, reference_filter.name) not in (None, "")
        for reference_filter in filters_of(query.read)
        if reference_filter.required
    )


__all__ = [
    "ReferenceFilter",
    "ReferenceFilterError",
    "ReferenceFilterKind",
    "filters_of",
    "form_value",
    "is_complete",
    "query_from_form",
]
