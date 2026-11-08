"""Spelling segments for the authoritative locale audit."""

from __future__ import annotations

import re
from functools import lru_cache
from importlib.resources import files

from cadrumo.core.spanish_postcode import SPANISH_PROVINCE_CODES

from .signal_command_paths import command_path_pattern, registered_operation_id_pattern
from .signal_contracts import DictionaryLike
from .signal_policy import LOCALES
from .signal_syntax import (
    MODELO_FORM_RE,
    TRANSLATION_CLAVE_NAME_RE,
    TRANSLATION_HTML_LANGUAGE_RE,
    TRANSLATION_HUNGARIAN_DATE_RE,
    TRANSLATION_HUNGARIAN_HYPHENATED_SUFFIX_RE,
    TRANSLATION_HUNGARIAN_PERCENT_SUFFIX_RE,
    TRANSLATION_LEGAL_TITLE_RE,
    TRANSLATION_LITERAL_RE,
    TRANSLATION_MARKDOWN_LINK_CONTEXT_RE,
    TRANSLATION_RST_LINK_RE,
    TRANSLATION_SPANISH_AUTHORITY_RE,
    TRANSLATION_SPANISH_TAX_TERM_RE,
)
from .signal_tokens import (
    DESCENDANT_BOOL_CHOICES_RE,
    DESCENDANT_RELATION_CHOICES_RE,
    filtered_translation_text,
    translation_words,
)

# These exact Catalan pronoun forms are attested in the operator guides. Keep
# the verb visible and the set closed; arbitrary stems still need checking.
# https://aplicacions.llengua.gencat.cat/llc/AppJava/pdf/ortografia_catalana_versio_digital.pdf
_CATALAN_NE_VERB_FORMS = (
    "aconsegueix",
    "afegeix",
    "afegir",
    "aportar",
    "canviar",
    "començar",
    "configura",
    "configurar",
    "confirmar",
    "conservar",
    "consultar",
    "controlar",
    "conèixer",
    "crear",
    "declarar",
    "demostrant",
    "demostrar",
    "desar",
    "desbloquejar",
    "eliminar",
    "esborrar",
    "escriu",
    "gestionar",
    "indicar",
    "iniciar",
    "intentar",
    "introdueix",
    "introduint",
    "llegeix",
    "llegir",
    "obrir",
    "obtenir",
    "reduir",
    "registrar",
    "reobrir",
    "resol",
    "segueix",
    "seguir",
    "seleccionar",
    "suprimir",
    "tria",
    "triar",
)
CATALAN_HYPHENATED_CLITIC_RE = re.compile(
    r"(?<![\w-])(?P<form>[Mm]antén-(?:lo|los)|revisar-los|traçar-lo|"
    r"(?i:(?:" + "|".join(map(re.escape, _CATALAN_NE_VERB_FORMS)) + r")-ne))(?![\w-])"
)
# The export/VIES definitions and architecture/CLI guides retain these
# complete English standard, license and product names.
# Route each word to English rather than exempting its spelling.
# https://csrc.nist.gov/glossary/term/hash_based_message_authentication_code
# https://cloud.google.com/products
# https://workspace.google.com/products/sheets/
# https://developer.apple.com/documentation/apple-silicon
# https://developer.apple.com/help/account/certificates/create-developer-id-certificates
# https://www.apache.org/licenses/LICENSE-2.0.html
# https://learn.microsoft.com/en-us/connectors/excelonlinebusiness/
_ENGLISH_REFERENCE_NAME_RE = re.compile(
    r"(?<!\w)(?:JSON Lines|VAT Information Exchange System|Model Context Protocol|"
    r"Portable Document Format|Open Financial Exchange|Advanced Encryption Standard|"
    r"Tom['’]s Obvious Minimal Language|hash-based message authentication code|"
    r"Google Cloud|Google Sheets?|Apple silicon|Apple Developer ID|Apache License|"
    r"Microsoft Excel Open XML)(?!\w)"
)
# Fact 0129-renta-ccaa-tax-residence-catalogue owns these region identities;
# profile/schema and
# wizard choices supply their reviewed English/Hungarian display variants.
# Validate complete names only on those typed choice-label surfaces. Their
# individual words are not vocabulary exceptions elsewhere.
_RESIDENCE_REGION_LABELS: dict[str, dict[str, tuple[str, ...]]] = {
    "en": {
        "cantabria": ("Cantabria",),
        "castilla_la_mancha": ("Castilla-La Mancha", "Castile-La Mancha"),
        "castilla_y_leon": ("Castilla y León", "Castile and León"),
        # The two ciudades autónomas keep their Spanish proper names, which the
        # English dictionary does not carry; the gloss names what they are.
        "ceuta": ("Ceuta (autonomous city)",),
        "comunidad_valenciana": ("Valencian Community",),
        "extremadura": ("Extremadura",),
        "galicia": ("Galicia",),
        "la_rioja": ("La Rioja",),
        "melilla": ("Melilla (autonomous city)",),
    },
    "hu": {
        # The European Commission's Hungarian regional designations:
        # https://fish-commercial-names.ec.europa.eu/fish-names/commercial-designations_hu?ms=ES&msLang=es&page=12&rows=100&s=1&v=1
        "asturias": ("Asztúria",),
        "cantabria": ("Kantábria",),
        "castilla_la_mancha": ("Kasztília-La Mancha",),
        # The two ciudades autónomas keep their Spanish proper names, which the
        # Hungarian dictionary does not carry; the gloss names what they are.
        "ceuta": ("Ceuta (autonóm város)",),
        "extremadura": ("Extremadura",),
        "galicia": ("Galicia",),
        "la_rioja": ("La Rioja",),
        "melilla": ("Melilla (autonóm város)",),
        # https://eur-lex.europa.eu/legal-content/HU/TXT/?uri=CELEX%3A02003D0467-20210101
        "murcia": ("Murcia",),
    },
    "es": {
        # The autonomous community's own official name:
        # https://www.juntadeandalucia.es/organismos/transparencia/informacion-juridica/estatuto.html
        "andalucia": ("Andalucía",),
    },
}
_RESIDENCE_REGION_LABEL_KEY_RE = re.compile(
    r"(?:profile\.schema\.field\.tax_residence\.ccaa\.choices\.(?P<profile>[a-z_]+)|"
    r"wizard\.setup\.residence\.ccaa\.choices\.(?P<wizard>[a-z_]+)\.label)\Z"
)


def is_known_residence_region_label(locale: str, key: str, value: str) -> bool:
    """Validate one complete regional proper name under its declared choice."""
    match = _RESIDENCE_REGION_LABEL_KEY_RE.fullmatch(key)
    if match is None:
        return False
    region = match.group("profile") or match.group("wizard")
    return value in _RESIDENCE_REGION_LABELS.get(locale, {}).get(region, ())


_PROVINCE_CHOICE_KEY_RE = re.compile(r"application\.modelo\.edit_choice\.province_code\.(\d{2})\Z")
_PROVINCE_TABLE_START = "del domicilio fiscal del declarado según la relación siguiente:\n"
_PROVINCE_TABLE_END = (
    "En el caso de no residentes que no operen en territorio español mediante establecimiento permanente, "
    "se consignará 99."
)


def official_province_labels_from_table(source: str) -> dict[str, str]:
    """Read the complete code/name table from the bundled official record design."""
    if source.count(_PROVINCE_TABLE_START) != 1 or source.count(_PROVINCE_TABLE_END) != 1:
        raise ValueError("official province table boundaries are missing or ambiguous")
    table = source.split(_PROVINCE_TABLE_START, 1)[1].split(_PROVINCE_TABLE_END, 1)[0]
    lines = table.splitlines()
    if len(lines) != 2 * len(SPANISH_PROVINCE_CODES):
        raise ValueError("official province table has an unexpected number of rows")
    labels = dict(zip(lines[1::2], lines[::2], strict=True))
    if (
        set(labels) != set(SPANISH_PROVINCE_CODES)
        or len(set(labels.values())) != len(labels)
        or any(not label.strip() or label != label.strip() for label in labels.values())
    ):
        raise ValueError("official province table has invalid or duplicate entries")
    return labels


@lru_cache(maxsize=1)
def _official_province_labels() -> dict[str, str]:
    """Load the same official source that governs the edit-choice vocabulary."""
    source = (
        files("cadrumo")
        .joinpath("_data", "corpus", "normatives", "html", "orden-eha-3481-2008.html.extracted.md")
        .read_text(encoding="utf-8")
    )
    return official_province_labels_from_table(source)


def is_known_official_province_label(key: str, value: str) -> bool:
    """Recognize only the complete official label for its actual province code."""
    match = _PROVINCE_CHOICE_KEY_RE.fullmatch(key)
    return match is not None and _official_province_labels().get(match.group(1)) == value


# These are attested Hungarian endings on structural stems, not a productive
# suffix rule for ordinary words. Keep acronym/endings paired; e.g. admitting
# PDF-jét must not silently admit an arbitrary word followed by -jét.
_HUNGARIAN_STRUCTURAL_SUFFIX_PATTERNS = tuple(
    re.compile(r"(?<![\w-])" + pattern + r"(?![\w-])")
    for pattern in (
        r"(?<!`)(?P<stem>``[^`\r\n]+``|`[^`\r\n]+`)-(?:ból|ből|tól|től|ig|vel|nek|et|on|ra|tel|re|nak)",
        r"(?P<stem>IVA)-(?:jának|jával)",
        r"(?P<stem>PDF)-(?:jét|jének|jével|ekről)",
        r"(?P<stem>CSV)-(?:je|jével)",
        r"(?P<stem>JSON)-ját",
        r"(?P<stem>DEK)-jével",
        r"(?P<stem>HANDLE)-öket",
        r"(?P<stem>IGIC|IPSI)-jére",
        r"(?P<stem>UUID)-jával",
        r"(?P<stem>NIF)-(?:jét|jének|jüket)",
        r"(?P<stem>NIE)-jüket",
        # A case ending on the complete, official regional tax-authority name.
        # https://gobiernoabierto.navarra.es/es/transparencia/convenio-economico
        r"(?P<stem>Hacienda[ \t]+Foral)nál",
        r"(?P<stem>URL)-jét",
        r"(?P<stem>Cl@ve)-vel",
        # AEAT's exact service name with the attested Hungarian allative;
        # preserve the stem so its own exact-name recognizer still checks it.
        # https://www3.agenciatributaria.gob.es/Sede/clave.html
        # https://www.helyesiras.mta.hu/helyesiras/default/akh12
        r"(?P<stem>Cl@ve[ \t]+Móvil)hoz",
        r"(?P<stem>GitHub)on",
        r"(?P<stem>PowerShell)ben",
        r"(?P<stem>Model[ \t]+Context[ \t]+Protocol)t",
        r"(?P<stem>Modelo[ \t]+\d{1,4}|\*\*Modelo[ \t]+\d{1,4}\*\*)-(?:et|ban)",
        r"(?P<stem>\d{4}-\d{2}-\d{2})-tól",
        r"(?P<stem>1)-jén",
        r"(?P<stem>\{expected\})-nek",
    )
)


def hungarian_suffix_spelling_text(value: str) -> tuple[str, int]:
    """Mask attested endings while retaining every stem and its source offsets."""
    masked = list(value)
    ranges: set[tuple[int, int]] = set()
    foreign_ranges = tuple(
        (match.start(), match.end())
        for match in TRANSLATION_HTML_LANGUAGE_RE.finditer(value)
        if match.group("locale").casefold() != "hu"
    )
    for pattern in (TRANSLATION_HUNGARIAN_HYPHENATED_SUFFIX_RE, *_HUNGARIAN_STRUCTURAL_SUFFIX_PATTERNS):
        for match in pattern.finditer(value):
            start, end = match.end("stem"), match.end()
            if any(start < foreign_end and foreign_start < end for foreign_start, foreign_end in foreign_ranges):
                continue
            if (start, end) not in ranges:
                masked[start:end] = [" "] * (end - start)
                ranges.add((start, end))
    return "".join(masked), len(ranges)


def html_spelling_segments(value: str, foreign: list[tuple[int, int, str, str, int]]) -> None:
    """Html spelling segments."""
    for match in TRANSLATION_HTML_LANGUAGE_RE.finditer(value):
        language = match.group("locale").casefold()
        if language in LOCALES:
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    language,
                    match.group("body"),
                    filtered_translation_text(match.group(0))[1],
                )
            )


def markdown_link_spelling_segments(value: str, foreign: list[tuple[int, int, str, str, int]]) -> None:
    """Markdown link spelling segments."""
    for match in TRANSLATION_MARKDOWN_LINK_CONTEXT_RE.finditer(value):
        target = match.group("angle_target") or match.group("target") or ""
        if is_legal_authority_target(target) and is_spanish_legal_label(match.group("label")):
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    "es",
                    match.group("label"),
                    filtered_translation_text(match.group(0))[1],
                )
            )


def rst_link_spelling_segments(value: str, foreign: list[tuple[int, int, str, str, int]]) -> None:
    """Rst link spelling segments."""
    for match in TRANSLATION_RST_LINK_RE.finditer(value):
        if is_legal_authority_target(match.group("target")) and is_spanish_legal_label(match.group("label")):
            foreign.append(
                (
                    match.start(),
                    match.end(),
                    "es",
                    match.group("label"),
                    filtered_translation_text(match.group(0))[1],
                )
            )


def is_spanish_legal_label(label: str) -> bool:
    """Recognize Spanish official labels independently of their destination."""
    if TRANSLATION_HTML_LANGUAGE_RE.search(label):
        return False
    return bool(
        TRANSLATION_LEGAL_TITLE_RE.match(label.strip()) or TRANSLATION_SPANISH_AUTHORITY_RE.fullmatch(label.strip())
    )


def legal_title_spelling_segments(
    value: str, default_locale: str, foreign: list[tuple[int, int, str, str, int]]
) -> None:
    """Legal title spelling segments."""
    # A complete command is transport syntax. Extracting a Spanish word
    # such as "modelo" first would split its path before command masking.
    literal_ranges = tuple(
        (match.start(), match.end())
        for pattern in (
            TRANSLATION_LITERAL_RE,
            command_path_pattern(),
            registered_operation_id_pattern(),
            DESCENDANT_BOOL_CHOICES_RE,
            DESCENDANT_RELATION_CHOICES_RE,
        )
        for match in pattern.finditer(value)
    )
    for pattern in (
        MODELO_FORM_RE,
        TRANSLATION_LEGAL_TITLE_RE,
        TRANSLATION_SPANISH_AUTHORITY_RE,
        TRANSLATION_SPANISH_TAX_TERM_RE,
        TRANSLATION_CLAVE_NAME_RE,
    ):
        _append_legal_title_matches(value, pattern, default_locale, literal_ranges, foreign)


def _append_legal_title_matches(
    value: str,
    pattern: re.Pattern[str],
    default_locale: str,
    literal_ranges: tuple[tuple[int, int], ...],
    foreign: list[tuple[int, int, str, str, int]],
) -> None:
    """Route one family of complete legal names outside literal syntax."""
    for match in pattern.finditer(value):
        if any(start <= match.start() and match.end() <= end for start, end in literal_ranges):
            continue
        text = match.group(0)
        # Both names identify a numbered return, but "Form" is English.
        language = "en" if pattern is MODELO_FORM_RE and text.split(maxsplit=1)[0].casefold() == "form" else "es"
        if language == default_locale:
            continue
        foreign.append((match.start(), match.end(), language, text, filtered_translation_text(text)[1]))


def english_reference_spelling_segments(
    value: str, default_locale: str, foreign: list[tuple[int, int, str, str, int]]
) -> None:
    """Check complete English names without taking over explicit code spans."""
    if default_locale == "en":
        return
    matches = tuple(_ENGLISH_REFERENCE_NAME_RE.finditer(value))
    if not matches:
        return
    literals = tuple(match.span() for match in TRANSLATION_LITERAL_RE.finditer(value))
    for match in matches:
        if any(start <= match.start() and match.end() <= end for start, end in literals):
            continue
        text = match.group()
        foreign.append((match.start(), match.end(), "en", text, filtered_translation_text(text)[1]))


def translation_spelling_segments(
    value: str,
    key: str,
    default_locale: str,
) -> tuple[tuple[str, tuple[str, ...], int], ...]:
    """Split prose by explicit language-bearing markup and legal identifiers.

    The returned text is already filtered for transport syntax.  A Spanish legal
    label, a ``lang``-annotated HTML element, or a numbered form/legal title is
    therefore checked with the dictionary that owns that rendered text rather
    than with the language of the surrounding catalogue cell.
    """
    # Resolve Hungarian endings before a Spanish title recognizer takes away
    # the stem (e.g. Modelo 111-et). Otherwise -et becomes an isolated word.
    suffix_excluded = 0
    if default_locale == "hu":
        value, suffix_excluded = hungarian_suffix_spelling_text(value)
    foreign: list[tuple[int, int, str, str, int]] = []
    html_spelling_segments(value, foreign)
    markdown_link_spelling_segments(value, foreign)
    rst_link_spelling_segments(value, foreign)
    legal_title_spelling_segments(value, default_locale, foreign)
    english_reference_spelling_segments(value, default_locale, foreign)

    # Keep the first structured span when two recognizers describe the same
    # source range (for example a legal title inside a marked link).
    accepted: list[tuple[int, int, str, str, int]] = []
    for candidate in sorted(foreign, key=lambda item: (item[0], -(item[1] - item[0]))):
        if any(candidate[0] < previous[1] and previous[0] < candidate[1] for previous in accepted):
            continue
        accepted.append(candidate)
    masked = list(value)
    for start, end, _language, _text, _excluded in accepted:
        masked[start:end] = [" "] * (end - start)
    words, excluded = locale_spelling_words("".join(masked), default_locale)
    segments: list[tuple[str, tuple[str, ...], int]] = [(default_locale, words, excluded + suffix_excluded)]
    for _start, _end, language, text, structural_excluded in accepted:
        words, _excluded = locale_spelling_words(text, language)
        wrapper_excluded = structural_excluded - filtered_translation_text(text)[1]
        segments.append((language, words, wrapper_excluded + _excluded))
    return tuple(segments)


def locale_spelling_words(value: str, locale: str) -> tuple[tuple[str, ...], int]:
    """Exclude locale-specific notation before generic syntax splits its tokens."""
    excluded = 0
    if locale == "hu":
        value, matches = TRANSLATION_HUNGARIAN_DATE_RE.subn(" ", value)
        excluded += matches
        # Preserve the numeric stem for the ordinary number filter; remove
        # only the attested Hungarian suffix on percentage expressions.
        value, matches = TRANSLATION_HUNGARIAN_PERCENT_SUFFIX_RE.subn(lambda match: match.group("stem"), value)
        excluded += matches
        # Keep the stem visible to ordinary spelling checks; only the
        # recognized Hungarian suffix is structural notation.
        value, matches = hungarian_suffix_spelling_text(value)
        excluded += matches
    elif locale == "ca":
        value, matches = CATALAN_HYPHENATED_CLITIC_RE.subn(lambda match: match.group("form").split("-")[0], value)
        excluded += matches
    filtered, structural_excluded = filtered_translation_text(value)
    # English dictionaries own contractions and possessives as complete words;
    # Catalan elisions still need their lexical word checked separately.
    if locale == "en":
        filtered = filtered.replace("’", "'")
    return (
        translation_words(filtered, preserve_apostrophes=locale == "en", preserve_periods=locale == "hu"),
        excluded + structural_excluded,
    )


def is_legal_authority_target(target: str) -> bool:
    """Recognize legal authority links from their structured destination."""
    normalized = target.casefold()
    return (
        "_generated/legal/" in normalized
        or ".boe.es/" in normalized
        or ".aeat.es/" in normalized
        or "agenciatributaria.gob.es/" in normalized
    )


def spanish_word_context(
    value: str,
    key: str,
    word: str,
    *,
    owner_locale: str,
    dictionary: object | None,
    spanish_dictionary: DictionaryLike | None,
) -> bool:
    """Whether an unknown word sits in structured Spanish legal/name prose."""
    if owner_locale == "es" or spanish_dictionary is None:
        return False
    languages = {
        language
        for language, words, _excluded in translation_spelling_segments(value, key, owner_locale)
        if any(candidate.casefold() == word.casefold() for candidate in words)
    }
    return "es" in languages and owner_locale not in languages
