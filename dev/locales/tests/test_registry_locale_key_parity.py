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

from typing import cast

import pytest

from cadrumo.core.i18n import tr

from .._paths import LOCALES_DIR
from .._registry_scanner import scan_registry_keys
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# The catalogue root is the tooling's own constant, not a path rebuilt from this
# file's position. The hand-built form counted two parents up from
# `dev/locales/tests/`, which lands on `dev/` and resolved to a `dev/src/...`
# tree that does not exist; it also named a monolithic `<locale>.yml` that the
# shard split retired. Both are fixed by asking `_paths` where the catalogues
# live and by loading the locale's shard DIRECTORY, which `load_locale` merges.
_LOCALES_DIR = LOCALES_DIR
_LOCALES = ("en", "es", "ca", "hu")

# Returned verbatim when a key has no catalogue entry, so a miss is detectable
# without inspecting the rendered text. Chosen to be a string no catalogue
# could plausibly contain.
_SENTINEL = "__CADRUMO_UNRESOLVED__"


def _unresolved(keys: set[str], locale: str) -> set[str]:
    """Return the subset of ``keys`` that one catalogue does not translate."""
    return {key for key in keys if tr(key, locale=locale, default=_SENTINEL) == _SENTINEL}


def _as_str_keyed_dict(value: object) -> dict[str, object] | None:
    """Narrow a loaded YAML catalogue node to a string-keyed dict, or ``None``.

    Locale catalogues are YAML mappings, whose keys are always strings; the
    runtime check restores that static guarantee for the dotted-key walk
    below.
    """
    if not isinstance(value, dict):
        return None
    for key in value:
        if not isinstance(key, str):
            return None
    return cast("dict[str, object]", value)


def _leaf_value(catalogue: object, dotted_key: str) -> object:
    """Walk a dotted key through a loaded catalogue and return its leaf value."""
    node = _as_str_keyed_dict(catalogue)
    if node is None:
        return None
    head, _, rest = dotted_key.partition(".")
    if head not in node:
        return None
    value = node[head]
    return _leaf_value(value, rest) if rest else value


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("registry_key", sorted(scan_registry_keys()))
def test_registry_key_resolves_in_catalogue(registry_key: str, locale: str) -> None:
    """Every registry-declared locale key resolves in every catalogue."""
    assert not _unresolved({registry_key}, locale), (
        f"{registry_key!r} is declared by the category profile registry but does not "
        f"resolve in {locale}.yml; run `python -m dev.locales scaffold`, then author "
        f"the value with `python -m dev.locales set {locale} {registry_key} <value>`. "
        f"Scaffolding alone leaves the key echoing itself, which does not count as translated."
    )


def test_registry_scan_excludes_citation_quotes() -> None:
    """The scan covers labels, notes, and cap variants — never citation quotes.

    Citation quotes are verbatim AEAT excerpts sourced through a separate
    evidence pass; enrolling them here would invite a translator to author
    legal evidence.

    The carve-out is held by SHAPE rather than by a pinned count. A tally reds
    on every new spending category, which trains the reader to raise the number
    and stops discriminating; it also says nothing about which key appeared.
    What remains are the properties the data can actually violate: a citation
    quote entering the scan, a key escaping the namespace, and the literal key
    "None", which is what a profile that declares no value for a stringified
    field produces. That last one shipped: the mutualidad rule's ``notes`` sat
    after its cap-schedule array-of-tables, so TOML bound it to the final
    schedule row and the rule itself had none.
    """
    keys = scan_registry_keys()

    # A FLOOR, which is not the pinned count the docstring rightly refuses: a
    # tally reds on every new category, while a floor only fires when the scan
    # SHRINKS. Truthiness alone ruled out a scan returning nothing, and the
    # shape assertions below are all negatives - no quote, no escape, no
    # literal None - so they hold trivially over a handful of keys. The same
    # scan parametrizes the per-key parity gate above, where a partial
    # collapse shrinks 360 cases without failing anything. Live: 90 keys,
    # 42 notes and 37 labels.
    assert len(keys) >= 70, (
        f"the registry scan returned {len(keys)} keys; the negative assertions below and "
        "the per-key parity gate above are both measured over a fraction of the surface"
    )
    assert not [key for key in keys if key.endswith(".quote")]
    assert "None" not in keys, (
        "the scan emitted the literal key 'None', which means a profile declares no "
        "value for a field the scanner stringifies unconditionally -- the key is then "
        "unauthorable and reds the parity gate with no way to fix it in a catalogue"
    )
    escaped = sorted(k for k in keys if not k.startswith("categories.registry."))
    assert not escaped, (
        "a scanned key escaped the category-registry namespace, so it is outside "
        f"this gate's reasoning entirely: {escaped}"
    )


@pytest.mark.parametrize("locale", _LOCALES)
def test_fabricated_key_is_reported_unresolved(locale: str) -> None:
    """Anti-tautology: the resolution check reports a key no catalogue declares."""
    fabricated = "categories.registry.__nonexistent__"
    assert _unresolved({fabricated}, locale) == {fabricated}


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_catalogue_leaf_echoes_its_own_key(locale: str) -> None:
    """No catalogue ships a scaffold placeholder in place of a translation.

    ``scaffold`` writes a missing key as its own dotted path, so a membership
    check turns green the moment the scaffolder runs over a catalogue nobody
    has translated. The renderer treats such a value as a miss
    (``_render.py`` ``_lookup_translation``), which is what lets the resolution
    checks above distinguish a translation from a reserved slot.

    This asserts the shipped state directly: reintroducing a placeholder reds
    the gate and names the key, rather than being absorbed as "declared".
    """
    manager = LocaleManager(_LOCALES_DIR.parent, _LOCALES_DIR)
    catalogue = manager.load_locale(_LOCALES_DIR / locale)
    keys = manager.get_yaml_keys(catalogue)
    assert keys, f"{locale} catalogue yielded no keys; no leaf can echo its own key in an empty catalogue"
    echoes = sorted(key for key in keys if _leaf_value(catalogue, key) == key)
    assert not echoes, (
        f"the {locale} catalogue stores {len(echoes)} key(s) as their own value, which the renderer "
        f"treats as untranslated: {echoes[:5]}. Author them with "
        f"`python -m dev.locales set {locale} <key> <value>`."
    )
