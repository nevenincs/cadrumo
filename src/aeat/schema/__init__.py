"""Programmatic AEAT modelo schema extraction and typed IR.

This subpackage owns the pipeline that reads primary AEAT sources
(currently BOE-published *Ordenes ministeriales*) and emits typed,
versioned, pydantic v2 records the rest of the project consumes as
ground truth. The scope and decisions behind the shape live in the
2026-04-17 schema-extraction ADR and research document.

Consumers outside :mod:`aeat.schema` MUST import from this module
only; underscore-prefixed submodules are internal and unstable. The
public surface is the :data:`__all__` tuple below.

Non-goals:

- This subpackage is NOT the curated, human-reviewed catalogue —
  that is :mod:`aeat.casillas`. Schema records emitted here are the
  extractor IR, before review.
- :mod:`aeat.schema` MUST NOT import from :mod:`aeat.casillas`. The
  dependency direction is strictly downstream.
"""

from __future__ import annotations

from ._boe_extractor import BoeOrdenExtractor
from ._cache import (
    load_modelo_from_cache,
    resolve_schema_cache_file,
    save_modelo_to_cache,
)
from ._enums import (
    BinaryFormulaOp,
    CasillaDataType,
    CompareOp,
    SchemaSource,
)
from ._errors import (
    SchemaCacheError,
    SchemaError,
    SchemaEvaluationError,
    SchemaExtractionError,
    SchemaValidationError,
)
from ._fetch import (
    BOE_ORDEN_SOURCES,
    BoeOrdenSource,
    FetchedSchemaSource,
    fetch_boe_pdf,
)
from ._models import (
    BinaryOp,
    Casilla,
    CasillaRef,
    CrossCasillaRule,
    EnumRule,
    FormulaNode,
    LiteralFormula,
    Modelo,
    RangeRule,
    RegexRule,
    SchemaProvenance,
    SchemaVersion,
    SumFormula,
    ValidationRule,
    evaluate,
    validate_period_for_modelo,
)

__all__ = (
    "BOE_ORDEN_SOURCES",
    "BinaryFormulaOp",
    "BinaryOp",
    "BoeOrdenExtractor",
    "BoeOrdenSource",
    "Casilla",
    "CasillaDataType",
    "CasillaRef",
    "CompareOp",
    "CrossCasillaRule",
    "EnumRule",
    "FetchedSchemaSource",
    "FormulaNode",
    "LiteralFormula",
    "Modelo",
    "RangeRule",
    "RegexRule",
    "SchemaCacheError",
    "SchemaError",
    "SchemaEvaluationError",
    "SchemaExtractionError",
    "SchemaProvenance",
    "SchemaSource",
    "SchemaValidationError",
    "SchemaVersion",
    "SumFormula",
    "ValidationRule",
    "evaluate",
    "fetch_boe_pdf",
    "load_modelo_from_cache",
    "resolve_schema_cache_file",
    "save_modelo_to_cache",
    "validate_period_for_modelo",
)
