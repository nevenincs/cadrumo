"""Parity gate: registry-declared locale keys resolve in every catalogue.

The category profile registry declares operator-facing labels and notes as
translation keys. Those keys are invisible to the Python-source scanners, so
they were absent from all four catalogues and rendered as their own raw key.
This gate binds the registry key universe to the catalogues.

The check is RESOLUTION, not membership. ``scaffold`` inserts a missing key
with its own dotted path as the value, so a membership check turns green the
moment the scaffolder runs, over a catalogue nobody has translated. Asking the
real renderer with a sentinel ``default`` distinguishes "a human wrote this"
from "the scaffolder reserved a slot": the renderer already treats a value
equal to its key as a miss, so placeholders stay red until translated.

Assertions are structural — they assert that resolution SUCCEEDS, never what a
key resolves to. Asserting a translated string would encode prose the test
author wrote, which no defect can falsify.
"""

from pathlib import Path

import pytest

from ..core.i18n import tr
from ..locales._registry_scanner import scan_registry_keys
from ..locales.manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
_LOCALES = ("en", "es", "ca", "hu")

# Returned verbatim when a key has no catalogue entry, so a miss is detectable
# without inspecting the rendered text. Chosen to be a string no catalogue
# could plausibly contain.
_SENTINEL = "__CADRUMO_UNRESOLVED__"


def _unresolved(keys: set[str], locale: str) -> set[str]:
    """Return the subset of ``keys`` that one catalogue does not translate."""
    return {key for key in keys if tr(key, locale=locale, default=_SENTINEL) == _SENTINEL}


def _leaf_value(catalogue: object, dotted_key: str) -> object:
    """Walk a dotted key through a loaded catalogue and return its leaf value."""
    node = catalogue
    for part in dotted_key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("registry_key", sorted(scan_registry_keys()))
def test_registry_key_resolves_in_catalogue(registry_key: str, locale: str) -> None:
    """Every registry-declared locale key resolves in every catalogue."""
    assert not _unresolved({registry_key}, locale), (
        f"{registry_key!r} is declared by the category profile registry but does not "
        f"resolve in {locale}.yml; run `python -m cadrumo.locales scaffold`, then author "
        f"the value with `python -m cadrumo.locales set {locale} {registry_key} <value>`. "
        f"Scaffolding alone leaves the key echoing itself, which does not count as translated."
    )


def test_registry_scan_excludes_citation_quotes() -> None:
    """The scan covers labels, notes, and cap variants — never citation quotes.

    Citation quotes are verbatim AEAT excerpts sourced through a separate
    evidence pass; enrolling them here would invite a translator to author
    legal evidence.

    The count is pinned deliberately: a new spending category reds this gate
    until the number is raised by hand, which forces the carve-out to be
    re-examined rather than silently widened.
    """
    keys = scan_registry_keys()
    assert len(keys) == 86
    assert not [key for key in keys if key.endswith(".quote")]


@pytest.mark.parametrize("locale", _LOCALES)
def test_fabricated_key_is_reported_unresolved(locale: str) -> None:
    """Anti-tautology: the resolution check reports a key no catalogue declares."""
    fabricated = "categories.registry.__nonexistent__"
    assert _unresolved({fabricated}, locale) == {fabricated}


def test_a_self_echoing_catalogue_value_is_reported_unresolved() -> None:
    """A scaffold placeholder does not count as translated.

    This is the property a membership check cannot express, and the reason this
    gate asks the renderer instead of the catalogue key set: ``scaffold`` writes
    a missing key as its own dotted path, so membership would go green while the
    operator still sees a humanised key fragment.

    Driven from a real catalogue value that echoes its own key rather than a
    constructed one, so the assertion exercises the same path a scaffolded key
    takes. If no catalogue holds such a value the premise no longer exists and
    the test says so instead of passing vacuously.
    """
    manager = LocaleManager(_LOCALES_DIR.parent, _LOCALES_DIR)
    for locale in _LOCALES:
        catalogue = manager.load_locale(_LOCALES_DIR / f"{locale}.yml")
        echoes = [key for key in manager.get_yaml_keys(catalogue) if _leaf_value(catalogue, key) == key]
        if not echoes:
            continue
        assert _unresolved({echoes[0]}, locale) == {echoes[0]}, (
            f"{echoes[0]!r} stores its own key as its value in {locale}.yml, but the "
            f"resolution check reported it as translated; scaffold placeholders must "
            f"never satisfy this gate."
        )
        return
    pytest.fail(
        "no catalogue holds a self-echoing value, so this gate's placeholder "
        "premise could not be exercised; re-verify the check still rejects them",
    )
