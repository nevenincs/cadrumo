"""Hash a frozen record's content identity once per instance."""

from __future__ import annotations

from typing import Any, Self, override

from pydantic import BaseModel


class CachedIdentityModel(BaseModel):
    """A frozen record whose ``cached_property`` identities do not survive a copy.

    Validation fixes the fields, so an identity computed once stays true of that
    instance.  ``model_copy(update=...)`` changes fields on a copy of the instance
    dictionary, which also holds the cached values, so each copy forgets them.
    """

    @override
    def __copy__(self) -> Self:
        """Return a shallow copy holding no cached identity."""
        return self._without_cached_identity(super().__copy__())

    @override
    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> Self:
        """Return a deep copy holding no cached identity."""
        return self._without_cached_identity(super().__deepcopy__(memo))

    @classmethod
    def _without_cached_identity(cls, copied: Self) -> Self:
        for name in tuple(copied.__dict__):
            if name not in cls.model_fields:
                del vars(copied)[name]
        return copied


__all__ = ["CachedIdentityModel"]
