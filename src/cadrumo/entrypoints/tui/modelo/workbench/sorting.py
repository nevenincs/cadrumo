"""Order the whole declaration other than as the form prints it: by box, by amount, or what needs the filer.

Form order is the default and keeps the official pages. Any other order lays
every page's boxes out as one flat list, each line naming its page and section,
so a filer looking for the largest amounts or everything still to do sees them
together. The boxes of one printed grid row stay together, in the row's own
order, wherever the row sorts. The active filter still applies.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from .....application.modelo.work_form_models import ModeloFormField, ModeloFormOrigin, address_key, section_fields
from .casilla_list import AddressKey, CasillaListEntry, CasillaListHeading, description_text
from .navigator import readable_text
from .page_items import StagedDisplay, WorkbenchFilter, WorkbenchPage, page_items


class SortOrder(StrEnum):
    """How the boxes are ordered."""

    FORM = "form"
    BOX = "box"
    AMOUNT = "amount"
    ATTENTION = "attention"


SORT_LOCALE_KEYS: Final[Mapping[SortOrder, str]] = MappingProxyType(
    {
        SortOrder.FORM: "tui.modelo.workbench.sort.form",
        SortOrder.BOX: "tui.modelo.workbench.sort.box",
        SortOrder.AMOUNT: "tui.modelo.workbench.sort.amount",
        SortOrder.ATTENTION: "tui.modelo.workbench.sort.attention",
    }
)
"""The words naming each order on the page title line; total over the orders."""

_BOX_DIGITS: Final[re.Pattern[str]] = re.compile(r"(\d+)(.*)")
_SEPARATOR: Final[str] = " · "
_ATTENTION_RANKS: Final[Mapping[ModeloFormOrigin, int]] = MappingProxyType(
    {
        ModeloFormOrigin.NEEDS_INPUT: 1,
        ModeloFormOrigin.CALCULATION_FAILED: 1,
        ModeloFormOrigin.DEFAULT_TO_CONFIRM: 2,
        ModeloFormOrigin.NOT_IMPORTED_YET: 3,
    }
)
_BLOCKED_RANK: Final[int] = 0
_STAGED_RANK: Final[int] = 4
_SETTLED_RANK: Final[int] = 5


def next_order(order: SortOrder) -> SortOrder:
    """The order after ``order``, back to form order after the last."""
    orders = tuple(SortOrder)
    return orders[(orders.index(order) + 1) % len(orders)]


def _box_key(field: ModeloFormField) -> tuple[int, int, str]:
    box = field.box
    if box is None:
        return (2, 0, "")
    match = _BOX_DIGITS.fullmatch(box)
    if match is None:
        return (1, 0, box)
    return (0, int(match.group(1)), str(match.group(2)))


def _amount(field: ModeloFormField) -> Decimal | None:
    value = field.value
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        return None
    return abs(Decimal(value))


def _attention_rank(entry: CasillaListEntry) -> int:
    if entry.field.blockers:
        return _BLOCKED_RANK
    rank = _ATTENTION_RANKS.get(entry.field.origin)
    if rank is not None:
        return rank
    return _STAGED_RANK if entry.staged_text is not None else _SETTLED_RANK


def _unit_key(unit: list[CasillaListEntry], order: SortOrder) -> tuple[object, ...]:
    if order is SortOrder.BOX:
        return min(_box_key(entry.field) for entry in unit)
    if order is SortOrder.AMOUNT:
        amounts = [amount for entry in unit if (amount := _amount(entry.field)) is not None]
        return (0, -max(amounts)) if amounts else (1, Decimal(0))
    if order is SortOrder.ATTENTION:
        return (min(_attention_rank(entry) for entry in unit),)
    return ()


def _units(page: WorkbenchPage, items: tuple[object, ...]) -> list[list[CasillaListEntry]]:
    """The page's shown boxes as sortable units: a grid row's boxes together, any other box alone."""
    sections: dict[AddressKey, str] = {
        address_key(field.address): section.heading.text
        for section in page.sections
        for field in section_fields(section)
    }
    units: list[list[CasillaListEntry]] = []
    row: list[CasillaListEntry] | None = None
    row_heading = ""
    for item in items:
        if isinstance(item, CasillaListHeading):
            row = [] if item.level else None
            row_heading = item.text if item.level else ""
            if row is not None:
                units.append(row)
            continue
        if not isinstance(item, CasillaListEntry):
            continue
        place = _SEPARATOR.join(part for part in (page.heading.text, sections.get(item.key)) if part)
        own = item.label or readable_text(item.field.label) or description_text(item.field) or ""
        label = f"{row_heading}: {own}" if row is not None and item.indent and row_heading else own
        entry = replace(item, indent=0, label=_SEPARATOR.join(part for part in (label, place) if part))
        if row is not None and item.indent:
            row.append(entry)
        else:
            units.append([entry])
    return [unit for unit in units if unit]


def sorted_items(
    pages: tuple[WorkbenchPage, ...],
    *,
    order: SortOrder,
    staged: Mapping[AddressKey, StagedDisplay],
    mode: WorkbenchFilter = WorkbenchFilter.ALL,
) -> tuple[CasillaListEntry, ...]:
    """Every page's shown boxes as one flat list in ``order``, form order breaking every tie."""
    units: list[list[CasillaListEntry]] = []
    for page in pages:
        units.extend(_units(page, page_items(page, staged=staged, mode=mode)))
    ranked = sorted(enumerate(units), key=lambda pair: (_unit_key(pair[1], order), pair[0]))
    return tuple(entry for _, unit in ranked for entry in unit)


__all__ = ["SORT_LOCALE_KEYS", "SortOrder", "next_order", "sorted_items"]
