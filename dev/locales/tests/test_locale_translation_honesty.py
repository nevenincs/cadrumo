"""Structural honesty assertions for the shared locale catalogues."""

from __future__ import annotations

from enum import StrEnum
from functools import cache
from typing import NamedTuple

import pytest

from cadrumo.core.toml import TomlDecodeError, parse_toml
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    casilla_continuity_locale_key,
    casilla_occurrence_locale_key,
    modelo_localization_source,
)

from .._paths import LOCALES_DIR, SRC_DIR
from ..manager import LocaleManager, locale_catalogue_source
from ..modelo_casilla_catalogue import ModeloCasillaCatalogue

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
    leaves = _flatten(raw)
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
            document = parse_toml(casilla_file.read_text(encoding="utf-8"))
        except (OSError, TomlDecodeError):  # pragma: no cover - unreadable fragment
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


# Keyed per (locale, Spanish label text): whether a translation may equal its source is a
# property of the wording, not of the key that happens to store it. Never widened by modelo,
# prefix or count: each entry is a translation a reviewer checked and found correct as written.
_LEGITIMATE_IDENTICAL_TRANSLATIONS: dict[tuple[str, str], IdenticalTranslation] = {
    ("ca", "1. Divisa"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "“Divisa” (currency) is the established Catalan term, spelled identically to the Spanish "
            "(used elsewhere in the same schema); the leading numbering is kept as in the Spanish."
        ),
    ),
    ("ca", "1. Indicador de simplificada"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "“Indicador de simplificada” is spelled identically in Catalan; the leading numbering is "
            "kept as in the Spanish."
        ),
    ),
    ("ca", "1. NIF del perceptor"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        (
            "NIF is a universal acronym and “del perceptor” is spelled identically in Catalan; the "
            "leading numbering is kept as in the Spanish."
        ),
    ),
    ("ca", "1. Prorrata %"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "“Prorrata” is the established Catalan IVA term, spelled identically to the Spanish (e.g. "
            "“IVA. Prorrata i sectors diferenciats”); the leading numbering and percent sign are kept "
            "as in the Spanish."
        ),
    ),
    ("ca", "2. Divisa"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "“Divisa” (currency) is the established Catalan term, spelled identically to the Spanish; "
            "the leading numbering is kept as in the Spanish."
        ),
    ),
    ("ca", "2. Indicador de simplificada"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "“Indicador de simplificada” is spelled identically in Catalan; the leading numbering is "
            "kept as in the Spanish."
        ),
    ),
    ("ca", "2. Prorrata %"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "“Prorrata” is the established Catalan IVA term, spelled identically to the Spanish; the "
            "leading numbering and percent sign are kept as in the Spanish."
        ),
    ),
    ("ca", "47 - Número de casa."): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        "“Número de casa” is spelled identically in Catalan; the numbering and punctuation are kept as in the Spanish.",
    ),
    ("ca", "50 - Portal."): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "“Portal” (building entrance) is spelled identically in Catalan; the numbering and "
            "punctuation are kept as in the Spanish."
        ),
    ),
    ("ca", "52 - Planta."): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        "“Planta” (floor) is spelled identically in Catalan; the numbering and punctuation are kept as in the Spanish.",
    ),
    ("ca", "Base liquidable general"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "“Base liquidable general” is the established Catalan AEAT term, spelled identically to the"
            " Spanish (used throughout the Catalan schema, e.g. “base liquidable general negativa...”)."
        ),
    ),
    ("ca", "Base total"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD, "“Base” and “total” are spelled identically in Catalan and Spanish."
    ),
    ("ca", "Ceuta o Melilla"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        "“Ceuta o Melilla” (the place names and the conjunction “o”) is spelled identically in Catalan.",
    ),
    ("ca", "Cooperativa protegida [00017]"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        "“Cooperativa protegida” is spelled identically in Catalan; the box suffix is kept as in the Spanish.",
    ),
    ("ca", "Gran empresa [00023]"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        "“Gran empresa” is spelled identically in Catalan; the box suffix is kept as in the Spanish.",
    ),
    ("ca", "IBAN (10)"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        (
            "IBAN is a universal international banking acronym, unchanged across languages; the "
            "footnote number is kept as in the Spanish."
        ),
    ),
    ("ca", "Matrícula"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD, "“Matrícula” is spelled identically in Catalan and Spanish."
    ),
    ("ca", "NIF"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM, "NIF is a universal AEAT acronym, unchanged across languages."
    ),
    ("ca", "NIF DEL PAGADOR ANTERIOR"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        (
            "NIF is a universal acronym and “del pagador anterior” is spelled identically in Catalan; "
            "capitalisation is kept as in the Spanish."
        ),
    ),
    ("ca", "NIF DEL PERCEPTOR"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        (
            "NIF is a universal acronym and “del perceptor” is spelled identically in Catalan; "
            "capitalisation is kept as in the Spanish."
        ),
    ),
    ("ca", "NIF del perceptor"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        "NIF is a universal acronym and “del perceptor” is spelled identically in Catalan.",
    ),
    ("ca", "NIF del productor 1"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        "NIF is a universal acronym and “del productor 1” is spelled identically in Catalan.",
    ),
    ("ca", "NIF del productor 2"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        "NIF is a universal acronym and “del productor 2” is spelled identically in Catalan.",
    ),
    ("ca", "NIF del productor 3"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        "NIF is a universal acronym and “del productor 3” is spelled identically in Catalan.",
    ),
    ("ca", "NIF del promotor o constructor:"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        "NIF is a universal acronym and “del promotor o constructor” is spelled identically in Catalan.",
    ),
    ("ca", "NIF/NIE 1"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM, "NIF and NIE are universal AEAT acronyms, unchanged across languages."
    ),
    ("ca", "NIF/NIE 3"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM, "NIF and NIE are universal AEAT acronyms, unchanged across languages."
    ),
    ("ca", "NIF/NIE 4"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM, "NIF and NIE are universal AEAT acronyms, unchanged across languages."
    ),
    ("ca", "Número de casa [29]"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        "“Número de casa” is spelled identically in Catalan; the box suffix is kept as in the Spanish.",
    ),
    ("ca", "PERCEPTOR MEDIADOR"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        "“Perceptor” and “mediador” are spelled identically in Catalan; capitalisation is kept as in the Spanish.",
    ),
    ("ca", "Pagador. NIF [50]"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        (
            "“Pagador” is spelled identically in Catalan and NIF is a universal acronym; the box suffix"
            " is kept as in the Spanish."
        ),
    ),
    ("ca", "Planta [34]"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        "“Planta” is spelled identically in Catalan; the box suffix is kept as in the Spanish.",
    ),
    ("ca", "Portal [32]"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        "“Portal” is spelled identically in Catalan; the box suffix is kept as in the Spanish.",
    ),
    (
        "ca",
        (
            "Suma ( [0181] a [0194] + [0198] a [0200] + [0202] + [0203] + [0205] + [0206] + [0208] + "
            "[0227] + [0214] a [0217] )"
        ),
    ): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "“Suma” (sum) is spelled identically in Catalan and Spanish; the rest of the label is only "
            "box-reference codes, kept unchanged."
        ),
    ),
    ("ca", "Total"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD, "“Total” is spelled identically in Catalan and Spanish."
    ),
    ("en", "IBAN (10)"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        (
            "IBAN is a universal international banking acronym, unchanged across languages; the "
            "footnote number is kept as in the Spanish."
        ),
    ),
    ("en", "Modelo"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "The product keeps the AEAT form designation “Modelo” untranslated as an established domain"
            " term, matching usage elsewhere in the English schema (e.g. “Modelo 190”)."
        ),
    ),
    ("en", "SOCIMI [00012]"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        (
            "SOCIMI is a universal Spanish REIT-regime acronym, unchanged across languages; the box "
            "suffix is kept as in the Spanish."
        ),
    ),
    ("en", "Total"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD, "“Total” is spelled identically in English and Spanish."
    ),
    ("hu", "IBAN (10)"): IdenticalTranslation(
        IdenticalTranslationClass.ACRONYM,
        (
            "IBAN is a universal international banking acronym, unchanged across languages; the "
            "footnote number is kept as in the Spanish."
        ),
    ),
    ("hu", "Modelo"): IdenticalTranslation(
        IdenticalTranslationClass.SHARED_WORD,
        (
            "The product keeps the AEAT form designation “Modelo” untranslated as an established domain"
            " term, matching usage elsewhere in the Hungarian schema (e.g. “Modelo 190 adóév 2024”)."
        ),
    ),
}


@cache
def _casilla_catalogue() -> ModeloCasillaCatalogue:
    """The shipped casilla surface as the runtime resolves it."""
    return ModeloCasillaCatalogue.published(LOCALES_DIR)


_NO_EXCUSES: dict[tuple[str, str], IdenticalTranslation] = {}
"""No stored copy is excused: an identical term is represented by the Spanish fallback."""


def _copied_offenders(
    catalogue: ModeloCasillaCatalogue,
    locale_code: str,
    allowlist: dict[tuple[str, str], IdenticalTranslation],
) -> list[str]:
    """Return the ``locale_code`` keys serving a label that merely repeats its Spanish text."""
    return sorted(
        key for key, text in catalogue.copied_translations(locale_code).items() if (locale_code, text) not in allowlist
    )


def test_copied_translation_detector_discriminates() -> None:
    """A planted Spanish copy fires and a classified one is excused, on real chains.

    The detector runs over the shipped catalogue with one served translation
    replaced by the Spanish text it renders, so this proves teeth on real key
    shapes and real resolution, not on a toy mapping.
    """
    shipped = _casilla_catalogue()
    values = {locale: dict(leaves) for locale, leaves in shipped.values.items()}
    lookup = shipped.lookup_for(values)
    planted = next(
        (source[0], spanish)
        for index, occurrence in enumerate(shipped.occurrences)
        if (spanish := shipped.resolve(index, "label", "es")) is not None
        and (source := modelo_localization_source(occurrence.chain("label"), locale="en", lookup=lookup)) is not None
        and source[1] == "en"
        and values["en"][source[0]] != spanish
    )
    key, spanish = planted
    values["en"][key] = spanish
    catalogue = ModeloCasillaCatalogue(shipped.occurrences, values)

    assert key not in _copied_offenders(shipped, "en", _LEGITIMATE_IDENTICAL_TRANSLATIONS)
    assert key in _copied_offenders(catalogue, "en", _LEGITIMATE_IDENTICAL_TRANSLATIONS)
    excused = {("en", spanish): IdenticalTranslation(IdenticalTranslationClass.SHARED_WORD, "planted")}
    assert key not in _copied_offenders(catalogue, "en", excused)


def test_casilla_labels_are_translated_not_copied() -> None:
    """No translated locale stores a casilla label that is only its Spanish text.

    A stored copy is never needed: the Spanish fallback renders the same text,
    and an identical term is classified in the allowlist instead.
    """
    catalogue = _casilla_catalogue()
    failures = [
        f"{locale_code}: {len(copied)} served label(s) copy the Spanish source. Translate them with "
        f"`python -m dev.locales casilla-author`, or classify a genuinely identical term. First five: {copied[:5]}"
        for locale_code in _TRANSLATED_LOCALES
        if (copied := _copied_offenders(catalogue, locale_code, _NO_EXCUSES))
    ]
    assert failures == [], "\n".join(failures)


def test_no_translated_lineage_leaves_a_row_in_spanish() -> None:
    """A row renders Spanish only when its lineage has no translation of that text at all."""
    catalogue = _casilla_catalogue()
    failures = [
        f"{locale_code}: {len(stranded)} row(s) render Spanish although their lineage translates that text; "
        f"run `python -m dev.locales casilla-collapse --apply` after carrying the translation. "
        f"First five: {stranded[:5]}"
        for locale_code in _TRANSLATED_LOCALES
        if (stranded := catalogue.stranded_translations(locale_code))
    ]
    assert failures == [], "\n".join(failures)


def _untranslated_texts(catalogue: ModeloCasillaCatalogue, locale_code: str) -> set[str]:
    """Return every Spanish label a row renders untranslated in ``locale_code``."""
    lookup = catalogue.lookup_for(catalogue.values)
    return {
        spanish
        for index, occurrence in enumerate(catalogue.occurrences)
        if (source := modelo_localization_source(occurrence.chain("label"), locale=locale_code, lookup=lookup))
        is not None
        and source[1] != locale_code
        and (spanish := catalogue.values[source[1]][source[0]]) is not None
    }


def test_every_untranslated_label_is_a_classified_identical_term() -> None:
    """A translated locale renders Spanish only for a term reviewed as spelled identically.

    An identical translation is not stored: it resolves to the same text through
    the Spanish fallback, so the catalogue keeps no copy. The review lives here.
    """
    catalogue = _casilla_catalogue()
    failures = [
        f"{locale_code}: {len(gaps)} Spanish label(s) render untranslated. Translate them with "
        f"`python -m dev.locales casilla-author`, or classify a genuinely identical term. First five: {gaps[:5]}"
        for locale_code in _TRANSLATED_LOCALES
        if (
            gaps := sorted(
                text
                for text in _untranslated_texts(catalogue, locale_code)
                if (locale_code, text) not in _LEGITIMATE_IDENTICAL_TRANSLATIONS
            )
        )
    ]
    assert failures == [], "\n".join(failures)


def test_identical_translation_allowlist_is_live() -> None:
    """Every allowlist entry still excuses a label some row renders untranslated.

    An entry whose label was since translated would otherwise sit silently
    ready to excuse a future gap.
    """
    catalogue = _casilla_catalogue()
    untranslated = {locale_code: _untranslated_texts(catalogue, locale_code) for locale_code in _TRANSLATED_LOCALES}
    stale = [
        f"{locale_code}:{spanish}"
        for (locale_code, spanish), entry in _LEGITIMATE_IDENTICAL_TRANSLATIONS.items()
        if not entry.reason.strip() or spanish not in untranslated.get(locale_code, set())
    ]
    assert stale == [], f"remove stale identical-translation allowlist entries: {stale}"
