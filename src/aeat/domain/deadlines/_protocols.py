"""Internal validating-string identifier for AEAT modelos.

The deadline engine cannot import :mod:`aeat.domain.modelos` directly:
:mod:`aeat.domain.modelos._registry` imports from :mod:`aeat.domain.deadlines` to
expose :func:`aeat.domain.modelos.year_plan`, so a hard back-edge would cause
a circular import at package-load time.

:class:`ModeloIdentifier` is therefore a deadlines-internal
regex-validated ``str`` subclass. Pydantic schema-aware validation
keeps boundary-crossing payloads (notably :class:`Schedule`) honest
without forcing the engine to depend on the closed
:class:`aeat.domain.modelos.ModeloCode` enum. Live AEAT payloads occasionally
carry modelos that are not yet in our v1 inventory; this type lets
those flow through the boundary without crashing the engine.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

_MODELO_RE = re.compile(r"^\d{3}[A-Z]?$")


class ModeloIdentifier(str):
    """Typed string identifier for an AEAT modelo (e.g. ``"100"``, ``"303"``).

    The format is intentionally permissive — three digits with an
    optional trailing uppercase letter — to admit modelos that have
    not yet been promoted into the closed :class:`aeat.domain.modelos.ModeloCode`
    catalogue.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> ModeloIdentifier:
        if not isinstance(value, str) or not _MODELO_RE.match(value):
            raise ValueError(f"Invalid modelo identifier: {value!r}")
        return super().__new__(cls, value)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: Any,
        handler: GetCoreSchemaHandler,
    ) -> CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,
            core_schema.str_schema(pattern=_MODELO_RE.pattern),
        )
