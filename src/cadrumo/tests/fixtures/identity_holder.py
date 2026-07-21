"""Shared Pydantic model helper for scalar alias validation tests."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(frozen=True)
class SingleFieldHolder:
    """A one-field model plus construction and read-back over its dynamic field.

    ``field_name`` is a runtime string, so the generated class exposes neither a
    constructor keyword nor an attribute a type checker can see. Routing both
    construction and read-back through this holder keeps the dynamic name in one
    place instead of leaking an unprovable keyword to every call site.
    """

    field_name: str
    model: type[BaseModel]

    def build(self, value: object) -> BaseModel:
        """Validate ``value`` through the real alias type, as pydantic would."""
        return self.model(**{self.field_name: value})

    def value_of(self, holder: BaseModel) -> object:
        """Read the dynamically-declared field back off a built instance."""
        return getattr(holder, self.field_name)


def single_field_holder(field_name: str, field_type: object) -> SingleFieldHolder:
    """Return a holder over a one-field model that validates a real scalar alias.

    Builds the class directly through :class:`type` (invoking ``BaseModel``'s
    own metaclass, exactly as a plain class-body field declaration would)
    rather than :func:`pydantic.create_model`: ``field_name`` is a dynamic
    runtime string that could collide with any of ``create_model``'s reserved
    dunder keyword parameters (``__config__``, ``__base__``, ...), so no
    static overload of that ``**field_definitions`` splat can be proven safe.
    """
    model = type("_Holder", (BaseModel,), {"__annotations__": {field_name: field_type}})
    return SingleFieldHolder(field_name=field_name, model=model)
