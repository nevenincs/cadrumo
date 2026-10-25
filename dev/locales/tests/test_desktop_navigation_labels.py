"""The navigation register's labels reach the desktop chrome strings in every locale."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from cadrumo_client.contracts.navigation import load_navigation_register

from .._paths import LOCALES_DIR
from ..desktop_chrome import DESKTOP_LOCALES, DESKTOP_NAVIGATION_LABEL_KEYS, desktop_chrome_strings, main
from ..errors import LocaleError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_label_keys_are_exactly_the_registers() -> None:
    assert {element.label for element in load_navigation_register().elements} == DESKTOP_NAVIGATION_LABEL_KEYS


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
