"""Strict catalogue YAML parsing, source discovery, and guarded serialization."""

from collections.abc import Hashable
from pathlib import Path
from typing import IO, Any, TypeGuard, override

import yaml

from .errors import LocaleError
from .locale_nodes import LocaleNode
from .write_guard import CatalogueWriteGuard


#: libyaml's C scanner. Only scanning and parsing are C-accelerated; the
#: constructor below stays Python and keeps running for every mapping, which is
#: what lets the duplicate-key refusal survive the swap unchanged.
class StrictUniqueKeyLoader(yaml.CSafeLoader):
    """YAML loader that raises an error on duplicate keys.

    The catalogues are ~3 MB each, and parsing one measured 9.016s on the pure
    Python base against 0.865s on the C one -- a 10.4x difference paid by every
    caller that reads a catalogue, of which the test layer has many.

    Both bases were confirmed to produce an EQUAL document for the largest
    shipped catalogue, and to raise ``LocaleError`` with the identical message
    and line number on a planted duplicate key, before the base was swapped. A
    faster parser that quietly stopped refusing duplicates would trade this
    module's whole purpose for speed.
    """

    @override
    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        """Construct a mapping node, raising ``LocaleError`` on duplicate keys.

        Args:
            node: The YAML mapping node to construct.
            deep: Whether to construct values recursively before returning.

        Returns:
            A plain ``dict`` of the mapping's key-value pairs.

        Raises:
            LocaleError: When a duplicate key is found in the mapping node.
        """
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in mapping:
                raise LocaleError(f"Duplicate key '{key}' found at line {key_node.start_mark.line + 1}")
            value = self.construct_object(value_node, deep=deep)
            mapping[key] = value
        return mapping


def _parse_raw_locale(source: IO[str] | str) -> dict[str, object]:
    """Parse catalogue YAML keeping every scalar leaf so the audit can report its type."""
    loader = StrictUniqueKeyLoader(source)
    try:
        data = loader.get_single_data()
    finally:
        loader.dispose()
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise LocaleError("Locale catalogue root must be a mapping of string keys")
    root: dict[str, object] = {}
    for key, value in data.items():
        if not isinstance(key, str):
            raise LocaleError("Locale catalogue root must be a mapping of string keys")
        root[key] = value
    return root


def _parse_locale(source: IO[str] | str) -> dict[str, LocaleNode]:
    """Parse catalogue YAML strictly from an open handle or an in-memory string.

    The string form is what a guarded read produces: the bytes are read and
    fingerprinted once by :class:`CatalogueWriteGuard`, then parsed from memory,
    so the parse cannot see a different file than the one the write is checked
    against.
    """
    loader = StrictUniqueKeyLoader(source)
    try:
        data = loader.get_single_data()
    finally:
        loader.dispose()
    if data is None:
        return {}
    if not _is_locale_mapping(data):
        raise LocaleError("Locale catalogue root must be a mapping of string keys")
    return data


def _is_locale_value(value: object) -> TypeGuard[LocaleNode]:
    """Return whether one parsed YAML value has the recursive locale shape."""
    if value is None or isinstance(value, str):
        return True
    if not isinstance(value, dict):
        return False
    return all(isinstance(key, str) and _is_locale_value(child) for key, child in value.items())


def _is_locale_mapping(value: object) -> TypeGuard[dict[str, LocaleNode]]:
    """Return whether a parsed YAML document is a locale mapping."""
    return isinstance(value, dict) and all(
        isinstance(key, str) and _is_locale_value(child) for key, child in value.items()
    )


def _deep_merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge overlay dictionary into base dictionary in place."""
    for k, v in overlay.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge_dicts(base[k], v)
        else:
            base[k] = v
    return base


def locale_catalogue_source(locales_dir: Path, locale: str) -> Path | None:
    """Return the path :meth:`LocaleManager.load_locale` should read for ``locale``.

    A catalogue ships either as a per-locale shard DIRECTORY or as a single
    flat ``<locale>.yml`` file, and both shapes are live. Every caller that
    wants "the committed catalogue for this locale" must resolve that here
    rather than constructing a path, because a caller that hardcodes one shape
    does not degrade -- it raises :exc:`FileNotFoundError` the moment the tree
    carries the other, and a gate that raises is a gate that has stopped
    checking. Four such call sites went dead exactly that way when the flat
    catalogues were resharded, taking the parity and honesty ratchets with
    them while the suite still reported them as failures rather than as
    silence.

    Returns ``None`` when neither shape is present, so a caller iterating
    discovered locales can skip rather than fabricate a path that cannot be
    read.
    """
    shard_dir = locales_dir / locale
    if shard_dir.is_dir():
        return shard_dir
    flat_file = locales_dir / f"{locale}.yml"
    if flat_file.is_file():
        return flat_file
    return None


def discover_locale_codes(locales_dir: Path) -> set[str]:
    """Return every locale code carried as a shard directory or legacy flat file.

    This is the discovery half of the pair completed by
    :func:`locale_catalogue_source`: discovery answers which catalogues exist,
    resolution answers which path to read for one of them. A caller that wants
    "every committed catalogue" needs both, and must not substitute a glob for
    a single shape. A glob is the more dangerous mistake of the two, because
    the hardcoded-path failure at least raises: a glob for the shape the tree
    does not carry returns an empty result, and an empty result reports as a
    clean pass.
    """
    locales: set[str] = set()
    if not locales_dir.is_dir():
        return locales
    for item in locales_dir.iterdir():
        if item.name.startswith(("_", ".")):
            continue
        if item.is_dir():
            locales.add(item.name)
        elif item.is_file() and item.suffix == ".yml":
            locales.add(item.stem)
    return locales


def _rewrite_locale_mapping(guard: CatalogueWriteGuard, path: Path, data: dict[str, LocaleNode]) -> None:
    """Replace a locale mapping after strict parsing, through the write guard.

    The locale CLI may be interrupted by an operator or orchestration timeout.
    Writing directly to the catalogue would expose a truncated YAML file between
    ``open(..., "w")`` and the final flush, so serialize in memory and persist
    through the guard, which performs the atomic replace and first refuses the
    write if the catalogue moved since this edit read it.
    """
    serialised = yaml.dump(data, allow_unicode=True, sort_keys=True, default_flow_style=False)
    guard.write_text(path, serialised)
