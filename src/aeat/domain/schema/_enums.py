"""Closed taxonomies exposed by :mod:`aeat.domain.schema`.

Every enum is a :class:`str.StrEnum` so members compare equal to
their canonical string representation across JSON boundaries.
"""

from __future__ import annotations

from enum import StrEnum

from ..casillas.models import CasillaDataType


class SchemaSource(StrEnum):
    """Provenance class of an extracted :class:`aeat.domain.schema.Modelo`.

    ``BOE_ORDEN`` is the only member implemented in the v1 PoC. Three
    reserved follow-up extractor slots (``PORTAL_HTML_PROBE``,
    ``MANUAL_LLM_DRAFT``, ``XSD_WIRE``) were dropped per restructure
    ADR Decision 6 (#476) — no active branch or open issue references
    them. Future extractors add new members here on first concrete
    use.
    """

    BOE_ORDEN = "boe_orden"


class BinaryFormulaOp(StrEnum):
    """Binary arithmetic operators supported by the formula AST."""

    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"


class CompareOp(StrEnum):
    """Comparison operators supported by :class:`CrossCasillaRule`."""

    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
