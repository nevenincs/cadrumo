"""Typed dataclass field lookup at validated dynamic boundaries."""

from __future__ import annotations

from dataclasses import Field, fields, is_dataclass
from typing import Any, ClassVar, Protocol, cast


class _DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Field[Any]]]


def dataclass_instance_fields(value: object) -> tuple[Field[Any], ...]:
    """Return fields after confirming a dynamic value is a dataclass instance."""
    if not is_dataclass(value) or isinstance(value, type):
        raise TypeError("expected a dataclass instance")
    return fields(cast(_DataclassInstance, value))


def dataclass_type_fields(value: type[object]) -> tuple[Field[Any], ...]:
    """Return fields after confirming a dynamic class is a dataclass type."""
    if not is_dataclass(value):
        raise TypeError("expected a dataclass type")
    return fields(value)
