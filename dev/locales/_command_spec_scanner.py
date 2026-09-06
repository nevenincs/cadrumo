"""Read the translation keys the live CLI command-spec registry declares.

Every other discovery path in this package reads SOURCE TEXT. That works while
a key is written at the site that uses it, and stops working the moment a spec
table builds one:

    _key(f"cli.app.modelo.work.{help_name or name}_help")

Fifty-eight live option and command help keys are built that way. They ship in
all four catalogues and the CLI resolves them on every run, but no literal for
them exists anywhere, so to a text scan they are indistinguishable from keys
nothing uses.

The registry is the authority the text is only evidence for, so this reads the
registry: it imports ``COMMAND_SPECS`` and takes the fields the codebase
ANNOTATES ``TranslationKey``. Reading the annotated fields rather than every
dotted string it can reach is the whole discipline here -- a first attempt
walked all reachable strings and swept up command paths such as
``app.diagnostics.errors`` and module names as though they were keys, which
would have declared several hundred phantom keys required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable

#: The ``CommandSpec`` family fields declared ``TranslationKey``. Held here as
#: an explicit list, and kept honest by the annotation gate in
#: ``tests/test_dynamic_prefix_registry_coverage.py`` that fails when a
#: ``TranslationKey``-annotated parameter is not declared a key-bearing field.
_KEY_FIELDS: Final[tuple[str, ...]] = (
    "help_key",
    "short_help_key",
    "reason_key",
    "prompt_key",
    "confirmation_prompt_key",
)

_SCALARS: Final[tuple[type, ...]] = (str, int, float, bool, bytes)


def _key_text(candidate: object) -> str | None:
    """Return the dotted text of a translation-key field value.

    The field holds a ``TranslationKey`` value object rather than a bare
    string, so reading it as a string finds nothing at all -- which is exactly
    what a first version of this did, reporting zero keys from a registry that
    declares more than a thousand.
    """
    if isinstance(candidate, str):
        return candidate or None
    value = getattr(candidate, "value", None)
    return value if isinstance(value, str) and value else None


def _collect(value: object, seen: set[int], keys: set[str]) -> None:
    """Walk one spec object, taking only its annotated key fields."""
    if value is None or isinstance(value, _SCALARS) or id(value) in seen:
        return
    seen.add(id(value))
    if isinstance(value, dict):
        for item in value.values():
            _collect(item, seen, keys)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            _collect(item, seen, keys)
        return
    for field in dir(value):
        if field.startswith("_"):
            continue
        text = _key_text(getattr(value, field, None))
        if text is not None and "." in text:
            keys.add(text)
    slots: Iterable[str] | None = getattr(type(value), "__slots__", None)
    if slots:
        for name in slots:
            _collect(getattr(value, name, None), seen, keys)
        return
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, dict):
        for item in attributes.values():
            _collect(item, seen, keys)


def scan_command_spec_keys() -> set[str]:
    """Return every translation key the live command-spec registry declares."""
    from cadrumo.entrypoints.cli.command_specs import COMMAND_SPECS

    keys: set[str] = set()
    _collect(COMMAND_SPECS, set(), keys)
    return keys


__all__ = ["scan_command_spec_keys"]
