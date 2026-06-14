"""Shared selector normalization and field-validator helpers for registry bindings."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from ._errors import RegistryValidationError
from ._schema import DataBindingDefinition

__all__ = ["selector_as_dict", "unique_tuple", "uppercase_alpha_code"]


def selector_as_dict(binding: DataBindingDefinition) -> dict[str, object]:
    """Return a plain selector mapping without injected source metadata."""
    selector = binding.selector
    if isinstance(selector, BaseModel):
        return selector.model_dump(exclude={"source"}, exclude_none=True)
    return {key: value for key, value in selector.items() if key != "source"}


def uppercase_alpha_code(field_label: str) -> Callable[[type, str], str]:
    """Build a field validator that rejects a non-uppercase-alphabetic code.

    Shared by the binding observation models whose ISO country / member-state /
    currency codes must be uppercase alphabetic; ``field_label`` names the field
    in the raised :class:`RegistryValidationError`.
    """

    def _validate(cls: type, value: str) -> str:
        if value != value.upper() or not value.isalpha():
            raise RegistryValidationError(f"{field_label} must be uppercase alphabetic")
        return value

    return _validate


def unique_tuple(label: str) -> Callable[[type, tuple[str, ...]], tuple[str, ...]]:
    """Build a field validator that rejects duplicate entries in a tuple field.

    Shared by the binding requirement models; ``label`` names the offending
    tuple in the raised :class:`RegistryValidationError` (``"<label> entries
    must be unique"``).
    """

    def _validate(cls: type, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError(f"{label} entries must be unique")
        return value

    return _validate
