"""Syntax-validated tax-domain identifiers.

Catalogue membership belongs to the published registry authority. This module
defines only the stable wire identifier shape needed during its reconstruction.
"""

from __future__ import annotations

import re

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

from .errors.hierarchy import CoreValidationError

__all__ = ["TaxDomain"]

_TAX_DOMAIN_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class TaxDomain(str):
    """Open tax-domain identifier whose membership is authority-validated."""

    __slots__ = ()

    def __new__(cls, value: str) -> TaxDomain:
        raw = str(value)
        if _TAX_DOMAIN_PATTERN.fullmatch(raw) is None:
            raise CoreValidationError(f"invalid tax-domain identifier: {value!r}")
        return str.__new__(cls, raw)

    @property
    def value(self) -> str:
        """Return the stable string representation used on the wire."""
        return str(self)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        """Validate from and serialize to the canonical JSON string shape."""
        del source_type, handler
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(pattern=_TAX_DOMAIN_PATTERN.pattern),
            serialization=core_schema.to_string_ser_schema(),
        )
