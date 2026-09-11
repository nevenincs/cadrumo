"""A read-only mapping that frozen models can share across consumers."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Final, NoReturn, Self

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

__all__ = ["FROZEN_MAPPING", "FrozenMapping", "FrozenMappingMarker"]


class FrozenMapping[K, V](Mapping[K, V]):
    """An immutable mapping whose shallow and deep copies are itself."""

    __slots__ = ("_items",)
    _items: MappingProxyType[K, V]

    def __init__(self, items: Mapping[K, V]) -> None:
        """Freeze a private copy so later caller mutation cannot reach this value."""
        object.__setattr__(self, "_items", MappingProxyType(dict(items)))

    def __getitem__(self, key: K) -> V:
        """Return the value stored under ``key``."""
        return self._items[key]

    def __iter__(self) -> Iterator[K]:
        """Iterate keys in insertion order."""
        return iter(self._items)

    def __len__(self) -> int:
        """Return the number of entries."""
        return len(self._items)

    def __repr__(self) -> str:
        """Render the wrapped mapping with an explicit frozen type marker."""
        return f"{type(self).__name__}({dict(self._items)!r})"

    def __setattr__(self, name: str, value: object) -> NoReturn:
        """Refuse rebinding the private storage."""
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __delattr__(self, name: str) -> NoReturn:
        """Refuse removing the private storage."""
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __copy__(self) -> Self:
        """Return this immutable value unchanged."""
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        """Return this deeply immutable value unchanged."""
        return self

    def __reduce__(self) -> tuple[type[Self], tuple[dict[K, V]]]:
        """Rebuild from an ordinary dictionary when pickled."""
        return type(self), (dict(self._items),)


def _serialise_as_dict(value: Mapping[object, object], handler: core_schema.SerializerFunctionWrapHandler) -> object:
    return handler(dict(value))


class FrozenMappingMarker:
    """Pydantic annotation that validates a mapping into a frozen mapping."""

    __slots__ = ()

    def __get_pydantic_core_schema__(self, source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Wrap the declared mapping schema with immutable output storage."""
        mapping_schema = handler(source)
        return core_schema.no_info_after_validator_function(
            FrozenMapping,
            mapping_schema,
            serialization=core_schema.wrap_serializer_function_ser_schema(_serialise_as_dict, schema=mapping_schema),
        )


FROZEN_MAPPING: Final = FrozenMappingMarker()
