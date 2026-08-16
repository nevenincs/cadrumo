"""Honesty assertions for the shared locale catalogues.

A locale that ships untranslated content while pretending to be a real
translation surface is dishonest about its support. This module pins three
contracts. First, generic application keys under ``ca``, ``es``, and
``hu`` must differ from the corresponding ``en`` value. Modelo schema keys
must instead be judged against the official Spanish source, and Spanish
itself is never treated as a translation target. An exact non-Spanish match
requires an explicit ``_intentional_identical.json`` reason. Second, no
catalogue value in ANY locale (``en``
included) may echo its own dotted key: a key-echo is the scaffold
placeholder, never a legitimate translation, so it has no per-key
allowlist — only a shrink-only ``_key_echo_ceiling`` ratchet recorded in
the same allowlist file.

The Modelo catalogue also contains optional non-Spanish leaves whose value is
``null`` until a translation is authored. Those absent values are intentional
Spanish fallback and are excluded from the identical-source comparison;
authored non-null values remain subject to the same allowlist and ratchet
rules. The ``_untranslated_ceiling = 0`` metadata therefore grants no bypass
for a new authored value that merely echoes its canonical source.

The bucket and its ceiling are retained rather than removed because
neither is hand-editable — ``_intentional_identical.json`` is
CLI-managed (``aeat-locales-cli``), ``allow-identical`` only ADDS a
per-key entry, and no verb removes one; ``dev.locales._status``
also binds the bucket key, so dropping it is a code change rather than
a data edit.
"""

from __future__ import annotations

import json
import tomllib
from functools import cache
from pathlib import Path

import pytest
import yaml

from ..domain.calculations.registry import (
    casilla_continuity_locale_key,
    casilla_occurrence_locale_key,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LOCALES_DIR = Path(__file__).resolve().parents[1] / "locales"
_MODELO_SCHEMA_PREFIX = "modelo.schema."
_MODELO_SOURCE_SUFFIXES = (".label", ".title", ".official_name")


def _is_modelo_source_key(key: str) -> bool:
    """Return whether a Modelo leaf carries mandatory official source text."""

    return key.startswith(_MODELO_SCHEMA_PREFIX) and key.endswith(_MODELO_SOURCE_SUFFIXES)


# Recursive YAML node: either a leaf string or a nested mapping.
type _LocaleNode = str | dict[str, "_LocaleNode"] | None


def _flatten(mapping: dict[str, _LocaleNode], prefix: str = "") -> dict[str, str | None]:
    """Walk a nested YAML mapping and return ``{dotted_key: leaf}``."""

    result: dict[str, str | None] = {}
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


@cache
def _parsed_catalogue(locale_code: str) -> tuple[tuple[str, str | None], ...]:
    """Parse and flatten one shipped catalogue, once per process.

    The catalogues are ~3 MB each and pure-Python YAML parsing measured ~7s
    apiece, while the five gates below read the same four files roughly
    nineteen times between them -- so this module spent almost its entire
    runtime re-parsing four unchanging files.

    ``yaml.CSafeLoader`` is libyaml, the C parser, and measured 0.773s against
    7.402s for the pure-Python loader on the largest catalogue. Both loaders
    were confirmed to produce equal documents for all four shipped locales
    before this switched; the fallback keeps the gate runnable on a build of
    PyYAML compiled without libyaml. This mirrors what the production renderer
    in ``core.i18n`` already does.

    Parsing here stays INDEPENDENT of the production locale reader on purpose.
    These gates make claims about what the shipped FILES contain, so borrowing
    the reader would let a reader that silently dropped entries certify its own
    view of the catalogue rather than the catalogue.

    The proof of scan lives here rather than at each gate because several gates
    read the same four catalogues: guarding the reader means one added later
    inherits it instead of forgetting it. An empty catalogue carries no blank
    value, no key echo and no reserved token, so each of those gates would
    report exactly what a clean catalogue reports.
    """
    text = (_LOCALES_DIR / f"{locale_code}.yml").read_text(encoding="utf-8")
    raw = yaml.load(text, Loader=yaml.CSafeLoader) if hasattr(yaml, "CSafeLoader") else yaml.safe_load(text)
    leaves = _flatten(raw if isinstance(raw, dict) else {})
    assert leaves, f"{locale_code}.yml flattened to no leaves; every honesty gate over it is vacuous"
    return tuple(leaves.items())


def _catalogue_leaves(locale_code: str) -> dict[str, str | None]:
    """Return one shipped catalogue's flattened leaves.

    Rebuilt per call from the cached parse so each gate owns its own mapping.
    Handing out one shared dict would make every caller's correctness depend on
    no other caller ever mutating it -- safe only by convention, where the
    copy costs microseconds against a multi-second parse.
    """
    return dict(_parsed_catalogue(locale_code))


@cache
def _continuity_backing() -> dict[str, str]:
    """Map each casilla occurrence label key to its continuity label key.

    Read from the registry's casilla TOML rather than through the validated
    authority, because this gate makes a claim about the SHIPPED catalogues and
    must stay answerable while the registry is refusing validation for unrelated
    reasons. It mirrors exactly what the loader does at
    :func:`~cadrumo.domain.calculations.registry._modelo_localization._localised_casilla`:
    read ``id`` and ``continuidad_id`` off the raw casilla table and derive both
    keys with the same two canonical encoders.

    Returns:
        ``{occurrence_label_key: continuity_label_key}`` for every casilla that
        declares a ``continuidad_id``. A casilla without one is simply absent,
        which is what makes its null occurrence value a real offender.
    """
    backing: dict[str, str] = {}
    modelos_dir = _LOCALES_DIR.parent / "_data" / "registry" / "aeat" / "modelos"
    for casilla_file in modelos_dir.glob("*/revisions/*/casillas/*.toml"):
        modelo_id = casilla_file.parents[3].name
        try:
            document = tomllib.loads(casilla_file.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):  # pragma: no cover - unreadable fragment
            continue
        for revision_id, revision in (document.get("revisions") or {}).items():
            if not isinstance(revision, dict):
                continue
            for casilla in revision.get("casillas") or ():
                if not isinstance(casilla, dict):
                    continue
                casilla_id = casilla.get("id")
                continuidad_id = casilla.get("continuidad_id")
                if not isinstance(casilla_id, str) or not isinstance(continuidad_id, str):
                    continue
                backing[casilla_occurrence_locale_key(modelo_id, revision_id, casilla_id, "label")] = (
                    casilla_continuity_locale_key(modelo_id, continuidad_id, "label")
                )
    assert backing, "no casilla declares a continuidad_id; the continuity exemption below would be vacuous"
    return backing


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


def _key_echo_offenders(flat_leaves: dict[str, str | None]) -> list[str]:
    """Return keys whose value is the key itself — the scaffold placeholder.

    Whitespace-normalised, and tolerant of trailing punctuation, so one
    stray character cannot convert a placeholder into "authored".
    """

    offenders: list[str] = []
    for key, value in flat_leaves.items():
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped == key or stripped.rstrip(".:").rstrip() == key:
            offenders.append(key)
    return sorted(offenders)


def _blank_offenders(flat_leaves: dict[str, str | None]) -> list[str]:
    """Return keys whose value is empty or whitespace-only."""

    return sorted(key for key, value in flat_leaves.items() if isinstance(value, str) and not value.strip())


def _reserved_token_offenders(flat_leaves: dict[str, str | None]) -> list[str]:
    """Return keys whose value carries a token tr() can never interpolate.

    ``tr()`` consumes ``locale`` and ``default`` as rendering directives and
    strips them from the interpolation map, so a catalogue token named after
    either is permanently unfillable regardless of what a call site passes.
    """
    from dev.locales import RESERVED_INTERPOLATION_TOKENS

    from ..core.i18n import extract_placeholders

    return sorted(
        key
        for key, value in flat_leaves.items()
        if isinstance(value, str) and extract_placeholders(value) & RESERVED_INTERPOLATION_TOKENS
    )


def test_no_catalogue_value_carries_a_reserved_interpolation_token() -> None:
    """No locale value may name a tr() rendering directive as a placeholder.

    Such a token can never bind, so the value looks authored while being
    structurally broken. There is no allowlist and no ratchet: the shipped
    count is zero and must stay zero.
    """

    failures: list[str] = []
    for locale_code in ("ca", "en", "es", "hu"):
        leaves = _catalogue_leaves(locale_code)
        offenders = _reserved_token_offenders(leaves)
        if offenders:
            failures.append(
                f"{locale_code}.yml carries {len(offenders)} value(s) with a reserved interpolation "
                f"token (locale/default) that tr() can never fill. Rename the token (e.g. "
                f"locale_code) in the value AND the call site. Keys: {offenders[:5]}"
            )

    assert failures == [], "\n".join(failures)


def test_key_echo_offender_detection_discriminates() -> None:
    """The echo detector fires on injected echo variants and stays quiet otherwise."""

    assert _key_echo_offenders({"a.b": "a.b", "c.d": "translated"}) == ["a.b"]
    assert _key_echo_offenders({"a.b": "a.b ", "c.d": "a.b."}) == ["a.b"]
    assert _key_echo_offenders({"c.d": "c.d."}) == ["c.d"]
    assert _key_echo_offenders({"c.d": "translated"}) == []
    assert _blank_offenders({"a.b": "", "c.d": "  ", "e.f": "x"}) == ["a.b", "c.d"]


def test_key_echo_count_matches_the_pinned_ceiling() -> None:
    """The committed echo ceiling must equal the observed count, both ways.

    A value equal to its own dotted key is the scaffold's "no translation
    yet" marker leaking into a shipped catalogue. It is never legitimate,
    so there is no per-key allowlist; the ``_key_echo_ceiling`` metadata
    field in ``_intentional_identical.json`` is a pinned statement of the
    current debt (a missing field means zero). Equality is enforced in
    BOTH directions: clearing echoes forces the ceiling down in the same
    change, and new echoes require an explicit, reviewable ceiling raise
    — shrink-only by structure, not by convention.
    """

    failures: list[str] = []
    for locale_code in ("ca", "en", "es", "hu"):
        leaves = _catalogue_leaves(locale_code)
        offenders = _key_echo_offenders(leaves)
        ceiling = _load_metadata_ceiling(locale_code, "_key_echo_ceiling") or 0
        if len(offenders) < ceiling:
            failures.append(
                f"{locale_code}.yml has {len(offenders)} key-echo value(s) but the pinned ceiling is "
                f"{ceiling}: the debt shrank, so lower (or remove) '_key_echo_ceiling' in "
                f"_intentional_identical.json in this same change."
            )
        elif len(offenders) > ceiling:
            failures.append(
                f"{locale_code}.yml carries {len(offenders)} key-echo value(s) against a pinned ceiling "
                f"of {ceiling}. A key-echo is the scaffold placeholder, never a translation; author the "
                f"value via `python -m dev.locales set`. First five: {offenders[:5]}"
            )

    assert failures == [], "\n".join(failures)


def test_no_catalogue_value_is_blank() -> None:
    """No locale value may be empty or whitespace-only.

    A blank leaf reads as present to a membership check while rendering
    nothing to the operator. The CLI refuses to write one, so the shipped
    count is zero and must stay zero — no allowlist, no ratchet.
    """

    failures: list[str] = []
    for locale_code in ("ca", "en", "es", "hu"):
        leaves = _catalogue_leaves(locale_code)
        offenders = _blank_offenders(leaves)
        if offenders:
            failures.append(
                f"{locale_code}.yml carries {len(offenders)} blank value(s). Author the value via "
                f"`python -m dev.locales set`, or remove the key. Keys: {offenders[:5]}"
            )

    assert failures == [], "\n".join(failures)


def test_modelo_spanish_values_are_authority_source() -> None:
    """Every enrolled Modelo key resolves to one non-blank Spanish source value.

    A null occurrence value is NOT automatically an offender.
    :func:`~cadrumo.domain.calculations.registry._modelo_localization.resolve_modelo_localization`
    advances on the absence of a VALUE and carries the casilla's continuity key
    in the same chain, so a casilla whose ``continuidad_id`` has a populated
    continuity label already renders correct Spanish. Demanding a value on the
    occurrence key too would force a second copy of text that already has one
    curated home, and the next edit to the continuity label would silently not
    change what renders.

    What stays sharp is the other half: a null with NO continuity backing --
    no ``continuidad_id``, or one whose continuity label is itself blank --
    renders nothing, and still fails here.
    """

    es_keys = _catalogue_leaves("es")
    backing = _continuity_backing()
    offenders = sorted(
        key
        for key, value in es_keys.items()
        if _is_modelo_source_key(key)
        and (not isinstance(value, str) or not value.strip())
        and not (
            (continuity_key := backing.get(key)) is not None
            and isinstance(fallback := es_keys.get(continuity_key), str)
            and fallback.strip()
        )
    )
    assert offenders == [], (
        f"es.yml is the mandatory official Modelo source; these schema leaves are blank AND have no "
        f"populated continuity label to fall back to, so they render nothing: {offenders[:10]}"
    )


def test_translated_values_differ_from_canonical_source_unless_allowlisted() -> None:
    """Generic values differ from English; Modelo values differ from Spanish.

    When the wholesale ``untranslated_pending`` bucket is active, the test
    acts as a ratchet: the number of identical-source keys must not exceed
    the ``_untranslated_ceiling`` stored in the allowlist.  This prevents
    regressions that add new untranslated strings while the bulk translation
    work is in progress.

    To lower the ratchet after a translation pass: update
    ``_untranslated_ceiling`` in ``_intentional_identical.json`` to the new
    (lower) observed count.
    """
    allowlist = _load_allowlist()
    en_keys = _catalogue_leaves("en")
    es_keys = _catalogue_leaves("es")
    failures: list[str] = []

    for locale_code in ("ca", "es", "hu"):
        locale_allows = allowlist.get(locale_code, set())
        locale_keys = _catalogue_leaves(locale_code)

        offenders_by_source: dict[str, list[str]] = {}
        for key, en_value in en_keys.items():
            locale_value = locale_keys.get(key)
            if not isinstance(locale_value, str):
                continue
            if key.startswith(_MODELO_SCHEMA_PREFIX):
                # Spanish is the authority source for the schema. Its own
                # value is never an untranslated translation, and absent
                # non-Spanish values deliberately resolve to it at runtime.
                if locale_code == "es":
                    continue
                source_label = "es.yml"
                source_value = es_keys.get(key)
            else:
                source_label = "en.yml"
                source_value = en_value
            if not isinstance(source_value, str) or locale_value != source_value or key in locale_allows:
                continue
            offenders_by_source.setdefault(source_label, []).append(key)

        for source_label, offenders in offenders_by_source.items():
            failure = _identical_to_source_failure(
                locale_code,
                source_label,
                offenders,
                bucket_active="untranslated_pending" in locale_allows,
            )
            if failure is not None:
                failures.append(failure)

    assert failures == [], "\n".join(failures)


def _identical_to_source_failure(
    locale_code: str,
    source_label: str,
    offenders: list[str],
    *,
    bucket_active: bool,
) -> str | None:
    """Render one locale's identical-source verdict, or ``None`` when clean.

    Wholesale-bucket mode enforces the ratchet ceiling instead of requiring
    per-key allowlist entries; a regression that adds new untranslated
    strings pushes the count over the ceiling.
    """

    if not bucket_active:
        if not offenders:
            return None
        return (
            f"{locale_code}.yml carries {len(offenders)} value(s) identical to {source_label} without an "
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
            f"{locale_code}.yml has {len(offenders)} key(s) identical to {source_label}, "
            f"exceeding the ratchet ceiling of {ceiling}. "
            f"New untranslated keys (first five of overflow): {offenders[ceiling:][:5]}"
        )
    return None
