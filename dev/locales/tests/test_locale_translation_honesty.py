"""Structural honesty assertions for the shared locale catalogues."""

from __future__ import annotations

import tomllib
from enum import StrEnum
from functools import cache
from typing import NamedTuple

import pytest

from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_continuity_locale_key,
    casilla_occurrence_locale_key,
)

from .._paths import LOCALES_DIR, SRC_DIR
from ..manager import LocaleManager, locale_catalogue_source

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_MODELO_SCHEMA_PREFIX = "modelo.schema."
_MODELO_SOURCE_SUFFIXES = (".label", ".title", ".official_name")


def test_runtime_locale_root_contains_no_development_metadata() -> None:
    """The shipped locale root contains catalogues, not audit dispositions."""

    assert list(LOCALES_DIR.glob("*.json")) == []


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
    source = locale_catalogue_source(LOCALES_DIR, locale_code)
    assert source is not None, f"no committed catalogue for {locale_code!r}; every honesty gate over it is vacuous"
    raw = LocaleManager(src_dir=SRC_DIR, locales_dir=LOCALES_DIR).load_locale(source)
    leaves = _flatten(raw if isinstance(raw, dict) else {})
    assert leaves, f"catalogue {locale_code!r} flattened to no leaves; every honesty gate over it is vacuous"
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
    :func:`~cadrumo.domain.calculations.registry.modelo_localization._localised_casilla`:
    read ``id`` and ``continuidad_id`` off the raw casilla table and derive both
    keys with the same two canonical encoders.

    Returns:
        ``{occurrence_label_key: continuity_label_key}`` for every casilla that
        declares a ``continuidad_id``. A casilla without one is simply absent,
        which is what makes its null occurrence value a real offender.
    """
    backing: dict[str, str] = {}
    modelos_dir = SRC_DIR / "_data" / "registry" / "aeat" / "modelos"
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
                backing[
                    casilla_occurrence_locale_key(modelo_id, revision_id, casilla_id, ModeloLocalizationFieldKind.LABEL)
                ] = casilla_continuity_locale_key(modelo_id, continuidad_id, ModeloLocalizationFieldKind.LABEL)
    assert backing, "no casilla declares a continuidad_id; the continuity exemption below would be vacuous"
    return backing


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
    from cadrumo.core.i18n.render import extract_placeholders

    from .._status import RESERVED_INTERPOLATION_TOKENS

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


def test_no_catalogue_value_echoes_its_key() -> None:
    """A key-echo is a scaffold placeholder and the exact target is zero."""

    failures: list[str] = []
    for locale_code in ("ca", "en", "es", "hu"):
        leaves = _catalogue_leaves(locale_code)
        offenders = _key_echo_offenders(leaves)
        if offenders:
            failures.append(
                f"{locale_code}.yml carries {len(offenders)} key-echo value(s). "
                f"A key-echo is the scaffold placeholder, never a translation; author the "
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
    :func:`~cadrumo.domain.calculations.registry.modelo_localization.resolve_modelo_localization`
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


_TRANSLATED_LOCALES = ("ca", "en", "hu")


class IdenticalTranslationClass(StrEnum):
    """Why a translated casilla label may legitimately equal its Spanish source."""

    SHARED_WORD = "shared_word"
    """The target language spells the correct term exactly as Spanish does."""
    ACRONYM = "acronym"
    """The label is dominated by an official acronym the product keeps untranslated."""


class IdenticalTranslation(NamedTuple):
    """One classified, reviewed exception to the copied-source rule."""

    classification: IdenticalTranslationClass
    reason: str


# Keyed per (locale, continuity label key). Never widened by modelo, prefix or count:
# each entry is a translation a reviewer checked and found correct as written.
_LEGITIMATE_IDENTICAL_CONTINUITY_LABELS: dict[tuple[str, str], IdenticalTranslation] = {
    ("ca", "modelo.schema.100.casilla.continuidad.irpf-deduccion-vehiculo-matricula.label"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD, "Catalan for a vehicle registration plate is also 'Matrícula'."
    ),
    ("ca", "modelo.schema.131.casilla.continuidad.irpf-pf-modulos-total.label"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD, "Catalan 'Total' is the same word as the Spanish."
    ),
    ("en", "modelo.schema.131.casilla.continuidad.irpf-pf-modulos-total.label"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD, "English 'Total' is the same word as the Spanish."
    ),
    ("ca", "modelo.schema.180.casilla.continuidad.payee-nif.label"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        "NIF stays untranslated and 'del perceptor' is the correct Catalan, as the catalogue renders it elsewhere.",
    ),
}


def _is_continuity_label_key(key: str) -> bool:
    """Return whether ``key`` is a casilla continuity LABEL key.

    Structural rather than registry-derived so the gate also sees a continuity
    entry no current casilla declares. Encoded segments never carry a dot, so
    the split is exact: ``modelo.schema.<modelo>.casilla.continuidad.<id>.label``.
    """
    parts = key.split(".")
    return (
        len(parts) == 7
        and parts[:2] == ["modelo", "schema"]
        and parts[3:5] == ["casilla", "continuidad"]
        and parts[6] == ModeloLocalizationFieldKind.LABEL
    )


def _continuity_label_offenders(
    source_leaves: dict[str, str | None],
    target_leaves: dict[str, str | None],
    *,
    locale_code: str,
    backing: dict[str, str],
    allowlist: dict[tuple[str, str], IdenticalTranslation],
) -> tuple[list[str], list[str]]:
    """Return ``(copied, stranded)`` continuity label keys for one translated locale.

    A continuity label is the lineage-wide tier of the label chain: an inherited
    casilla row with no occurrence text of its own lands on it. Two states make
    that tier render Spanish to a non-Spanish reader:

    * copied -- the value IS the Spanish source, which reads as translated to a
      presence check while giving the reader nothing. Only a classified per-key
      allowlist entry excuses it.
    * stranded -- the value is unfilled although one of the lineage's occurrence
      keys already carries a translation in this locale. The translation exists;
      only the rows that fall through to the continuity tier miss it.

    A lineage with no translation at ANY tier is a coverage gap of a different
    kind and is not judged here.
    """
    translated_lineages = {
        continuity_key
        for occurrence_key, continuity_key in backing.items()
        if isinstance(value := target_leaves.get(occurrence_key), str) and value.strip()
    }
    copied: list[str] = []
    stranded: list[str] = []
    for key, source in source_leaves.items():
        if not _is_continuity_label_key(key) or not isinstance(source, str) or not source.strip():
            continue
        target = target_leaves.get(key)
        if isinstance(target, str) and target.strip():
            if target.strip() == source.strip() and (locale_code, key) not in allowlist:
                copied.append(key)
        elif key in translated_lineages:
            stranded.append(key)
    return sorted(copied), sorted(stranded)


def test_continuity_label_detector_discriminates() -> None:
    """A planted copy and a planted stranded entry fire against the real catalogue.

    The detector runs over the shipped ``en`` catalogue with one continuity
    label replaced by its Spanish source and one reset to null, so this proves
    teeth on real key shapes and a real registry backing, not on a toy mapping.
    """
    source = _catalogue_leaves("es")
    target = _catalogue_leaves("en")
    backing = _continuity_backing()
    lineages = sorted(
        {
            continuity_key
            for occurrence_key, continuity_key in backing.items()
            if continuity_key.startswith("modelo.schema.303.")
            and isinstance(target.get(occurrence_key), str)
            and isinstance(target.get(continuity_key), str)
            and isinstance(source.get(continuity_key), str)
        }
    )
    assert len(lineages) >= 2, "modelo 303 carries no translated continuity lineage to plant a defect in"
    planted_copy, planted_null = lineages[0], lineages[1]

    clean_copied, clean_stranded = _continuity_label_offenders(
        source, target, locale_code="en", backing=backing, allowlist=_LEGITIMATE_IDENTICAL_CONTINUITY_LABELS
    )
    assert planted_copy not in clean_copied
    assert planted_null not in clean_stranded

    target[planted_copy] = source[planted_copy]
    target[planted_null] = None
    copied, stranded = _continuity_label_offenders(
        source, target, locale_code="en", backing=backing, allowlist=_LEGITIMATE_IDENTICAL_CONTINUITY_LABELS
    )
    assert planted_copy in copied
    assert planted_null in stranded

    excused, _ = _continuity_label_offenders(
        source,
        target,
        locale_code="en",
        backing=backing,
        allowlist={("en", planted_copy): IdenticalTranslation(IdenticalTranslationClass.SHARED_WORD, "planted")},
    )
    assert planted_copy not in excused
    assert _is_continuity_label_key("modelo.schema.303.casilla.continuidad.dr303-01.label")
    assert not _is_continuity_label_key("modelo.schema.303.casilla.continuidad.dr303-01.help")
    assert not _is_continuity_label_key("modelo.schema.303.revision.2024.casilla.01.label")


def test_continuity_labels_are_translated_not_copied() -> None:
    """No translated locale may render a continuity label as the Spanish source."""

    source = _catalogue_leaves("es")
    backing = _continuity_backing()
    failures: list[str] = []
    for locale_code in _TRANSLATED_LOCALES:
        copied, stranded = _continuity_label_offenders(
            source,
            _catalogue_leaves(locale_code),
            locale_code=locale_code,
            backing=backing,
            allowlist=_LEGITIMATE_IDENTICAL_CONTINUITY_LABELS,
        )
        if copied:
            failures.append(
                f"{locale_code}: {len(copied)} continuity label(s) copy the Spanish source. Translate them via "
                f"`python -m dev.locales set-batch`, or classify a genuinely identical term per key. "
                f"First five: {copied[:5]}"
            )
        if stranded:
            failures.append(
                f"{locale_code}: {len(stranded)} continuity label(s) are unfilled although their lineage is "
                f"translated, so inherited rows render Spanish. First five: {stranded[:5]}"
            )
    assert failures == [], "\n".join(failures)


def test_identical_translation_allowlist_is_live() -> None:
    """Every allowlist entry still names a continuity label that equals its Spanish source.

    An entry whose label was since retranslated, or whose key vanished, would
    otherwise sit silently ready to excuse a future copy.
    """
    source = _catalogue_leaves("es")
    stale: list[str] = []
    for (locale_code, key), entry in _LEGITIMATE_IDENTICAL_CONTINUITY_LABELS.items():
        target = _catalogue_leaves(locale_code).get(key)
        if not entry.reason.strip() or not _is_continuity_label_key(key):
            stale.append(f"{locale_code}:{key} (malformed entry)")
        elif not isinstance(target, str) or target != source.get(key):
            stale.append(f"{locale_code}:{key} (no longer identical to the Spanish source)")
    assert stale == [], f"remove stale identical-translation allowlist entries: {stale}"
