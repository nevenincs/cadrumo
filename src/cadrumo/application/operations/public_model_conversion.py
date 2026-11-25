"""Recursive conversion between domain models and ordinary public scalars.

Operation request schemas must not embed domain models with custom scalar
validators.  Public DTOs therefore carry plain JSON scalars and
:class:`PublicDecimal` wrappers; these helpers copy a domain graph into that
shape and restore the domain-validated shape before any service runs.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel

from ...core.type_guards import is_object_tuple
from .public_scalar import PublicDecimal


def public_value(value: object) -> object:
    """Copy a domain value into ordinary public scalars and nested mappings."""
    if isinstance(value, Decimal):
        return PublicDecimal(decimal=str(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {name: public_value(getattr(value, name)) for name in type(value).model_fields}
    if is_object_tuple(value):
        return tuple(public_value(item) for item in value)
    return value


def domain_value(value: object) -> object:
    """Restore public decimal wrappers and enum values for domain validation."""
    if isinstance(value, PublicDecimal):
        return Decimal(value.decimal)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return {name: domain_value(getattr(value, name)) for name in type(value).model_fields}
    if is_object_tuple(value):
        return tuple(domain_value(item) for item in value)
    return value


def public_model_mapping(value: BaseModel) -> dict[str, object]:
    """Return one model's recursively converted public mapping."""
    return {name: public_value(getattr(value, name)) for name in type(value).model_fields}


def domain_model_mapping(value: BaseModel) -> dict[str, object]:
    """Return one public model's recursively restored domain mapping."""
    if isinstance(value, PublicDecimal):
        raise TypeError("domain model conversion did not produce an object")
    return {name: domain_value(getattr(value, name)) for name in type(value).model_fields}
