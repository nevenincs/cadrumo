"""The navigation register's labels reach the desktop chrome strings in every locale."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from cadrumo_client.contracts.navigation import load_navigation_register

from .._paths import LOCALES_DIR
from ..desktop_chrome import (
    DESKTOP_LOCALES,
    DESKTOP_NAVIGATION_KEYWORD_KEYS,
    DESKTOP_NAVIGATION_LABEL_KEYS,
    desktop_chrome_strings,
    main,
)
from ..errors import LocaleError
from ..signal_translation_matrix import suspicious_translation_locales

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The official Spanish words a person meets on AEAT pages, forms and bank
# documents. Every locale keeps them as search words beside its own, so the
# palette finds a view by the word printed on the paper in front of them.
_OFFICIAL_SPANISH_TERMS: dict[str, frozenset[str]] = {
    "ledger": frozenset({"libro", "registros"}),
    "ledger/movements": frozenset({"movimientos", "extracto"}),
    "ledger/invoices": frozenset({"facturas"}),
    "ledger/documents": frozenset({"justificantes"}),
    "ledger/registers": frozenset({"prorrata", "libros", "registro"}),
    "withholding": frozenset({"retenciones", "irpf"}),
    "declarations": frozenset({"modelo", "declaraciones"}),
    "aeat-sync": frozenset({"aeat", "sede", "censo", "notificaciones", "dehu"}),
    "reference": frozenset({"normativa", "boe"}),
    "profile": frozenset({"contribuyente"}),
    "profile/aeat-access": frozenset({"aeat", "clave", "certificado"}),
    "calendar": frozenset({"plazos"}),
    "browser": frozenset({"sede", "aeat", "agencia", "tributaria"}),
}


def test_the_label_keys_are_exactly_the_registers() -> None:
    assert {element.label for element in load_navigation_register().elements} == DESKTOP_NAVIGATION_LABEL_KEYS


def test_the_register_names_a_keyword_key_beside_each_label_never_the_words() -> None:
    elements = load_navigation_register().elements
    assert {element.keywords for element in elements} == DESKTOP_NAVIGATION_KEYWORD_KEYS
    assert len(DESKTOP_NAVIGATION_KEYWORD_KEYS) == len(elements)
    for element in elements:
        assert element.keywords == element.label.removesuffix(".label") + ".keywords", element.id


def test_every_navigation_keyword_set_is_generated_and_translated_in_every_locale(tmp_path: Path) -> None:
    output = tmp_path / "chrome-strings.json"
    assert main(["--output", str(output)]) == 0
    written = json.loads(output.read_text(encoding="utf-8"))
    for key in DESKTOP_NAVIGATION_KEYWORD_KEYS:
        words = {locale: frozenset(written[locale][key].split()) for locale in DESKTOP_LOCALES}
        assert all(words.values()), key
        # A translated locale searches by its own words, not a copy of another's.
        assert len(set(words.values())) == len(DESKTOP_LOCALES), key
        leaves = {locale: {key: written[locale][key]} for locale in DESKTOP_LOCALES}
        assert not suspicious_translation_locales(key, leaves), key


def test_every_locale_keeps_the_official_spanish_search_words() -> None:
    register = load_navigation_register()
    strings = desktop_chrome_strings(LOCALES_DIR)
    assert set(_OFFICIAL_SPANISH_TERMS) <= {element.id for element in register.elements}
    for view_id, terms in _OFFICIAL_SPANISH_TERMS.items():
        element = register.element(view_id)
        assert element is not None
        for locale in DESKTOP_LOCALES:
            assert terms <= set(strings[locale][element.keywords].split()), (view_id, locale)


def test_a_missing_keyword_translation_refuses_generation(tmp_path: Path) -> None:
    key = sorted(DESKTOP_NAVIGATION_KEYWORD_KEYS)[0]
    for locale, text in (("en", "records books"), ("es", None)):
        directory = tmp_path / locale
        directory.mkdir()
        document = {} if text is None else _nested(key, text)
        (directory / "common.yml").write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(LocaleError, match=key.replace(".", r"\.")):
        desktop_chrome_strings(tmp_path, keys=frozenset({key}), locales=("en", "es"))


def test_every_navigation_label_is_generated_in_every_locale(tmp_path: Path) -> None:
    output = tmp_path / "chrome-strings.json"
    assert main(["--output", str(output)]) == 0
    written = json.loads(output.read_text(encoding="utf-8"))
    for locale in DESKTOP_LOCALES:
        assert set(written[locale]) >= DESKTOP_NAVIGATION_LABEL_KEYS, locale
        assert all(written[locale][key].strip() for key in DESKTOP_NAVIGATION_LABEL_KEYS), locale


def _nested(key: str, value: str) -> dict[str, object]:
    head, _, rest = key.partition(".")
    return {head: _nested(rest, value) if rest else value}


def test_a_missing_label_translation_refuses_generation(tmp_path: Path) -> None:
    label = sorted(DESKTOP_NAVIGATION_LABEL_KEYS)[0]
    for locale, text in (("en", "Ledger"), ("es", None)):
        directory = tmp_path / locale
        directory.mkdir()
        document = {} if text is None else _nested(label, text)
        (directory / "common.yml").write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(LocaleError, match=label.replace(".", r"\.")):
        desktop_chrome_strings(tmp_path, keys=frozenset({label}), locales=("en", "es"))
    # The canonical catalogues carry every label, so the default projection admits them.
    strings = desktop_chrome_strings(LOCALES_DIR)
    assert all(set(strings[locale]) >= DESKTOP_NAVIGATION_LABEL_KEYS for locale in DESKTOP_LOCALES)
