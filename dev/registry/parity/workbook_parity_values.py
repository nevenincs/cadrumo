"""Normalize values exchanged with workbook recalculation backends."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from cadrumo.core.decimal.coercion import coerce_decimal

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these need not exist at runtime. openpyxl is one of
    # the heaviest third-party imports in the tree and this module is imported
    # eagerly by the registry facade, so the symbols that ARE needed at runtime
    # (``load_workbook``, ``Tokenizer``, and the ``TokenizerError`` /
    # ``InvalidFileException`` handler types) are imported inside the functions
    # that use them -- a taxpayer calculation must not load a spreadsheet engine.
    pass


def _excel_value(value: Decimal | int | str | bool) -> str | int | bool:
    if isinstance(value, Decimal):
        return str(value)
    return value


def _coerce_excel_result(value: object) -> Decimal | int | str | bool | None:
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        coerced = coerce_decimal(value)
        return coerced if coerced is not None else str(value)
    return str(value)
