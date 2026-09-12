"""Opaque token contract for the registry-owned rental-reduction axis.

The membership, selection semantics, and legal provenance are governed by the
dated facts registry. This module deliberately retains only the transport type
used by profile and binding surfaces; callers must resolve a token through the
typed registry projection before using it as a calculation selector.
"""

from __future__ import annotations

__all__ = ["RentalReductionArt232Tier"]


class RentalReductionArt232Tier(str):
    """Opaque registry-projected rental-reduction token.

    Membership is intentionally absent here. The registry projection validates
    the token against the selected dated catalogue and refuses unknown values;
    this class exists only to preserve the typed transport boundary.
    """

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: object, _handler: object) -> object:
        """Expose the opaque token as a string to Pydantic."""
        from pydantic_core import core_schema

        return core_schema.no_info_after_validator_function(cls, core_schema.str_schema())

    @property
    def value(self) -> str:
        """Return the token for string-oriented serialization."""
        return str(self)
