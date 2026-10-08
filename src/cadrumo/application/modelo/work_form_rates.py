"""Resolve rates from bound values and official printed design facts."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .work_form_context import WorkFormContext

import re
from decimal import Decimal, InvalidOperation
from typing import Final

from ...domain.calculations.registry.ledger_iva_bindings import LedgerIvaProvider
from ...domain.calculations.registry.schema_base import CasillaDataType
from ...domain.calculations.registry.schema_form_layouts import FormCellKind, FormPageCondition, FormPageDefinition
from .edit_value_grammar import ModeloEditRatioUnit, ratio_unit
from .work_form_models import (
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormGridCell,
    ModeloFormGridRow,
    ModeloFormOrigin,
    ModeloFormPrintedRate,
    ModeloFormRate,
    ModeloFormRepeatingBlock,
    ModeloFormScalar,
    ModeloFormSection,
    section_fields,
)

_PERCENT_LITERAL: Final[re.Pattern[str]] = re.compile(r"\s*([0-9]+(?:[.,][0-9]+)?)\s*%\s*")

"""A design literal that states a percentage outright, such as ``21 %`` or ``1,75%``."""

_DIGIT_LITERAL: Final[re.Pattern[str]] = re.compile(r"[0-9]+")


def parse_form_number(value: ModeloFormScalar) -> Decimal | None:
    """Read a form scalar as a decimal while leaving booleans and non-numeric text unknown."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (Decimal, int)):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation:
            return None
    return None


def page_applies_for_values(
    page: FormPageDefinition, context: WorkFormContext, sections: tuple[ModeloFormSection, ...]
) -> bool | None:
    """Decide from declared facts alone whether a page applies; ``None`` when the data cannot say."""
    if page.condition is FormPageCondition.ALWAYS:
        return True
    if page.condition is FormPageCondition.PERIOD_RESTRICTED:
        return context.review.period.registry_token in page.condition_periods
    if page.condition is FormPageCondition.REQUIRES_POSITIVE_CASILLA and page.condition_casilla_id is not None:
        return _positive_casilla_page_applies(str(page.condition_casilla_id), context)
    return _page_has_value_or_records(sections)


def _positive_casilla_page_applies(casilla_id: str, context: WorkFormContext) -> bool | None:
    row = context.rows.get(casilla_id)
    amount = None if row is None else parse_form_number(row.value)
    return None if amount is None else amount > 0


def _page_has_value_or_records(sections: tuple[ModeloFormSection, ...]) -> bool | None:
    has_value = any(
        field.origin in {ModeloFormOrigin.ENTERED, ModeloFormOrigin.IMPORTED, ModeloFormOrigin.OVERRIDES_SOURCE}
        for section in sections
        for field in section_fields(section)
    )
    has_records = any(
        isinstance(block, ModeloFormRepeatingBlock) and bool(block.rows)
        for section in sections
        for block in section.blocks
    )
    return True if has_value or has_records else None


def _grounded_rate(field: ModeloFormField, context: WorkFormContext) -> ModeloFormRate | None:
    """The one rate the bindings filling a base box declare, or ``None`` when they do not declare exactly one.

    Every binding that fills the box must be a rate-specific IVA ledger
    aggregate: a rate-blind binding admits records at any rate of its tier, so
    a box it fills is not grounded on one rate, however the others read.
    """
    if not isinstance(field.address, ModeloFormCasillaAddressV1):
        return None
    casilla = context.casillas.get(str(field.address.casilla_id))
    if casilla is None:
        return None
    binding_ids = tuple(item for item in (casilla.binding, *casilla.alternate_bindings) if item is not None)
    rates: set[Decimal] = set()
    for binding_id in binding_ids:
        binding = context.bindings.get(str(binding_id))
        provider = None if binding is None else binding.provider
        if not isinstance(provider, LedgerIvaProvider) or provider.applied_rates is None:
            return None
        rates.update(provider.applied_rates)
    if len(rates) != 1:
        return None
    return ModeloFormRate(ratio=rates.pop(), binding_id=binding_ids[0])


def with_grounded_grid_rates(
    cells: tuple[ModeloFormGridCell, ...], context: WorkFormContext
) -> tuple[ModeloFormGridCell, ...]:
    """Give an official row's rate box the one rate its base box is grounded on.

    The row must print exactly one rate box, and its other boxes must be
    grounded on exactly one rate between them; any other row is left as it is,
    with no rate claimed for its rate box.
    """
    rate_index = _rate_cell_index(cells)
    if rate_index is None or _placeholder_literal(cells[rate_index]):
        # The design prints zeros where this row's rate would stand: it prints no rate, so none is claimed.
        return cells
    grounded = _grounded_rates(cells, rate_index, context)
    if len(grounded) != 1:
        return cells
    rate_cell = cells[rate_index]
    if rate_cell.field is None:
        return cells
    (rate,) = grounded.values()
    field = rate_cell.field.model_copy(update={"grounded_rate": rate})
    return tuple(
        rate_cell.model_copy(update={"field": field}) if index == rate_index else cell
        for index, cell in enumerate(cells)
    )


def _rate_cell_index(cells: tuple[ModeloFormGridCell, ...]) -> int | None:
    rate_indexes = [
        index
        for index, cell in enumerate(cells)
        if cell.field is not None and cell.field.data_type == CasillaDataType.RATIO.value
    ]
    return rate_indexes[0] if len(rate_indexes) == 1 else None


def _grounded_rates(
    cells: tuple[ModeloFormGridCell, ...], rate_index: int, context: WorkFormContext
) -> dict[Decimal, ModeloFormRate]:
    grounded: dict[Decimal, ModeloFormRate] = {}
    for index, cell in enumerate(cells):
        rate = None if index == rate_index or cell.field is None else _grounded_rate(cell.field, context)
        if rate is not None:
            grounded.setdefault(rate.ratio, rate)
    return grounded


def _rate_literal(cell: ModeloFormGridCell) -> str | None:
    """The literal of a rate box the design fixes, or ``None`` for any other cell."""
    field = cell.field
    if cell.kind is not FormCellKind.DESIGN_CONSTANT or field is None or cell.literal is None:
        return None
    return cell.literal if field.data_type == CasillaDataType.RATIO.value else None


def _placeholder_literal(cell: ModeloFormGridCell) -> bool:
    """Whether a rate box the design fixes holds only zeros, the design's placeholder where no rate is printed."""
    literal = _rate_literal(cell)
    return literal is not None and _DIGIT_LITERAL.fullmatch(literal) is not None and int(literal) == 0


def _stated_percent(literal: str) -> Decimal | None:
    """A literal that states a percentage outright, as a fraction of one."""
    match = _PERCENT_LITERAL.fullmatch(literal)
    if match is None:
        return None
    return Decimal(match.group(1).replace(",", ".")).scaleb(-2)


def _declared_scale_rate(field: ModeloFormField) -> Decimal | None:
    """A fixed rate box's figure read at the scale its export field declares, as a fraction of one.

    The box holds a figure only when the export field declares its implied
    decimals; the casilla's declared bounds then say whether that figure is a
    percentage or a fraction. Without both, the literal's scale is unknown and
    no rate is read from it.
    """
    value = field.value
    if not isinstance(value, Decimal):
        return None
    maximum = None if field.constraints is None else field.constraints.max_value
    unit = ratio_unit(field.data_type, maximum)
    if unit is ModeloEditRatioUnit.PERCENT:
        return value.scaleb(-2)
    if unit is ModeloEditRatioUnit.FRACTION:
        return value
    return None


def _printed_rate(cell: ModeloFormGridCell) -> ModeloFormPrintedRate | None:
    """The rate a fixed rate box prints, where its literal states it or its export field declares the scale.

    Nothing is inferred from other rows: a literal whose scale is not declared
    prints no rate Cadrumo can state.
    """
    literal = _rate_literal(cell)
    if literal is None or cell.field is None or _placeholder_literal(cell):
        return None
    ratio = _stated_percent(literal)
    if ratio is None:
        ratio = _declared_scale_rate(cell.field)
    if ratio is None or not Decimal(0) < ratio <= 1:
        return None
    return ModeloFormPrintedRate(ratio=ratio.normalize(), literal=literal)


def with_printed_row_rates(rows: tuple[ModeloFormGridRow, ...]) -> tuple[ModeloFormGridRow, ...]:
    """Give each rate box the design fixes the rate its literal prints, where that reading is declared."""
    updated: list[ModeloFormGridRow] = []
    for row in rows:
        cells: list[ModeloFormGridCell] = []
        for cell in row.cells:
            printed = _printed_rate(cell)
            if printed is None or cell.field is None:
                cells.append(cell)
                continue
            field = cell.field.model_copy(update={"printed_rate": printed})
            cells.append(cell.model_copy(update={"field": field}))
        updated.append(row.model_copy(update={"cells": tuple(cells)}))
    return tuple(updated)


def read_design_value(literal: str, decimals: int | None) -> Decimal | None:
    """Read a design literal as the fichero writes it: digits with the export field's implied decimals."""
    if decimals is None or not literal.isdigit():
        return None
    return Decimal(int(literal)).scaleb(-decimals)
