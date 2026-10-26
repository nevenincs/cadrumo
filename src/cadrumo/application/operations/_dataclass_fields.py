"""Typed dataclass field lookup at validated dynamic boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import Field, fields, is_dataclass
from functools import cache
from types import MappingProxyType
from typing import Any, ClassVar, Protocol, cast, get_type_hints


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


@cache
def dataclass_type_hints(value: type[object]) -> Mapping[str, object]:
    """Return a dataclass type's resolved annotations, evaluated once per type.

    Resolving postponed annotations compiles and evaluates each one; a public
    mirror walks thousands of instances of the same few types per document.
    """
    if not is_dataclass(value):
        raise TypeError("expected a dataclass type")
    return MappingProxyType(get_type_hints(value))
