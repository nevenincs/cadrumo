"""Canonical generic factories admitted by API alias analysis."""

from __future__ import annotations

_TYPE_ALIAS_FACTORIES = frozenset(
    {
        "Annotated",
        "AsyncIterator",
        "Awaitable",
        "Callable",
        "Collection",
        "Iterable",
        "Iterator",
        "Literal",
        "Mapping",
        "MutableMapping",
        "NewType",
        "Protocol",
        "Sequence",
        "TypeAliasType",
    }
)

TYPE_ALIAS_FACTORY_MODULES: dict[str, frozenset[str]] = {
    "typing": _TYPE_ALIAS_FACTORIES,
    "typing_extensions": _TYPE_ALIAS_FACTORIES,
    "collections.abc": frozenset(
        {
            "AsyncIterator",
            "Awaitable",
            "Callable",
            "Collection",
            "Iterable",
            "Iterator",
            "Mapping",
            "MutableMapping",
            "Sequence",
        }
    ),
}

TYPE_ALIAS_CALL_FACTORIES: dict[str, frozenset[str]] = {
    "typing": frozenset({"NewType", "TypeAliasType"}),
    "typing_extensions": frozenset({"NewType", "TypeAliasType"}),
}

BUILTIN_GENERIC_FACTORIES = frozenset({"dict", "frozenset", "list", "set", "tuple", "type"})

BUILTIN_TYPE_EXPRESSIONS = frozenset(
    {
        "bool",
        "bytearray",
        "bytes",
        "complex",
        "dict",
        "float",
        "frozenset",
        "int",
        "list",
        "memoryview",
        "object",
        "set",
        "str",
        "tuple",
        "type",
    }
)
