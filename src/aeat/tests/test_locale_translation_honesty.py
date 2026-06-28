"""Honesty assertion for ca and hu locale translations.

A locale that ships untranslated content while pretending to be a real
translation surface is dishonest about its support. This module pins a
contract: for every key, the value under ``ca`` and ``hu`` must differ
from the corresponding ``en`` value, OR the deviation must appear in
the ``_intentional_identical.json`` allowlist with an explicit reason.

The current state ships ca and hu as wholesale-English placeholders.
The allowlist's ``untranslated_pending`` bucket captures that state
with a ``_untranslated_ceiling`` integer that records the maximum
number of allowed identical-to-en keys.  Adding new untranslated
strings causes the count to exceed the ceiling and the test fails —
the ceiling is a ratchet, not a blanket bypass.

To lower the ratchet after translating a batch of keys: re-run the
count and update ``_untranslated_ceiling`` in the allowlist file.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"

# Recursive YAML node: either a leaf string or a nested mapping.
type _LocaleNode = str | dict[str, "_LocaleNode"]


def _flatten(mapping: dict[str, _LocaleNode], prefix: str = "") -> dict[str, str]:
    """Walk a nested YAML mapping and return ``{dotted_key: leaf}``."""

    result: dict[str, str] = {}
    for key, value in mapping.items():
        sub = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten(value, sub))
        else:
            result[sub] = value
    return result


def _load_allowlist() -> dict[str, set[str]]:
    """Return ``{locale: <set of keys explicitly allowed to match en>}``.

    The allowlist uses either per-key justifications OR the wholesale
    ``untranslated_pending`` bucket. Keys beginning with ``_`` are
    internal metadata (e.g. ``_untranslated_ceiling``) and are excluded
    from the returned set.
    """

    path = _LOCALES_DIR / "_intentional_identical.json"
    raw = json.loads(path.read_text(encoding="utf-8")) or {}
    data: dict[str, dict[str, str]] = raw if isinstance(raw, dict) else {}
    result: dict[str, set[str]] = {}
    for locale, entries in data.items():
        if isinstance(entries, dict):
            # Exclude internal metadata keys (prefixed with "_").
            result[locale] = {str(key) for key in entries if not str(key).startswith("_")}
    return result


def _load_untranslated_ceiling(locale_code: str) -> int | None:
    """Return the ``_untranslated_ceiling`` for *locale_code* if set."""

    path = _LOCALES_DIR / "_intentional_identical.json"
    raw = json.loads(path.read_text(encoding="utf-8")) or {}
    data: dict[str, dict[str, object]] = raw if isinstance(raw, dict) else {}
    entries = data.get(locale_code, {})
    ceiling = entries.get("_untranslated_ceiling") if isinstance(entries, dict) else None
    return int(ceiling) if isinstance(ceiling, int) else None


@pytest.mark.parametrize("locale_code", ["ca", "hu"])
def test_ca_hu_values_differ_from_en_unless_allowlisted(locale_code: str) -> None:
    """Every ``ca`` / ``hu`` value must differ from ``en`` OR be allowlisted.

    When the wholesale ``untranslated_pending`` bucket is active, the test
    acts as a ratchet: the number of identical-to-en keys must not exceed
    the ``_untranslated_ceiling`` stored in the allowlist.  This prevents
    regressions that add new untranslated strings while the bulk translation
    work is in progress.

    To lower the ratchet after a translation pass: update
    ``_untranslated_ceiling`` in ``_intentional_identical.json`` to the new
    (lower) observed count.
    """

    allowlist = _load_allowlist()
    locale_allows = allowlist.get(locale_code, set())

    en_raw = yaml.safe_load((_LOCALES_DIR / "en.yml").read_text(encoding="utf-8"))
    locale_raw = yaml.safe_load((_LOCALES_DIR / f"{locale_code}.yml").read_text(encoding="utf-8"))
    en_keys = _flatten(en_raw if isinstance(en_raw, dict) else {})
    locale_keys = _flatten(locale_raw if isinstance(locale_raw, dict) else {})

    offenders: list[str] = []
    for key, en_value in en_keys.items():
        locale_value = locale_keys.get(key)
        if locale_value is None:
            continue
        if locale_value == en_value and key not in locale_allows:
            offenders.append(key)

    if "untranslated_pending" in locale_allows:
        # Wholesale-bucket mode: enforce the ratchet ceiling instead of
        # requiring per-key allowlist entries.  A regression that adds new
        # untranslated strings causes the count to exceed the ceiling.
        ceiling = _load_untranslated_ceiling(locale_code)
        if ceiling is None:
            pytest.fail(
                f"{locale_code}: 'untranslated_pending' bucket is active but "
                f"'_untranslated_ceiling' is missing from _intentional_identical.json. "
                f"Add the current identical-key count ({len(offenders)}) as the ceiling.",
            )
        if len(offenders) > ceiling:
            pytest.fail(
                f"{locale_code}.yml has {len(offenders)} key(s) identical to en.yml, "
                f"exceeding the ratchet ceiling of {ceiling}. "
                f"New untranslated keys (first five of overflow): "
                f"{offenders[ceiling:][:5]}",
            )
        return

    if offenders:
        pytest.fail(
            f"{locale_code}.yml carries {len(offenders)} value(s) identical to en.yml without an "
            f"explicit allowlist entry. First five: {offenders[:5]}",
        )
