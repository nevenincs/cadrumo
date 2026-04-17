"""Closed taxonomies exposed by :mod:`aeat.schema`.

Every enum is a :class:`str.StrEnum` so members compare equal to
their canonical string representation across JSON boundaries.
"""

from __future__ import annotations

from enum import StrEnum


class SchemaSource(StrEnum):
    """Provenance class of an extracted :class:`aeat.schema.Modelo`.

    ``BOE_ORDEN`` is the only member implemented in the v1 PoC; the
    remaining members are reserved enum slots for the follow-up
    extractors described in the 2026-04-17 ADR.
    """

    BOE_ORDEN = "boe_orden"
    PORTAL_HTML_PROBE = "portal_html_probe"
    MANUAL_LLM_DRAFT = "manual_llm_draft"
    XSD_WIRE = "xsd_wire"


class CasillaDataType(StrEnum):
    """Closed catalogue of casilla data types.

    Owned by :mod:`aeat.schema`. The adjacent
    :class:`aeat.casillas.models.CasillaDataType` carries the same
    member values for the curated reviewer corpus; the two enums are
    bridged by string-value round-trip (see the 2026-04-17 schema
    extraction ADR §7). ``isinstance`` comparisons across the two
    enums are forbidden.
    """

    CURRENCY_EUR = "currency_eur"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    TEXT = "text"
    SELECT = "select"
    PERCENTAGE = "percentage"


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
