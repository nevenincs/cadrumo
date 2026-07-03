"""Shared Pydantic model helper for scalar alias validation tests."""

from __future__ import annotations

from pydantic import BaseModel, create_model


def single_field_model(field_name: str, field_type: object) -> type[BaseModel]:
    """Return a one-field model that validates a real scalar alias type."""
    return create_model("_Holder", **{field_name: (field_type, ...)})
