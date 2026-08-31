"""Canonical reader for the shipped locale catalogues, for catalogue audits.

A gate that asserts something about the SHIPPED translation data has to locate
that data, and the layout is not obvious: the catalogues are sharded per
language, and which shard owns a key is a routing rule rather than a naming
convention. Every gate that restated the layout for itself acquired the same
silent failure mode when the monolithic ``locales/<lang>.yml`` files were
retired -- it stopped reading any catalogue at all, and a gate that reads
nothing asserts nothing while still reporting green.

So the layout is stated once, here, on top of the renderer's own
:func:`~core.i18n.route_key_to_shard`. A future relayout changes the router and
every audit follows; it cannot leave one gate reading a path that no longer
exists.

This is audit machinery for tests. Runtime translation goes through
:func:`~core.i18n.tr`, which resolves a single key through the lazy catalogue
rather than loading a whole shard.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from pydantic import TypeAdapter

from ..core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ..core.i18n._routing import route_key_to_shard

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

__all__ = [
    "CATALOGUE_LANGUAGES",
    "catalogue_shard_path",
    "flatten_catalogue",
    "shard_keys",
    "shard_payload",
]

#: The languages every catalogue audit must cover, drawn from the runtime's own
#: supported set rather than re-listed, so a new language cannot be audited by
#: three gates and missed by a fourth.
CATALOGUE_LANGUAGES: tuple[str, ...] = tuple(str(language) for language in SUPPORTED_OUTPUT_LANGUAGES)

_STR_KEYED_MAPPING_ADAPTER: TypeAdapter[dict[str, object]] = TypeAdapter(dict[str, object])


def catalogue_shard_path(language: str, dotted_key: str) -> Path:
    """Return the shard file owning ``dotted_key`` in ``language``.

    Resolved through the ``cadrumo`` package the way the renderer does rather
    than through ``cadrumo.locales``: the catalogue directory carries data
    only, so it is a namespace package whose ``files()`` result does not
    survive a round trip through ``str()``.
    """
    root = Path(str(importlib.resources.files("cadrumo").joinpath("locales")))
    return root / language / route_key_to_shard(dotted_key)


def shard_payload(language: str, dotted_key: str) -> Mapping[str, object]:
    """Return the parsed shard owning ``dotted_key`` in ``language``."""
    text = catalogue_shard_path(language, dotted_key).read_text(encoding="utf-8")
    raw_payload = yaml.safe_load(text)
    if not isinstance(raw_payload, dict):
        raise TypeError(f"locale shard for {language!r}/{dotted_key!r} is not a mapping")
    payload = _STR_KEYED_MAPPING_ADAPTER.validate_python(raw_payload)
    # A shard may or may not be wrapped in its language code depending on how it
    # was authored; unwrap the wrapper when it is the sole top-level key.
    inner = payload.get(language)
    if isinstance(inner, dict) and set(payload) == {language}:
        return _STR_KEYED_MAPPING_ADAPTER.validate_python(inner)
    return payload


def flatten_catalogue(node: object, prefix: str = "") -> Iterator[tuple[str, object]]:
    """Yield ``(dotted_key, value)`` for every leaf beneath ``node``."""
    if not isinstance(node, dict):
        yield prefix, node
        return
    for key, value in node.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        yield from flatten_catalogue(value, dotted)


def shard_keys(language: str, dotted_key: str) -> frozenset[str]:
    """Return every dotted key declared by the shard owning ``dotted_key``."""
    return frozenset(key for key, _ in flatten_catalogue(shard_payload(language, dotted_key)))
