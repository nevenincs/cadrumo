"""Typed IR, cache, errors, and runtime evaluate for AEAT modelo schemas.

This subpackage owns the intermediate-representation (IR) types,
cache I/O, error hierarchy, and the ``evaluate`` / ``validate_period_for_modelo``
runtime functions. The BOE-PDF extraction engine lives in the inbound
adapter layer at :mod:`aeat.adapters.inbound.schema`.

Consumers outside :mod:`aeat.domain.schema` MUST import from this
module only; underscore-prefixed submodules are internal and unstable.
The public surface is the :data:`__all__` tuple below.

Non-goals:

- This subpackage is NOT the curated, human-reviewed catalogue --
  that is :mod:`aeat.domain.casillas`. Schema records emitted here are the
  extractor IR, before review.
- :mod:`aeat.domain.schema` MUST NOT import from :mod:`aeat.domain.casillas`.
  The dependency direction is strictly downstream.
"""

from __future__ import annotations

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
from ._models import (
    BinaryOp,
    Casilla,
    CrossCasillaRule,
    EnumRule,
    FormulaNode,
    LiteralFormula,
    Modelo,
    RangeRule,
    RegexRule,
    SchemaCasillaRef,
    SchemaProvenance,
    SchemaVersion,
    SumFormula,
    ValidationRule,
    evaluate,
    validate_period_for_modelo,
)

__all__ = (
    "BinaryFormulaOp",
    "BinaryOp",
    "Casilla",
    "CasillaDataType",
    "CompareOp",
    "CrossCasillaRule",
    "EnumRule",
    "FormulaNode",
    "LiteralFormula",
    "Modelo",
    "RangeRule",
    "RegexRule",
    "SchemaCacheError",
    "SchemaCasillaRef",
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
    "load_modelo_from_cache",
    "resolve_schema_cache_file",
    "save_modelo_to_cache",
    "validate_period_for_modelo",
)
