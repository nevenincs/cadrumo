"""Shared Pydantic model helper for scalar alias validation tests."""

from __future__ import annotations

from pydantic import BaseModel


def single_field_model(field_name: str, field_type: object) -> type[BaseModel]:
    """Return a one-field model that validates a real scalar alias type.

    Builds the class directly through :class:`type` (invoking ``BaseModel``'s
    own metaclass, exactly as a plain class-body field declaration would)
    rather than :func:`pydantic.create_model`: ``field_name`` is a dynamic
    runtime string that could collide with any of ``create_model``'s reserved
    dunder keyword parameters (``__config__``, ``__base__``, ...), so no
    static overload of that ``**field_definitions`` splat can be proven safe.
    """
    return type("_Holder", (BaseModel,), {"__annotations__": {field_name: field_type}})
