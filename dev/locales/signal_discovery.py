"""Discovery for the authoritative locale audit."""

from __future__ import annotations

from collections.abc import Iterable

from .locale_tree import _flatten_raw_locale_leaves
from .locale_yaml import discover_locale_codes, locale_catalogue_source
from .manager import LocaleManager
from .signal_syntax import DOTTED_KEY_RE


def signal_catalogue_only_findings(
    catalogue_only_keys: set[str], locale_leaves: dict[str, dict[str, object]]
) -> list[dict[str, object]]:
    """Signal catalogue only findings."""
    catalogue_only_findings: list[dict[str, object]] = [
        {
            "classification": "blocking",
            "kind": "catalogue_only_key",
            "domain": signal_key_domain(key),
            "key": key,
            "locales": sorted(locale for locale, leaves in locale_leaves.items() if key in leaves),
            "cells": sum(1 for leaves in locale_leaves.values() if key in leaves),
            "next_action": "remove the stale key through locales-remove-batch",
        }
        for key in sorted(catalogue_only_keys)
    ]
    return catalogue_only_findings


def discover_signal_catalogues(
    manager: LocaleManager,
) -> tuple[
    set[str],
    list[dict[str, object]],
    list[str],
    dict[str, tuple[str, ...]],
    tuple[str, ...],
    dict[str, dict[str, object]],
    list[dict[str, object]],
]:
    """Discover signal catalogues."""
    discovery_findings: list[dict[str, object]] = []
    try:
        required_keys = set(manager.get_codebase_keys())
    except Exception as exc:  # This is an intentional audit boundary.
        required_keys = set()
        discovery_findings.append(
            {
                "classification": "blocking",
                "kind": "key_discovery_failure",
                "error_type": type(exc).__name__,
                "detail": str(exc),
                "next_action": "restore authoritative key discovery, then rerun check-locales",
            }
        )
    namespace_markers = sorted(manager.get_codebase_namespaces())
    finite_families, unresolved_families = dynamic_key_families(namespace_markers)
    locale_leaves, catalogue_findings = catalogue_leaves(manager)
    if discovery_findings:
        required_keys.update(key for leaves in locale_leaves.values() for key in leaves)
    return (
        required_keys,
        discovery_findings,
        namespace_markers,
        finite_families,
        unresolved_families,
        locale_leaves,
        catalogue_findings,
    )


def include_signal_namespace_keys(
    required_keys: set[str],
    namespace_markers: list[str],
    finite_families: dict[str, tuple[str, ...]],
    locale_leaves: dict[str, dict[str, object]],
) -> None:
    """Include signal namespace keys."""
    namespace_prefixes = tuple(marker.rstrip("*").rstrip(".") for marker in namespace_markers)
    required_keys.update(key for values in finite_families.values() for key in values)
    required_keys.update(
        key for leaves in locale_leaves.values() for key in leaves if covered_by_namespace(key, namespace_prefixes)
    )


def signal_catalogue_coverage(
    locale_leaves: dict[str, dict[str, object]], required_keys: set[str]
) -> tuple[int, int, set[str], list[dict[str, object]]]:
    """Signal catalogue coverage."""
    catalogue_key_cells = sum(len(leaves) for leaves in locale_leaves.values())
    catalogue_keys_unique = len({key for leaves in locale_leaves.values() for key in leaves})
    catalogue_only_keys = {key for leaves in locale_leaves.values() for key in leaves if key not in required_keys}
    catalogue_only_findings = signal_catalogue_only_findings(catalogue_only_keys, locale_leaves)
    return catalogue_key_cells, catalogue_keys_unique, catalogue_only_keys, catalogue_only_findings


def dynamic_key_families(
    namespace_markers: Iterable[str],
    *,
    registered_keys: Iterable[str] | None = None,
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    """Partition namespace markers using concrete f-string registry evidence.

    The scanner emits a marker whenever it cannot enumerate a dynamic key.  A
    marker is finite when the f-string registry supplies at least one concrete
    key below its prefix; only markers without that evidence remain unresolved.
    ``registered_keys`` is injectable so this boundary can be tested without
    importing the full runtime registry.
    """
    markers = tuple(sorted(set(namespace_markers)))
    if registered_keys is None:
        from .fstring_registry import get_registered_keys

        registered_keys = get_registered_keys()
    concrete_keys = tuple(sorted(set(registered_keys)))
    finite: dict[str, tuple[str, ...]] = {}
    unresolved: list[str] = []
    for marker in markers:
        prefix = marker.rstrip("*").rstrip(".")
        values = tuple(key for key in concrete_keys if covered_by_namespace(key, (prefix,)))
        if values:
            finite[marker] = values
        else:
            unresolved.append(marker)
    return finite, tuple(unresolved)


def catalogue_leaves(
    manager: LocaleManager,
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    """Read every discovered catalogue and report non-text translation leaves."""
    leaves_by_locale: dict[str, dict[str, object]] = {}
    findings: list[dict[str, object]] = []
    for locale in sorted(discover_locale_codes(manager.locales_dir)):
        source = locale_catalogue_source(manager.locales_dir, locale)
        if source is None:
            continue
        leaves = _flatten_raw_locale_leaves(manager.load_locale(source))
        leaves_by_locale[locale] = leaves
        for key, value in sorted(leaves.items()):
            if not isinstance(value, str):
                findings.append(
                    {
                        "classification": "blocking",
                        "kind": "non_string_translation",
                        "key": key,
                        "locale": locale,
                        "value_type": type(value).__name__,
                        "next_action": "set_translation",
                    }
                )
    return leaves_by_locale, findings


def signal_key_domain(key: str) -> str:
    """Return the canonical dotted-key domain or the unassigned inventory domain."""
    return key.split(".", 1)[0] if DOTTED_KEY_RE.fullmatch(key) else "unassigned"


def covered_by_namespace(key: str, prefixes: tuple[str, ...]) -> bool:
    """Return whether a concrete key falls under a declared namespace prefix."""
    return any(f".{prefix}." in f".{key}." for prefix in prefixes if prefix)
