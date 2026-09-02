"""Runtime narrowing predicates for untrusted, unparameterised containers.

A bare ``isinstance(value, dict)`` narrows to an *unparameterised* ``dict``, so
every key and value the caller then touches is ``Unknown`` to a type checker.
That is not a checker quirk to be silenced: the check genuinely proves only
"this is a mapping", and these predicates say the rest -- the entries are
untrusted ``object`` until something validates them.

The predicates exist here rather than beside each caller because the same three
shapes are needed wherever a deserialised payload, a parsed TOML root, or a
third-party return value is walked. Before this module the pattern was copied
into five places under two different names.

``is_str_keyed_mapping`` is deliberately NOT here: the two copies in
``domain/iva`` assert string keys because *their* input came from ``tomllib``,
which is a caller-specific justification rather than a general narrowing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypeGuard

__all__ = [
    "is_object_collection",
    "is_object_dict",
    "is_object_list",
    "is_object_list_or_tuple",
    "is_object_mapping",
    "is_object_set",
    "is_object_set_or_frozenset",
    "is_object_tuple",
    "is_str_keyed_dict",
]


def is_object_dict(value: object) -> TypeGuard[dict[object, object]]:
    """Narrow to a concrete ``dict`` with untrusted key/value entries.

    Distinct from :func:`is_object_mapping` on purpose: a caller that rebuilds a
    ``dict``, or that deliberately admits only the concrete type, must not
    silently start accepting every other mapping.
    """
    return isinstance(value, dict)


def is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """Narrow to any ``Mapping`` with untrusted key/value entries."""
    return isinstance(value, Mapping)


def is_object_list(value: object) -> TypeGuard[list[object]]:
    """Narrow an unparameterised runtime list to untrusted entries."""
    return isinstance(value, list)


def is_object_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    """Narrow an unparameterised runtime tuple to untrusted entries."""
    return isinstance(value, tuple)


def is_object_set(value: object) -> TypeGuard[set[object]]:
    """Narrow an unparameterised runtime set to untrusted entries."""
    return isinstance(value, set)


def is_object_list_or_tuple(value: object) -> TypeGuard[list[object] | tuple[object, ...]]:
    """Narrow to a list or tuple of untrusted entries.

    Deliberately not ``Sequence``: ``str`` is a sequence, and every caller of
    this shape walks elements only after handling text separately.
    """
    return isinstance(value, list | tuple)


def is_object_collection(
    value: object,
) -> TypeGuard[list[object] | tuple[object, ...] | set[object] | frozenset[object]]:
    """Narrow to any of the four unordered-or-ordered element containers.

    Deliberately not ``Iterable``: ``str`` and ``bytes`` are iterable, and every
    caller of this shape has already handled text and raw bytes separately.
    """
    return isinstance(value, list | tuple | set | frozenset)


def is_object_set_or_frozenset(value: object) -> TypeGuard[set[object] | frozenset[object]]:
    """Narrow to either set flavour with untrusted entries."""
    return isinstance(value, set | frozenset)


def is_str_keyed_mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    """Narrow a runtime dict to a string-keyed mapping WITHOUT checking the keys.

    Unlike :func:`is_str_keyed_dict` below, this asserts nothing about the keys
    at runtime. It is sound only where the provenance already guarantees them -
    a table parsed by ``tomllib`` always has string keys - and it is unsound
    anywhere else. Prefer :func:`is_str_keyed_dict` unless the caller can point
    at that guarantee.
    """
    return isinstance(value, dict)


def is_str_keyed_dict(value: object) -> TypeGuard[dict[str, object]]:
    """Narrow to a dict whose keys are all strings, checking the keys.

    Unlike the container guards above this one does real work at runtime, and
    it must: a caller that goes on to index by ``str`` is relying on the key
    type, so asserting it without looking would be a guess dressed as a proof.
    """
    if not is_object_dict(value):
        return False
    return all(isinstance(key, str) for key in value)
