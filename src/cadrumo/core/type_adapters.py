"""The two shape adapters this codebase narrows loosely-typed values with.

Both shapes answer the same question at a boundary: a value arrived as
``object`` -- decoded JSON, a parsed TOML fragment, a pydantic ``info.data``
bag, an error location -- and the code about to read it needs it to be a
string-keyed mapping, or a sequence, before it can index or iterate. A
:class:`pydantic.TypeAdapter` is the narrowing that answers, because it refuses
rather than degrading: a value of the wrong shape raises where an ``isinstance``
check would silently fall through to a default.

Neither shape carries any domain meaning, which is exactly why they were
redeclared. There is nothing to disagree about in ``dict[str, object]``, so
every module that needed one simply built one, under whichever private name fit
its local vocabulary -- selector metadata here, a translation context there, a
JSON object somewhere else. Nothing was ever wrong, and that is the point: the
cost was not a defect but a schema compiled once per declaring module, and a
reader who cannot tell from the name that eleven other modules mean the same
thing.

The adapters are stateless and safe to share; pydantic builds each validator
once and reuses it, which is the behaviour the per-module copies were each
paying for separately.

See Also:
    :func:`~core._toml.to_str_keyed_dict`
        The narrower TOML-specific bridge, which re-raises through a
        caller-supplied error factory instead of a
        :exc:`~pydantic.ValidationError`.
"""

from __future__ import annotations

from pydantic import TypeAdapter

STR_KEYED_MAPPING_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])
"""Narrow a value to a string-keyed mapping of unconstrained values."""

OBJECT_TUPLE_ADAPTER: TypeAdapter[tuple[object, ...]] = TypeAdapter(tuple[object, ...])
"""Narrow a value to a tuple of unconstrained entries."""

__all__ = [
    "OBJECT_TUPLE_ADAPTER",
    "STR_KEYED_MAPPING_ADAPTER",
]
