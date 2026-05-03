"""Closed taxonomies exposed by :mod:`aeat.domain.schema`.

Every enum is a :class:`enum.StrEnum` so members compare equal to
their canonical string representation across JSON boundaries.

The module re-exports :class:`aeat.domain.casillas.models.CasillaDataType`
so consumers of :mod:`aeat.domain.schema` reach the same closed
data-type taxonomy without importing through the casillas corpus
package.
"""

from __future__ import annotations

from enum import StrEnum

from ..casillas.models import CasillaDataType

__all__ = [
    "BinaryFormulaOp",
    "CasillaDataType",
    "CompareOp",
    "SchemaSource",
]


class SchemaSource(StrEnum):
    """Provenance class of an extracted :class:`aeat.domain.schema.Modelo`.

    ``BOE_ORDEN`` is the only currently implemented member. Future
    extractors add new members here on first concrete use; reserved /
    speculative slots are intentionally not pre-declared so the
    :class:`pydantic.StrEnum` validator gates unknown source values
    on parse.

    Attributes:
        BOE_ORDEN: Schema extracted from a BOE Orden Ministerial PDF.
    """

    BOE_ORDEN = "boe_orden"


class BinaryFormulaOp(StrEnum):
    """Binary arithmetic operators supported by the formula AST.

    Attributes:
        ADD: Addition (``a + b``).
        SUB: Subtraction (``a - b``).
        MUL: Multiplication (``a * b``).
        DIV: Division (``a / b``); zero divisor raises at evaluation time.
    """

    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"


class CompareOp(StrEnum):
    """Comparison operators supported by
    :class:`aeat.domain.schema._models.CrossCasillaRule`.

    Attributes:
        EQ: Equal.
        NEQ: Not equal.
        LT: Less than.
        LTE: Less than or equal.
        GT: Greater than.
        GTE: Greater than or equal.
    """

    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
