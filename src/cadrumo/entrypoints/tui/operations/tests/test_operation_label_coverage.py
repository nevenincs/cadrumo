"""Every label the Operations destination and the three new destinations render is worded in four locales.

``tr`` does not raise on a missing key: it humanises the last dotted segment,
so an unworded label renders English-looking text in every locale and nothing
fails. The keys are read from the modules' own ``tr("...")`` literals and from
the palette's destination maps, so a label added later is required here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from ...navigation import TUI_DESTINATION_CATALOGUE
from ...search import _DESTINATION_HELP_LOCALE_KEYS, _DESTINATION_LOCALE_KEYS

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[4] / "locales"
_OPERATIONS_ROOT = Path(__file__).resolve().parents[1]
_MODULES = (
    "destination.py",
    "interactions.py",
    "palette.py",
    "refusal_explanation.py",
    "run_result.py",
    "run_screen.py",
)
_NEW_DESTINATIONS = ("workbench.operations", "workbench.installation", "workbench.reference")


def _literal_keys(module: str) -> set[str]:
    """Return the keys ``module`` passes to ``tr`` as string literals."""
    tree = ast.parse((_OPERATIONS_ROOT / module).read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "tr"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            keys.add(node.args[0].value)
    return keys


def _expected_keys() -> tuple[str, ...]:
    keys = {key for module in _MODULES for key in _literal_keys(module) if key.startswith("tui.operations.")}
    for descriptor in TUI_DESTINATION_CATALOGUE:
        if descriptor.destination in _NEW_DESTINATIONS:
            keys.add(descriptor.label_key)
            keys.add(_DESTINATION_LOCALE_KEYS[descriptor.destination])
            keys.add(_DESTINATION_HELP_LOCALE_KEYS[descriptor.destination])
    return tuple(sorted(keys))


def _catalogue(locale: str) -> dict[str, object]:
    loaded = yaml.safe_load((_LOCALES_ROOT / locale / "common.yml").read_text(encoding="utf-8"))
    return {str(key): value for key, value in loaded.items()}


def _resolve(catalogue: dict[str, object], dotted: str) -> str | None:
    node: object = catalogue
    for segment in dotted.split("."):
        if not isinstance(node, dict) or segment not in node:
            return None
        node = node[segment]
    return node if isinstance(node, str) else None


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_rendered_label_is_worded_in_this_locale(locale: str) -> None:
    catalogue = _catalogue(locale)

    missing = [key for key in _expected_keys() if not (_resolve(catalogue, key) or "").strip()]

    assert not missing, f"{locale} has no wording for: {missing}"


@pytest.mark.parametrize("locale", _LOCALES)
def test_no_wording_under_the_operations_namespace_outlives_its_label(locale: str) -> None:
    """Copy for a label nothing renders reads as reviewed coverage while naming nothing."""
    node: object = _catalogue(locale)
    for segment in ("tui", "operations"):
        assert isinstance(node, dict)
        node = node[segment]

    def leaves(prefix: str, value: object) -> list[str]:
        if isinstance(value, dict):
            return [leaf for key, child in value.items() for leaf in leaves(f"{prefix}.{key}", child)]
        return [prefix]

    assert set(leaves("tui.operations", node)) <= set(_expected_keys())


@pytest.mark.parametrize("locale", ("es", "ca", "hu"))
def test_the_sentences_are_translated_rather_than_left_in_english(locale: str) -> None:
    english, translated = _catalogue("en"), _catalogue(locale)

    untranslated = [
        key
        for key in _expected_keys()
        if " " in (_resolve(english, key) or "") and _resolve(translated, key) == _resolve(english, key)
    ]

    assert not untranslated


def test_the_placeholders_agree_across_the_four_locales() -> None:
    catalogues = {locale: _catalogue(locale) for locale in _LOCALES}
    for key in (
        "tui.operations.status.count",
        "tui.operations.result.page",
        "tui.operations.stopped.remedy_command",
    ):
        english = _resolve(catalogues["en"], key) or ""
        names = {part.split("}")[0] for part in english.split("{")[1:]}
        assert names
        for locale in _LOCALES:
            wording = _resolve(catalogues[locale], key) or ""
            assert {part.split("}")[0] for part in wording.split("{")[1:]} == names, (locale, key)


def test_the_scan_covers_a_plausible_population_of_labels() -> None:
    """An emptied scan would satisfy every coverage test above."""
    keys = _expected_keys()

    assert len(keys) >= 55
    assert sum(1 for key in keys if key.startswith("tui.operations.")) >= 45
    assert {"tui.destination.operations", "tui.destination.installation", "tui.destination.reference"} <= set(keys)
