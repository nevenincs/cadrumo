"""Modern i18n primitives for the AEAT domain layer."""

from __future__ import annotations

from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class Translatable(str):
    """A strictly-typed marker for abstract i18n keys.

    Used to type-hint fields that hold translation keys rather than
    raw user-facing strings, ensuring all translatable text can be
    statically identified and routed through the python-i18n backend.
    """

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())


__all__ = ["Translatable"]
