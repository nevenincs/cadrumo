"""Opaque token contract for registry-owned LIVA art. 104.Tres exclusions.

The exclusion vocabulary and its legal semantics are governed facts. They are
projected at the domain boundary from the dated facts registry; this core
module deliberately retains only the transport type used by persistence and
command models.
"""

from __future__ import annotations

from .errors.hierarchy import pydantic_validation_boundary


class Art104TresExclusion(str):
    """Opaque registry-projected art. 104.Tres exclusion token.

    Membership is intentionally not represented here. Callers that accept a
    token must resolve it through the typed registry projection before using
    it. ``value`` is retained as a neutral string accessor for the existing
    serialization boundary; it does not enumerate or validate any token.
    """

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the opaque token as a string to Pydantic without a catalogue."""
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(pydantic_validation_boundary(cls), core_schema.str_schema())

    @property
    def value(self) -> str:
        """Return the opaque token for string-oriented serialization."""
        return str(self)


__all__ = ["Art104TresExclusion"]
