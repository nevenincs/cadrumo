"""A read-only mapping that frozen models can share across consumers.

A frozen pydantic model refuses attribute assignment, but a ``Mapping`` field
still validates to a plain ``dict`` that any holder can mutate in place. That
single hole is what forces a model graph to be rebuilt per consumer.
:data:`FROZEN_MAPPING` closes it at the defining field: annotate
``Annotated[Mapping[K, V], FROZEN_MAPPING]`` and the validated value is a
:class:`FrozenMapping`, while construction still accepts any mapping and
serialisation still emits the same JSON object the ``dict`` did.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Final, NoReturn, Self, override

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

__all__ = ["FROZEN_MAPPING", "FrozenMapping", "FrozenMappingMarker"]


class FrozenMapping[K, V](Mapping[K, V]):
    """An immutable mapping whose copy, shallow or deep, is itself.

    Sharing by copy is correct only because nothing reachable through the
    mapping can change: it has no mutating methods, its storage is a read-only
    proxy, and :data:`FROZEN_MAPPING` is applied only to fields whose values are
    themselves frozen. A deep copy of a model holding one therefore shares the
    mapping instead of failing on it, which a bare ``MappingProxyType`` does.
    """

    __slots__ = ("_items",)

    _items: MappingProxyType[K, V]

    def __init__(self, items: Mapping[K, V]) -> None:
        """Freeze a private copy, so the caller's mapping stays theirs to change."""
        object.__setattr__(self, "_items", MappingProxyType(dict(items)))

    @override
    def __getitem__(self, key: K) -> V:
        """Return the value stored under ``key``."""
        return self._items[key]

    @override
    def __iter__(self) -> Iterator[K]:
        """Iterate keys in insertion order."""
        return iter(self._items)

    @override
    def __len__(self) -> int:
        """Return the number of entries."""
        return len(self._items)

    @override
    def __repr__(self) -> str:
        """Render like the ``dict`` it replaces, marked as frozen."""
        return f"{type(self).__name__}({dict(self._items)!r})"

    @override
    def __setattr__(self, name: str, value: object) -> NoReturn:
        """Refuse rebinding the storage after construction."""
        raise AttributeError(f"{type(self).__name__} is immutable")

    @override
    def __delattr__(self, name: str) -> NoReturn:
        """Refuse removing the storage after construction."""
        raise AttributeError(f"{type(self).__name__} is immutable")

    def __copy__(self) -> Self:
        """Return this mapping: an immutable value needs no copy."""
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> Self:
        """Return this mapping: its entries are immutable, so sharing them is safe."""
        return self

    @override
    def __reduce__(self) -> tuple[type[Self], tuple[dict[K, V]]]:
        """Pickle as the constructor applied to an ordinary ``dict``."""
        return type(self), (dict(self._items),)


def _serialise_as_dict(value: Mapping[object, object], handler: core_schema.SerializerFunctionWrapHandler) -> object:
    """Hand the declared mapping serializer, with its include/exclude state, the ``dict`` it was written for."""
    return handler(dict(value))


class FrozenMappingMarker:
    """Pydantic annotation that validates a mapping field into a :class:`FrozenMapping`."""

    __slots__ = ()

    def __get_pydantic_core_schema__(self, source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
        """Wrap the field's own mapping schema; validation and JSON shape are unchanged."""
        mapping_schema = handler(source)
        return core_schema.no_info_after_validator_function(
            FrozenMapping,
            mapping_schema,
            serialization=core_schema.wrap_serializer_function_ser_schema(_serialise_as_dict, schema=mapping_schema),
        )


FROZEN_MAPPING: Final = FrozenMappingMarker()
