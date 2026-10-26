"""Nested catalogue leaf validation, resolution, and in-memory edits."""

from collections.abc import Mapping, Sequence

from cadrumo.core.product_identity import normalise_product_identity_references

from .errors import LocaleError
from .locale_nodes import _MISSING_LOCALE_LEAF, _MODELO_SCHEMA_PREFIX, LocaleNode, _MissingLocaleLeaf


def _apply_mapping_edits(
    data: dict[str, LocaleNode],
    edits: Mapping[str, str | None],
    removals: Sequence[str],
) -> None:
    """Set every edit and delete every removal inside one parsed catalogue mapping."""
    for dotted_key, value in sorted(edits.items()):
        _set_nested_leaf(data, dotted_key, value)
    for dotted_key in sorted(removals):
        parts = dotted_key.split(".")
        cursor: LocaleNode = data
        for part in parts:
            if not isinstance(cursor, dict) or part not in cursor:
                break
            cursor = cursor[part]
        else:
            if not isinstance(cursor, dict):
                parent = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
                del parent[parts[-1]]
                _prune_empty_namespaces(data, parts[:-1])


def _collect_required_leaves(
    keys: set[str],
    existing_data: dict[str, LocaleNode],
) -> dict[str, LocaleNode]:
    """Resolve each dotted ``key`` against ``existing_data`` to its leaf value.

    Returns a flat ``{dotted_key: value}`` map holding only keys that have a
    value. A key that resolves to a non-dict leaf carries its existing
    translation; a MISSING key -- absent, or bottoming out at an interior node
    -- is handled by what the catalogues actually accept for "no translation
    yet", which is not one answer:

    * A Modelo-schema key carries ``None``. That is the representation
      :meth:`LocaleManager.set_locale_values` already reserves for exactly
      these keys: it holds inter-locale key parity without fabricating text,
      and the Modelo resolver then applies its documented Spanish-source
      fallback.
    * Any other key is OMITTED. The parity check reports it as missing, which
      is an honest statement that the author still owes four values, and
      ``set`` creates it with the first real one.

    **Neither writes the key's own dotted path as its value, and that is the
    whole change.** Doing so was described here as the scaffold convention for
    "no translation yet", but no consumer in the tree accepts it: the
    translation-honesty ratchet refuses a key-echo outright, and three separate
    coverage gates fail on one. A convention nothing reads is not a convention,
    and this was its only producer -- so every echo the catalogues carried was
    written here and forbidden everywhere else.

    The failure directions are not symmetric, which is why omission is right
    rather than merely tidier. An omitted key costs the authoring lane a
    missing-key report it can clear with the values only it knows. An echoed
    key costs EVERY lane a red honesty gate it did not cause, cannot clear
    without those same values, and meets while working on something else.
    """
    resolved: dict[str, LocaleNode] = {}
    for key in keys:
        leaf = _resolve_leaf(existing_data, key.split("."))
        if leaf is not _MISSING_LOCALE_LEAF:
            resolved[key] = leaf
        elif key.startswith(_MODELO_SCHEMA_PREFIX):
            resolved[key] = None
    return resolved


def _resolve_leaf(existing_data: dict[str, LocaleNode], parts: list[str]) -> LocaleNode | _MissingLocaleLeaf:
    """Walk ``parts`` and distinguish an authored null from a missing leaf."""
    curr: LocaleNode = existing_data
    for part in parts:
        if not isinstance(curr, dict) or part not in curr:
            return _MISSING_LOCALE_LEAF
        curr = curr[part]
    return _MISSING_LOCALE_LEAF if isinstance(curr, dict) else curr


def _prune_empty_namespaces(root: dict[str, LocaleNode], parts: list[str]) -> None:
    """Delete namespaces left empty by a removal, innermost first.

    Walks the parsed mapping rather than the file's lines, so a namespace whose
    key YAML quotes is pruned like any other. Stops at the first ancestor that
    still holds something: an empty parent is a namespace nothing addresses,
    while a populated one is still in use by its remaining children.
    """
    for depth in range(len(parts), 0, -1):
        cursor: LocaleNode = root
        for part in parts[: depth - 1]:
            if not isinstance(cursor, dict):
                return
            cursor = cursor.get(part)
        if not isinstance(cursor, dict):
            return
        child = cursor.get(parts[depth - 1])
        if not isinstance(child, dict) or child:
            return
        del cursor[parts[depth - 1]]


def _set_nested_leaf(root: dict[str, LocaleNode], dotted_key: str, value: LocaleNode) -> None:
    """Write ``value`` at ``dotted_key`` inside ``root``, creating sub-dicts as needed."""
    parts = dotted_key.split(".")
    curr: dict[str, LocaleNode] = root
    for part in parts[:-1]:
        child = curr.get(part)
        if not isinstance(child, dict):
            child: dict[str, LocaleNode] = {}
            curr[part] = child
        curr = child
    curr[parts[-1]] = value


def _resolve_leaf_parent(
    data: dict[str, LocaleNode],
    parts: list[str],
    *,
    dotted_key: str,
) -> dict[str, LocaleNode]:
    """Walk to the mapping that owns ``parts[-1]``, refusing every wrong shape.

    Each refusal names what the path actually resolved to, so an operator who
    addressed a namespace or a leaf's child is told which of those happened.

    **A namespace that does not exist yet is CREATED rather than refused**, and
    the batch writer beside this one has always done so through
    :func:`_set_nested_leaf`; the two disagreed about the same operation. The
    refusal here said "run locale scaffold first", which was only ever true
    because the scaffold answered it by writing the key's own dotted path as a
    placeholder -- a value the honesty ratchet and three coverage gates all
    refuse. So the one route to a new key ran through a value nothing accepts.
    Creating the namespace is what lets the scaffold stop fabricating: an author
    adds a ``tr()`` call and supplies the four values directly, and no
    unvalued key exists at any point.

    The shape refusals below are unchanged. Addressing a namespace as a leaf, or
    a leaf's child, is still a mistake about the catalogue rather than a key
    that does not exist yet.
    """
    cursor: LocaleNode = data
    for part in parts[:-1]:
        if isinstance(cursor, dict) and part not in cursor:
            cursor[part] = {}
        if not isinstance(cursor, dict):
            raise LocaleError(f"Cannot set {dotted_key!r}: parent path resolves to a leaf")
        cursor = cursor[part]
    if not isinstance(cursor, dict):
        raise LocaleError(f"Cannot set {dotted_key!r}: parent path resolves to a leaf")
    if isinstance(cursor.get(parts[-1]), dict):
        raise LocaleError(f"Cannot set {dotted_key!r}: it resolves to a namespace")
    return cursor


def _normalise_product_identity_node(value: LocaleNode) -> LocaleNode:
    """Recursively normalize stale human-command references."""
    if isinstance(value, dict):
        return _normalise_product_identity_mapping(value)
    if isinstance(value, str):
        return normalise_product_identity_references(value)
    return value


def _normalise_product_identity_mapping(value: dict[str, LocaleNode]) -> dict[str, LocaleNode]:
    """Normalize a locale mapping while preserving its mapping type."""
    return {key: _normalise_product_identity_node(child) for key, child in value.items()}


def _flatten_leaf_values(mapping: dict[str, LocaleNode], prefix: str = "") -> dict[str, str | None]:
    """Return leaf locale values keyed by dotted path."""
    flattened: dict[str, str | None] = {}
    for key, value in mapping.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_leaf_values(value, path))
        else:
            flattened[path] = value
    return flattened


def _flatten_raw_locale_leaves(value: object, prefix: str = "") -> dict[str, object]:
    """Flatten parsed YAML without coercing invalid scalar types to strings."""
    if isinstance(value, dict):
        flattened: dict[str, object] = {}
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_raw_locale_leaves(child, path))
        return flattened
    return {prefix or "<root>": value}


def _set_locale_mapping_value(data: dict[str, LocaleNode], dotted_key: str, raw_value: str | None) -> None:
    """Set locale mapping value."""
    parts = dotted_key.split(".")
    if not dotted_key or any(not part for part in parts):
        raise LocaleError(f"Invalid locale key: {dotted_key!r}")
    if raw_value is None:
        if not dotted_key.startswith("modelo.schema."):
            raise LocaleError(f"Only Modelo schema keys may carry an absent locale value: {dotted_key!r}")
        value: LocaleNode = None
    else:
        if not raw_value.strip():
            raise LocaleError(f"Cannot set {dotted_key!r}: a locale value must not be blank")
        value = normalise_product_identity_references(raw_value)
    _set_nested_leaf(data, dotted_key, value)


def _remove_existing_locale_leaf(data: dict[str, LocaleNode], parts: list[str], dotted_key: str) -> None:
    """Remove existing locale leaf."""
    cursor: LocaleNode = data
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            raise LocaleError(f"Locale key not found: {dotted_key!r}")
        cursor = cursor[part]
    if isinstance(cursor, dict):
        raise LocaleError(f"Cannot remove {dotted_key!r}: it resolves to a namespace")

    parent = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
    del parent[parts[-1]]
    _prune_empty_namespaces(data, parts[:-1])


def _remove_optional_locale_leaf(data: dict[str, LocaleNode], dotted_key: str) -> None:
    """Remove optional locale leaf."""
    parts = dotted_key.split(".")
    cursor: LocaleNode = data
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            break
        cursor = cursor[part]
    else:
        if not isinstance(cursor, dict):
            parent = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
            del parent[parts[-1]]
            _prune_empty_namespaces(data, parts[:-1])


def _remove_required_locale_leaf(data: dict[str, LocaleNode], dotted_key: str) -> None:
    """Remove required locale leaf."""
    parts = dotted_key.split(".")
    if not dotted_key or any(not part for part in parts):
        raise LocaleError(f"Invalid locale key: {dotted_key!r}")
    cursor: LocaleNode = data
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            raise LocaleError(f"Locale key not found: {dotted_key!r}")
        cursor = cursor[part]
    if isinstance(cursor, dict):
        raise LocaleError(f"Cannot remove {dotted_key!r}: it resolves to a namespace")

    parent = _resolve_leaf_parent(data, parts, dotted_key=dotted_key)
    del parent[parts[-1]]
    _prune_empty_namespaces(data, parts[:-1])
