"""Project authored catalogue strings for a native frontend that cannot call ``tr()``.

A frontend's key declaration decides which keys it needs; this module only
reads those keys out of the canonical catalogues and refuses an incomplete or
inconsistent projection. It imports no key declaration, so a consumer that
names a handful of keys (the native manager) does not load the desktop shell's
declarations and what they import.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Final

from cadrumo.core.i18n.render import extract_placeholders

from ._paths import LOCALES_DIR, RUNTIME_SRC_DIR, SRC_DIR
from ._status import CatalogueLeafState, classify_catalogue_leaf
from .errors import LocaleError
from .locale_tree import _flatten_raw_locale_leaves
from .locale_yaml import locale_catalogue_source
from .manager import LocaleManager
from .service_catalogues import SERVICE_LOCALES_DIR

RUNTIME_LOCALES_DIR: Final[Path] = RUNTIME_SRC_DIR / "_data" / "locales"

# The only placeholder form a native frontend substitutes: ``{name}``.
_SHELL_PLACEHOLDER: Final[re.Pattern[str]] = re.compile(r"\{(\w+)\}")


def _verbatim(key: str, value: str) -> str:
    del key
    return value


def _catalogue_leaves(locales_dir: Path, locale: str) -> dict[str, object]:
    """Read one locale's catalogue leaves through the catalogue authority."""
    source = locale_catalogue_source(locales_dir, locale)
    if source is None:
        raise LocaleError(f"No catalogue for desktop locale {locale!r} under {locales_dir}")
    return _flatten_raw_locale_leaves(LocaleManager(SRC_DIR, locales_dir).load_locale(source))


def _shell_placeholders(key: str, locale: str, value: str) -> frozenset[str]:
    """Return the ``{name}`` placeholders of ``value``, refusing any other form."""
    shell = frozenset(str(match.group(1)) for match in _SHELL_PLACEHOLDER.finditer(value))
    if shell != extract_placeholders(value) or "%{" in value:
        raise LocaleError(
            f"{locale}:{key} carries a placeholder the desktop shell cannot substitute; use plain {{name}}"
        )
    return shell


def _project_locale(
    locales_dir: Path,
    locale: str,
    keys: frozenset[str],
    refusals: list[str],
    shell_form: Callable[[str, str], str],
) -> dict[str, str]:
    leaves = _catalogue_leaves(locales_dir, locale)
    if locales_dir == LOCALES_DIR:
        for owner, owned_locales in (("runtime", RUNTIME_LOCALES_DIR), ("service", SERVICE_LOCALES_DIR)):
            if not owned_locales.is_dir():
                continue
            owned_leaves = _catalogue_leaves(owned_locales, locale)
            collisions = leaves.keys() & owned_leaves.keys()
            if collisions:
                raise LocaleError(f"Desktop and {owner} catalogue keys overlap: {sorted(collisions)}")
            leaves.update(owned_leaves)
    values: dict[str, str] = {}
    for key in sorted(keys):
        leaf = leaves.get(key)
        value = leaf if isinstance(leaf, str) else None
        state = classify_catalogue_leaf(key, value)
        if state is not CatalogueLeafState.AUTHORED or value is None:
            refusals.append(f"{locale}:{key} is {state.value}")
            continue
        values[key] = shell_form(key, value)
    return values


def project_catalogue_strings(
    locales_dir: Path,
    *,
    keys: frozenset[str],
    locales: Sequence[str],
    shell_form: Callable[[str, str], str] = _verbatim,
) -> dict[str, dict[str, str]]:
    """Project ``keys`` out of every locale catalogue, as ``{locale: {key: text}}``.

    The tax catalogues at :data:`LOCALES_DIR` are composed with the runtime and
    service catalogues, which must not share a key with them. ``shell_form``
    rewrites an authored value into the form the frontend substitutes.

    Raises:
        LocaleError: when any key is not an authored string in every locale, or
            its placeholders differ between locales or use a form the frontend
            does not substitute.
    """
    refusals: list[str] = []
    strings = {locale: _project_locale(locales_dir, locale, keys, refusals, shell_form) for locale in locales}
    if refusals:
        raise LocaleError("Desktop chrome strings are incomplete: " + "; ".join(refusals))
    for key in sorted(keys):
        placeholders = {locale: _shell_placeholders(key, locale, strings[locale][key]) for locale in locales}
        if len(set(placeholders.values())) != 1:
            detail = ", ".join(f"{locale} {sorted(names)}" for locale, names in placeholders.items())
            raise LocaleError(f"{key} has different placeholders across locales: {detail}")
    return strings
