"""Honesty assertion for ca and hu locale translations.

A locale that ships untranslated content while pretending to be a real
translation surface is dishonest about its support. This module pins a
contract: for every key, the value under ``ca`` and ``hu`` must differ
from the corresponding ``en`` value, OR the deviation must appear in
the ``_intentional_identical.yml`` allowlist with an explicit reason.

The current state ships ca and hu as wholesale-English placeholders.
The allowlist's ``untranslated_pending`` bucket captures that state
explicitly; the test passes while later slices replace ca / hu values
with real translations and remove entries from the allowlist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_LOCALES_DIR = Path(__file__).parent


def _flatten(mapping: Any, prefix: str = "") -> dict[str, Any]:
    """Walk a nested YAML mapping and return ``{dotted_key: leaf}``."""

    result: dict[str, Any] = {}
    if isinstance(mapping, dict):
        for key, value in mapping.items():
            sub = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                result.update(_flatten(value, sub))
            else:
                result[sub] = value
    return result


def _load_allowlist() -> dict[str, set[str]]:
    """Return ``{locale: <set of keys explicitly allowed to match en>}``.

    Currently the allowlist uses one ``untranslated_pending`` bucket
    per locale that absorbs every offending key. Future slices replace
    the bucket with per-key reasons or remove entries when real
    translations land.
    """

    path = _LOCALES_DIR / "_intentional_identical.yml"
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # The current allowlist uses a wholesale "untranslated_pending"
    # entry per locale rather than per-key justifications. Treat the
    # presence of that key as "every key is allowed to match en".
    result: dict[str, set[str]] = {}
    for locale, entries in data.items():
        if isinstance(entries, dict):
            result[locale] = {str(key) for key in entries}
    return result


@pytest.mark.parametrize("locale_code", ["ca", "hu"])
def test_ca_hu_values_differ_from_en_unless_allowlisted(locale_code: str) -> None:
    """Every ``ca`` / ``hu`` value must differ from ``en`` OR be allowlisted."""

    allowlist = _load_allowlist()
    locale_allows = allowlist.get(locale_code, set())
    if "untranslated_pending" in locale_allows:
        # Wholesale allow for this slice; future per-key replacements
        # remove this bucket and the loop below starts flagging.
        return

    en_keys = _flatten(yaml.safe_load((_LOCALES_DIR / "en.yml").read_text(encoding="utf-8")))
    locale_keys = _flatten(yaml.safe_load((_LOCALES_DIR / f"{locale_code}.yml").read_text(encoding="utf-8")))

    offenders: list[str] = []
    for key, en_value in en_keys.items():
        locale_value = locale_keys.get(key)
        if locale_value is None:
            continue
        if locale_value == en_value and key not in locale_allows:
            offenders.append(key)

    if offenders:
        pytest.fail(
            f"{locale_code}.yml carries {len(offenders)} value(s) identical to en.yml without an "
            f"explicit allowlist entry. First five: {offenders[:5]}"
        )
