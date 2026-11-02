"""Heading keys that the committed Modelo form layouts declare.

Layout headings are registry data, so the Python-source locale scanners cannot see
them. This module reads the layout fragments so the locale audit and the layout tests
agree on which heading keys a stray key must be told apart from.
"""

from __future__ import annotations

from functools import cache

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.toml import TomlDecodeError, parse_toml
from cadrumo.domain.calculations.registry.modelo_localization import form_heading_edition_locale_key

from ._registry_scanner import LocaleRegistryEnumerationError

_FORM_LAYOUT_FRAGMENT_GLOB = "modelos/*/revisions/*/form_layouts/*.toml"


def is_form_layout_heading_candidate(key: str) -> bool:
    """Return whether ``key`` has the shape of a form layout heading key."""
    return key.startswith("modelo.") and ".form." in f"{key}."


@cache
def scan_form_layout_heading_keys() -> frozenset[str]:
    """Return every heading key the committed form layouts and the shared column vocabulary declare.

    Layout headings are registry-declared and optional: the runtime falls back
    from the operator's locale to Spanish, then to the design's official
    Spanish heading, then to a technical name. They are therefore neither
    required by key-set parity nor extra to it, but only a key some layout (or
    the shared vocabulary) actually declares is exempt, so a stray or
    misspelled heading key still reads as extra.

    Raises:
        LocaleRegistryEnumerationError: If a committed layout fragment cannot
            be read or parsed.
    """
    from dev.registry.form_layout.column_vocabulary import SHARED_COLUMN_HEADING_KEY_PREFIX, SHARED_COLUMN_KEYS

    root = bundled_path("registry", "aeat").resolve()
    keys = {f"{SHARED_COLUMN_HEADING_KEY_PREFIX}.{member}" for member in SHARED_COLUMN_KEYS}
    for path in sorted(root.glob(_FORM_LAYOUT_FRAGMENT_GLOB)):
        try:
            document = parse_toml(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, TomlDecodeError) as exc:
            raise LocaleRegistryEnumerationError(
                f"cannot enumerate form layout heading keys from {path}: {type(exc).__name__}: {exc}"
            ) from exc
        declared: set[str] = set()
        _collect_heading_keys(document, declared)
        keys |= declared
        keys |= _edition_heading_keys(declared, modelo_id=path.parts[-5], document=document)
    return frozenset(keys)


def _collect_heading_keys(node: object, keys: set[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "heading_key" and isinstance(value, str) and is_form_layout_heading_candidate(value):
                keys.add(value)
            _collect_heading_keys(value, keys)
    elif isinstance(node, list):
        for value in node:
            _collect_heading_keys(value, keys)


def _edition_heading_keys(declared: set[str], *, modelo_id: str, document: object) -> set[str]:
    """The edition-scoped key each revision a fragment declares gives the heading keys it names."""
    revisions = document.get("revisions") if isinstance(document, dict) else None
    if not isinstance(revisions, dict):
        return set()
    editions = (
        form_heading_edition_locale_key(modelo_id, str(revision_id), key)
        for revision_id in revisions
        for key in declared
    )
    return {edition for edition in editions if edition is not None}
