"""Parity gate: registry-declared locale keys resolve in every catalogue.

The category profile registry declares operator-facing labels and notes as
translation keys. Those keys are invisible to the Python-source scanners, so
they were absent from all four catalogues and rendered as their own raw key.
This gate binds the registry key universe to the catalogues.

Assertions are structural — key membership only. Asserting a translated string
would encode prose the test author wrote, which no defect can falsify.
"""

from functools import cache
from pathlib import Path

import pytest

from ..locales._registry_scanner import scan_registry_keys
from ..locales.manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"


@cache
def _catalogue_keys(locale_file: str) -> frozenset[str]:
    """Return every dotted leaf key declared by one catalogue.

    Cached because the per-key parametrisation asks the same four catalogues
    hundreds of times; a fresh parse per case costs minutes of wall clock.
    """
    manager = LocaleManager(_LOCALES_DIR.parent, _LOCALES_DIR)
    path = _LOCALES_DIR / locale_file
    return frozenset(manager.get_yaml_keys(manager.load_locale(path)))


def _unresolved(keys: set[str], locale_file: str) -> set[str]:
    """Return the subset of ``keys`` that one catalogue does not declare."""
    return keys - _catalogue_keys(locale_file)


@pytest.mark.parametrize("locale_file", ["en.yml", "es.yml", "ca.yml", "hu.yml"])
@pytest.mark.parametrize("registry_key", sorted(scan_registry_keys()))
def test_registry_key_resolves_in_catalogue(registry_key: str, locale_file: str) -> None:
    """Every registry-declared locale key is present in every catalogue."""
    assert not _unresolved({registry_key}, locale_file), (
        f"{registry_key!r} is declared by the category profile registry but absent "
        f"from {locale_file}; run `python -m cadrumo.locales scaffold`"
    )


def test_registry_scan_excludes_citation_quotes() -> None:
    """The scan covers labels, notes, and cap variants — never citation quotes.

    Citation quotes are verbatim AEAT excerpts sourced through a separate
    evidence pass; enrolling them here would invite a translator to author
    legal evidence.
    """
    keys = scan_registry_keys()
    assert len(keys) == 86
    assert not [key for key in keys if key.endswith(".quote")]


@pytest.mark.parametrize("locale_file", ["en.yml", "es.yml", "ca.yml", "hu.yml"])
def test_fabricated_key_is_reported_unresolved(locale_file: str) -> None:
    """Anti-tautology: the resolution check reports a key no catalogue declares."""
    fabricated = "categories.registry.__nonexistent__"
    assert _unresolved({fabricated}, locale_file) == {fabricated}
