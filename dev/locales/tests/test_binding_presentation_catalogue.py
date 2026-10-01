"""Authored binding text names live registry identities in every shipped language."""

from __future__ import annotations

from functools import cache

import pytest

from cadrumo.core.external_constants import OutputLanguage
from cadrumo.core.i18n.render import lookup_translation
from cadrumo.core.resources.bundled_data import bundled_path
from dev.registry.compiler.loader import load_modelo_locale_key_projection

from .._paths import LOCALES_DIR, SRC_DIR
from ..manager import LocaleManager

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@cache
def _catalogue_keys() -> dict[OutputLanguage, frozenset[str]]:
    manager = LocaleManager(SRC_DIR, LOCALES_DIR)
    return {
        language: frozenset(
            key
            for key in manager.get_yaml_keys(manager.load_locale(LOCALES_DIR / language.value))
            if key.startswith("modelo.schema.") and ".binding." in key
        )
        for language in OutputLanguage
    }


def _assert_declared(declared: frozenset[str], authored: frozenset[str]) -> None:
    assert not (authored - declared), sorted(authored - declared)


def _assert_translated(authored: frozenset[str], translated: frozenset[str]) -> None:
    assert not (authored - translated), sorted(authored - translated)


def test_binding_catalogue_keys_reference_declared_registry_bindings() -> None:
    declared = load_modelo_locale_key_projection(bundled_path("registry", "aeat"))
    authored = frozenset().union(*_catalogue_keys().values())
    assert authored, "no binding presentation text was discovered"
    _assert_declared(declared, authored)


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_every_authored_binding_text_resolves_in_each_language(language: OutputLanguage) -> None:
    catalogues = _catalogue_keys()
    authored = frozenset().union(*catalogues.values())
    _assert_translated(authored, catalogues[language])
    unresolved = [
        key
        for key in sorted(authored)
        if not (text := lookup_translation(key, locale=language.value)) or not text.strip() or text == key
    ]
    assert not unresolved, unresolved


def test_catalogue_gate_detects_an_orphan_and_a_missing_translation() -> None:
    live = "modelo.schema.999.binding.input.label"
    orphan = "modelo.schema.999.binding.unknown.label"
    declared = frozenset({live})
    _assert_declared(declared, declared)
    _assert_translated(declared, declared)
    with pytest.raises(AssertionError, match="unknown"):
        _assert_declared(declared, frozenset({live, orphan}))
    with pytest.raises(AssertionError, match="input"):
        _assert_translated(declared, frozenset())
