"""Validated AEAT modelo identifier value object.

:class:`ModeloCode` enforces the three-digit identifier shape used by modelo
work units and registry lookups, raising :class:`ModeloValidationError` before
filing-grade availability is resolved from registry snapshots.
"""

from __future__ import annotations

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema

from .errors import ModeloValidationError


class ModeloCode(str):
    """Three-digit AEAT modelo identifier.

    This type validates identifier shape only. Filing-grade availability is
    resolved from registry snapshots.
    """

    def __new__(cls, value: str) -> ModeloCode:
        raw = str(value)
        if len(raw) != 3 or not raw.isdigit():
            raise ModeloValidationError(f"modelo code must be a three-digit string, got {value!r}")
        return str.__new__(cls, raw)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        del source_type, handler
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())
