"""Honesty assertions for the non-English locale catalogues.

A locale that ships untranslated content while pretending to be a real
translation surface is dishonest about its support. This module pins two
contracts. First, for every key, the value under ``ca``, ``es``, and
``hu`` must differ from the corresponding ``en`` value, OR the deviation
must appear in the ``_intentional_identical.json`` allowlist with an
explicit reason. Second, no catalogue value in ANY locale (``en``
included) may echo its own dotted key: a key-echo is the scaffold
placeholder, never a legitimate translation, so it has no per-key
allowlist — only a shrink-only ``_key_echo_ceiling`` ratchet recorded in
the same allowlist file.

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


def _load_metadata_ceiling(locale_code: str, field: str) -> int | None:
    """Return one integer ``_``-prefixed metadata field for *locale_code*."""

    path = _LOCALES_DIR / "_intentional_identical.json"
    raw = json.loads(path.read_text(encoding="utf-8")) or {}
    data: dict[str, dict[str, object]] = raw if isinstance(raw, dict) else {}
    entries = data.get(locale_code, {})
    ceiling = entries.get(field) if isinstance(entries, dict) else None
    return int(ceiling) if isinstance(ceiling, int) else None


def _load_untranslated_ceiling(locale_code: str) -> int | None:
    """Return the ``_untranslated_ceiling`` for *locale_code* if set."""

    return _load_metadata_ceiling(locale_code, "_untranslated_ceiling")


def _key_echo_offenders(flat_leaves: dict[str, str]) -> list[str]:
    """Return keys whose value is the key itself — the scaffold placeholder."""

    return sorted(key for key, value in flat_leaves.items() if value == key)


def _reserved_token_offenders(flat_leaves: dict[str, str]) -> list[str]:
    """Return keys whose value carries a token tr() can never interpolate.

    ``tr()`` consumes ``locale`` and ``default`` as rendering directives and
    strips them from the interpolation map, so a catalogue token named after
    either is permanently unfillable regardless of what a call site passes.
    """
    from cadrumo.core.i18n import extract_placeholders
    from cadrumo.locales import RESERVED_INTERPOLATION_TOKENS

    return sorted(
        key
        for key, value in flat_leaves.items()
        if isinstance(value, str) and extract_placeholders(value) & RESERVED_INTERPOLATION_TOKENS
    )


def test_reserved_token_offender_detection_discriminates() -> None:
    """The detector fires on a planted reserved token and stays quiet otherwise."""

    assert _reserved_token_offenders({"a.b": "x %{locale} y", "c.d": "x %{subject} y"}) == ["a.b"]
    assert _reserved_token_offenders({"c.d": "x {default} y"}) == ["c.d"]
    assert _reserved_token_offenders({"c.d": "plain prose"}) == []


def test_no_catalogue_value_carries_a_reserved_interpolation_token() -> None:
    """No locale value may name a tr() rendering directive as a placeholder.

    Such a token can never bind, so the value looks authored while being
    structurally broken. There is no allowlist and no ratchet: the shipped
    count is zero and must stay zero.
    """

    failures: list[str] = []
    for locale_code in ("ca", "en", "es", "hu"):
        locale_raw = yaml.safe_load((_LOCALES_DIR / f"{locale_code}.yml").read_text(encoding="utf-8"))
        offenders = _reserved_token_offenders(_flatten(locale_raw if isinstance(locale_raw, dict) else {}))
        if offenders:
            failures.append(
                f"{locale_code}.yml carries {len(offenders)} value(s) with a reserved interpolation "
                f"token (locale/default) that tr() can never fill. Rename the token (e.g. "
                f"locale_code) in the value AND the call site. Keys: {offenders[:5]}"
            )

    assert failures == [], "\n".join(failures)


def test_key_echo_offender_detection_discriminates() -> None:
    """The echo detector fires on an injected echo and stays quiet otherwise."""

    assert _key_echo_offenders({"a.b": "a.b", "c.d": "translated"}) == ["a.b"]
    assert _key_echo_offenders({"c.d": "translated"}) == []


def test_no_locale_value_echoes_its_own_key_beyond_the_ratchet() -> None:
    """No catalogue may grow key-echo placeholders in any locale.

    A value equal to its own dotted key is the scaffold's "no translation
    yet" marker leaking into a shipped catalogue. It is never legitimate,
    so there is no per-key allowlist; the ``_key_echo_ceiling`` metadata
    field in ``_intentional_identical.json`` ratchets the existing debt
    down — a missing ceiling means zero tolerance.

    To lower the ratchet after authoring a batch: update
    ``_key_echo_ceiling`` for the locale to the new (lower) count.
    """

    failures: list[str] = []
    for locale_code in ("ca", "en", "es", "hu"):
        locale_raw = yaml.safe_load((_LOCALES_DIR / f"{locale_code}.yml").read_text(encoding="utf-8"))
        offenders = _key_echo_offenders(_flatten(locale_raw if isinstance(locale_raw, dict) else {}))
        ceiling = _load_metadata_ceiling(locale_code, "_key_echo_ceiling") or 0
        if len(offenders) > ceiling:
            failures.append(
                f"{locale_code}.yml carries {len(offenders)} key-echo value(s) against a ceiling of "
                f"{ceiling}. A key-echo is the scaffold placeholder, never a translation; author the "
                f"value via `python -m cadrumo.locales set`. First five: {offenders[:5]}"
            )

    assert failures == [], "\n".join(failures)


def test_translated_values_differ_from_en_unless_allowlisted() -> None:
    """Every ``ca`` / ``es`` / ``hu`` value must differ from ``en`` OR be allowlisted.

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
    en_raw = yaml.safe_load((_LOCALES_DIR / "en.yml").read_text(encoding="utf-8"))
    en_keys = _flatten(en_raw if isinstance(en_raw, dict) else {})
    failures: list[str] = []

    for locale_code in ("ca", "es", "hu"):
        locale_allows = allowlist.get(locale_code, set())
        locale_raw = yaml.safe_load((_LOCALES_DIR / f"{locale_code}.yml").read_text(encoding="utf-8"))
        locale_keys = _flatten(locale_raw if isinstance(locale_raw, dict) else {})

        offenders = [
            key
            for key, en_value in en_keys.items()
            if key in locale_keys and locale_keys[key] == en_value and key not in locale_allows
        ]
        failure = _identical_to_en_failure(
            locale_code, offenders, bucket_active="untranslated_pending" in locale_allows
        )
        if failure is not None:
            failures.append(failure)

    assert failures == [], "\n".join(failures)


def _identical_to_en_failure(locale_code: str, offenders: list[str], *, bucket_active: bool) -> str | None:
    """Render one locale's identical-to-en verdict, or ``None`` when clean.

    Wholesale-bucket mode enforces the ratchet ceiling instead of requiring
    per-key allowlist entries; a regression that adds new untranslated
    strings pushes the count over the ceiling.
    """

    if not bucket_active:
        if not offenders:
            return None
        return (
            f"{locale_code}.yml carries {len(offenders)} value(s) identical to en.yml without an "
            f"explicit allowlist entry. First five: {offenders[:5]}"
        )
    ceiling = _load_untranslated_ceiling(locale_code)
    if ceiling is None:
        return (
            f"{locale_code}: 'untranslated_pending' bucket is active but "
            f"'_untranslated_ceiling' is missing from _intentional_identical.json. "
            f"Add the current identical-key count ({len(offenders)}) as the ceiling."
        )
    if len(offenders) > ceiling:
        return (
            f"{locale_code}.yml has {len(offenders)} key(s) identical to en.yml, "
            f"exceeding the ratchet ceiling of {ceiling}. "
            f"New untranslated keys (first five of overflow): {offenders[ceiling:][:5]}"
        )
    return None
