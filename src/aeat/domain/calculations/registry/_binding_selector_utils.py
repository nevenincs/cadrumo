"""Shared selector normalization helpers for registry bindings."""

from __future__ import annotations

from pydantic import BaseModel

from ._schema import DataBindingDefinition

__all__ = ["selector_as_dict"]


def selector_as_dict(binding: DataBindingDefinition) -> dict[str, object]:
    """Return a plain selector mapping without injected source metadata."""
    selector = binding.selector
    if isinstance(selector, BaseModel):
        return selector.model_dump(exclude={"source"}, exclude_none=True)
    return {key: value for key, value in selector.items() if key != "source"}
