"""Spelling enrollment for the authoritative locale audit."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping

from .signal_contracts import DictionaryLike, ExcludedStructuralInventory
from .signal_policy import LOCALES, SPELLING_SURFACES
from .signal_spelling_reviewed_words import REVIEWED_LOCALE_SPELLINGS, REVIEWED_SPANISH_LEGAL_SPELLINGS
from .signal_spelling_segments import (
    is_known_residence_region_label,
    spanish_word_context,
    translation_spelling_segments,
)
from .signal_spelling_spanish_forms import is_reviewed_spanish_form
from .signal_tokens import filtered_translation_text

# Exact, attested forms absent from the pinned dictionaries. AEAT and modelo
# are documented in src/cadrumo/_data/terminology/concepts/{aeat,modelo}.toml.
# Google and Drive name the connected provider and its storage service, as in
# docs/locales/es/LC_MESSAGES/workstation-setup.po. Sheets is the named Google
# product component in docs/locales/{ca,es,hu}/LC_MESSAGES/workstation-setup.po.
# Python is the technology name in docs/locales/es/LC_MESSAGES/workstation-setup.po.
# Platform and installer names are used in translated download and setup pages:
# Windows/macOS in download.po, and Homebrew/Scoop/PyPI in download.po and
# workstation-setup.po for the es/ca/hu locales. Claude is named as an AI client
# in download.po and how-to/index.po for those same locales.
# Excel is used in the Spanish architecture overview; SQLite is used in the
# Spanish and Hungarian architecture overviews and registry API references.
# Enter is the terminal key name in
# docs/locales/es/LC_MESSAGES/how-to/fill-in-and-file-in-the-workbench.po.
# Snapshot/snapshots and bucket/buckets are used as technical terms in the
# translated architecture overview at docs/locales/{es,ca}/LC_MESSAGES/architecture/index.po.
# OAuth is the protocol name in src/cadrumo/locales/{es,ca,hu}/adapters.yml;
# DEHú is the official notification service name in src/cadrumo/locales/{es,ca,hu}/cli.yml
# and docs/locales/{es,ca,hu}/LC_MESSAGES/how-to/check-aeat-notifications.po.
# Spanish common.yml uses desactualizado/Desactualizado, recalcular/Recalcular,
# recálculo, recalcula and introdúcelo in stale-state and recalculation messages
# (including common.yml's Modelo workbench actions). The pinned Spanish dictionary
# misses these exact valid forms; keep the enrollment to those observed spellings.
# Current Spanish runtime prose also uses tributación in cli.yml and wizard.yml,
# contrafirmado in cli.yml, intracomunitarias in common.yml/profile.yml/wizard.yml,
# preadoptivo in wizard.yml, registral in wizard.yml, Confírmalo in common.yml,
# and revísalo in common.yml. The pinned Spanish dictionary misses each exact form;
# retain their observed capitalization and do not enroll adjacent inflections.
# Additional current Spanish forms absent from that dictionary are
# intracomunitaria and intracomunitario in application.yml/cli.yml and Modelo
# schemas, recapitulativa in common.yml and the Modelo 349 catalogue, minoración
# in application.yml and Modelo schemas, previsualiza in cli.yml, sobrescritura
# in cli.yml/errors.yml, tipados in cli.yml, autenticarte in adapters.yml, and
# impatriados in common.yml/wizard.yml. reintentar appears in application.yml,
# cli.yml and errors.yml. These are exact observed forms, not inflection families.
# Only dictionary gaps are enrolled; enumerating spellings does not admit
# arbitrary inflections or name typos.
# Identifier labels occur as standalone technical terms in diagnostics and
# error prose across all locale catalogues. Preserve only observed casing.
# WebP names an admitted evidence image format in every application.yml.
# Gmail names the evidence source in desktop/TUI common.yml; Catalan's
# dictionary already recognises it, so only the other locales enroll it below.
# The mixed-case tax abbreviations in cli.app.modelo.work are attested by
# BOE-A-2024-3329 (ITPyAJD) and Hacienda's TEAC 24/01192/2021 (LISyD).
# Preserve exactly those abbreviations, not arbitrary mixed-case tokens.
# Pagefind is the search-engine name; Ceuta and Melilla are the named IVA
# territories in the multilingual terminology definitions. Keep their exact case.
# Exact software/format names in architecture/index.md, authoring-guide.md,
# download.md and the signed-report verification recipe. pyproject.toml and
# docs/conf.py identify the same tools; casing and adjacent typos stay checked.
# Pydantic is the product name used by its own documentation; the lowercase
# Python distribution/module remains code syntax, not an alternate brand.
# https://docs.pydantic.dev/latest/
# https://developer.apple.com/documentation/apple-silicon
# https://bizum.com/es/sobre-bizum/
# https://poppler.freedesktop.org/
# https://diataxis.fr/
# https://www.facturae.gob.es/formato
_SOFTWARE_PROPER_NAMES = frozenset(
    {
        "Apple",
        "Bizum",
        "Diátaxis",
        "Facturae",
        "GitHub",
        "Linux",
        "Markdown",
        "OpenSSL",
        "PowerShell",
        "Pydantic",
        "Sphinx",
        "poppler",
        "reStructuredText",
    }
)
_SHARED_SPELLINGS = (
    frozenset(
        {
            "Cadrumo",
            "AEAT",
            "id",
            "Id",
            "ids",
            "Ids",
            "IDs",
            "Pagefind",
            "Ceuta",
            "Melilla",
            # Exact Spanish territory names in the Concierto source guidance:
            # https://www.boe.es/buscar/act.php?id=BOE-A-2002-9352
            "Álava",
            "Guipúzcoa",
            "Vizcaya",
            # Exact official names of the same historical territories:
            # https://www.ine.es/daco/daco42/codmun/cod_provincia.htm
            # https://www.euskadi.eus/what-is-basque-country/web01-ejeduki/en/
            "Bizkaia",
            "Gipuzkoa",
            "WebP",
            "ITPyAJD",
            "LISyD",
        }
    )
    | _SOFTWARE_PROPER_NAMES
)
# English technical nouns attested in primary tool and standards references.
# Only these stems receive regular plural and sentence-initial capitalization;
# arbitrary unknown words never become valid merely by removing a final s.
# https://docs.github.com/en/copilot/tutorials/explore-a-codebase
# https://docs.docker.com/reference/compose-file/services/
# https://docs.python.org/3/glossary.html
# https://docs.python.org/3/reference/import.html
# https://docs.python.org/3/howto/enum.html
# https://docs.kernel.org/filesystems/path-lookup.html
# https://csrc.nist.gov/glossary/term/ciphertext
# https://rust-lang.github.io/rustup/concepts/toolchains.html
# https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets
# https://docs.github.com/en/copilot/how-tos/troubleshoot-copilot/troubleshoot-firewall-settings
# https://docs.python.org/3/library/os.path.html#os.path.basename
# https://dictionary.cambridge.org/dictionary/english/walkthrough
# https://docs.python.org/3.15/whatsnew/changelog.html
# https://learn.microsoft.com/en-us/archive/msdn-magazine/2016/january/cutting-edge-don%E2%80%99t-gamble-with-ux-use-wireframes
# https://learn.microsoft.com/en-us/microsoft-365/copilot/copilot-tuning-document-validation-template
_ENGLISH_TECHNICAL_NOUNS = frozenset(
    {
        "codebase",
        "entrypoint",
        "docstring",
        "subpackage",
        "subcommand",
        "checksum",
        "lookup",
        "wireframe",
        "rulebook",
        "enum",
        "parser",
        "filesystem",
        "ciphertext",
        "toolchain",
        "ruleset",
        "basename",
        "allowlist",
        "walkthrough",
    }
)
# The concepts modelo and prorrata-especial use these complete Latin phrases.
# Their individual words are not general spelling exceptions.
_LATIN_PHRASES = (
    (re.compile(r"(?<![\w-])ad[ \t]+hoc(?![\w-])"), frozenset({"ad", "hoc"})),
    (re.compile(r"(?<![\w-])pro[ \t]+rata(?![\w-])"), frozenset({"pro", "rata"})),
)


def _known_latin_phrase_word(value: str, word: str) -> bool:
    """Recognize words only within the two complete, authored Latin phrases."""
    if not any(word in words for _pattern, words in _LATIN_PHRASES):
        return False
    prose = filtered_translation_text(value)[0]
    return any(word in words and pattern.search(prose) is not None for pattern, words in _LATIN_PHRASES)


def is_project_spelling(locale: str, word: str) -> bool:
    """Accept reviewed dictionary gaps without changing Hunspell data."""
    if locale == "en" and word.endswith("'s"):
        # A grammatical possessive does not change an exact enrolled name.
        # Other apostrophe forms and misspelled stems still need a dictionary.
        word = word[:-2]
    technical = word[:1].lower() + word[1:]
    return (
        word in _SHARED_SPELLINGS
        or word in REVIEWED_LOCALE_SPELLINGS.get(locale, frozenset())
        or (
            locale == "en"
            and (technical in _ENGLISH_TECHNICAL_NOUNS or technical.removesuffix("s") in _ENGLISH_TECHNICAL_NOUNS)
        )
        or (locale == "es" and is_reviewed_spanish_form(word))
    )


def spelling_surface(key: str) -> str:
    """Classify a spelling cell by its authored source surface."""
    if not key.startswith("parallel:"):
        return "runtime"
    relative = key.removeprefix("parallel:")
    if relative.startswith("src/"):
        return "toml"
    if relative.startswith("docs/locales/") or (
        not relative.startswith("docs/cli/") and not relative.startswith("docs/_generated/")
    ):
        return "docs_po"
    return "generated_docs"


def excluded_structural_inventory(excluded: Counter[tuple[str, str]]) -> ExcludedStructuralInventory:
    """Return stable structural-exclusion totals for every surface/locale."""
    by_surface_locale = {
        f"{surface}/{locale}": excluded[(surface, locale)] for surface in SPELLING_SURFACES for locale in LOCALES
    }
    return {
        "excluded_structural_tokens": sum(excluded.values()),
        "excluded_structural_tokens_by_surface_locale": by_surface_locale,
    }


def enroll_spelling_locale(
    locale: str,
    required_keys: set[str],
    locale_leaves: dict[str, dict[str, object]],
    additional_values: dict[str, dict[str, str]] | None,
    keys_by_word: dict[str, dict[str, set[tuple[str, str]]]],
    cell_words: dict[tuple[str, str], frozenset[str]],
    cell_words_by_language: dict[tuple[str, str], dict[str, frozenset[str]]],
    cell_excluded_structural_tokens: dict[tuple[str, str], int],
    cell_text: dict[tuple[str, str], str],
    excluded_by_surface_locale: Counter[tuple[str, str]],
    enrolled_cells_by_locale: Counter[str],
    prose_cells_by_locale: Counter[str],
    structural_only_cells_by_locale: Counter[str],
) -> None:
    """Enroll spelling locale."""
    leaves = locale_leaves.get(locale, {})
    values = {key: leaves.get(key) for key in required_keys}
    values.update((additional_values or {}).get(locale, {}))
    for key, value in sorted(values.items()):
        enroll_spelling_cell(
            key,
            value,
            locale,
            keys_by_word,
            cell_words,
            cell_words_by_language,
            cell_excluded_structural_tokens,
            cell_text,
            excluded_by_surface_locale,
            enrolled_cells_by_locale,
            prose_cells_by_locale,
            structural_only_cells_by_locale,
        )


def enroll_spelling_cell(
    key: str,
    value: object,
    locale: str,
    keys_by_word: dict[str, dict[str, set[tuple[str, str]]]],
    cell_words: dict[tuple[str, str], frozenset[str]],
    cell_words_by_language: dict[tuple[str, str], dict[str, frozenset[str]]],
    cell_excluded_structural_tokens: dict[tuple[str, str], int],
    cell_text: dict[tuple[str, str], str],
    excluded_by_surface_locale: Counter[tuple[str, str]],
    enrolled_cells_by_locale: Counter[str],
    prose_cells_by_locale: Counter[str],
    structural_only_cells_by_locale: Counter[str],
) -> None:
    """Enroll spelling cell."""
    if not isinstance(value, str):
        return
    enrolled_cells_by_locale[locale] += 1
    cell = (locale, value)
    if cell not in cell_words:
        cache_spelling_cell_words(
            value, key, locale, cell, cell_words, cell_words_by_language, cell_excluded_structural_tokens
        )
    words = cell_words[cell]
    excluded_by_surface_locale[(spelling_surface(key), locale)] += cell_excluded_structural_tokens[cell]
    cell_text[(locale, key)] = value
    if words:
        prose_cells_by_locale[locale] += 1
    else:
        structural_only_cells_by_locale[locale] += 1
    for dictionary_locale, language_words in cell_words_by_language[cell].items():
        locale_words = keys_by_word.setdefault(dictionary_locale, defaultdict(set))
        for word in language_words:
            locale_words[word].add((locale, key))


# Exact Spanish dictionary gaps also used in the bilingual legal references:
# IVA's Modelo 349 notes and citations use the intracomunitaria family and
# recapitulativa; IRPF uses Minoración, impatriados and bloqueantes; the Modelo
# 038/296 references use registral/subclave, and the IS notes use fiscalmente.
# Do not reuse the entire Spanish project vocabulary here: it
# includes literal option IDs such as modificacion, which is a typo in prose.
_SPANISH_LEGAL_REFERENCE_SPELLINGS = frozenset(
    {
        *REVIEWED_SPANISH_LEGAL_SPELLINGS,
        "Minoración",
        "intracomunitaria",
        "intracomunitarias",
        "intracomunitario",
        "recapitulativa",
        "impatriados",
        "subclave",
        "bloqueantes",
        "registral",
        "fiscalmente",
    }
)


def _spanish_legal_note_word(
    dictionary_locale: str, key: str, word: str, dictionaries: Mapping[str, DictionaryLike]
) -> bool:
    """Recognize Spanish source wording on the bilingual legal-reference surface."""
    return (
        dictionary_locale == "en"
        and key.startswith("parallel:docs/_generated/legal/")
        and ".rst:line[" in key
        and not key.endswith(":legal-link-chrome")
        and (word in _SPANISH_LEGAL_REFERENCE_SPELLINGS or dictionaries["es"].lookup(word))
    )


def check_dictionary_spelling_words(
    dictionary_locale: str,
    words: dict[str, set[tuple[str, str]]],
    dictionaries: Mapping[str, DictionaryLike],
    cell_text: dict[tuple[str, str], str],
    unknown_words: set[tuple[str, str]],
    unknown_by_cell: dict[tuple[str, str], set[str]],
) -> None:
    """Check dictionary spelling words."""
    dictionary = dictionaries[dictionary_locale]
    for word in words:
        if _dictionary_accepts_spelling(dictionary_locale, word, dictionary):
            continue
        for owner_locale, key in words[word]:
            if _spanish_legal_note_word(dictionary_locale, key, word, dictionaries):
                continue
            record_unknown_spelling_word(
                owner_locale, key, word, dictionary_locale, dictionaries, cell_text, unknown_words, unknown_by_cell
            )


def _dictionary_accepts_spelling(locale: str, word: str, dictionary: DictionaryLike) -> bool:
    """Check the original word and narrowly defined orthographic variants."""
    # Hungarian abbreviations such as "pl." need their final period; ordinary
    # sentence-final words instead need the unpunctuated stem.
    stem = word.removesuffix(".") if locale == "hu" else word
    if is_project_spelling(locale, stem) or dictionary.lookup(word) or (stem != word and dictionary.lookup(stem)):
        return True
    # English singular possessives require an independently accepted base;
    # never make an unknown or misspelled stem valid by adding an apostrophe.
    # https://dictionary.cambridge.org/grammar/british-grammar/apostrophe
    return (
        locale == "en"
        and word.endswith(("'s", "’s"))
        and bool(re.fullmatch(r"[^\W\d_]+['’]s", word))
        and dictionary.lookup(word[:-2])
    )


def record_unknown_spelling_word(
    owner_locale: str,
    key: str,
    word: str,
    dictionary_locale: str,
    dictionaries: Mapping[str, DictionaryLike],
    cell_text: dict[tuple[str, str], str],
    unknown_words: set[tuple[str, str]],
    unknown_by_cell: dict[tuple[str, str], set[str]],
) -> None:
    """Record unknown spelling word."""
    owner_cell = (owner_locale, key)
    value = cell_text[owner_cell]
    if is_known_residence_region_label(owner_locale, key, value):
        return
    stem = word.removesuffix(".") if dictionary_locale == "hu" else word
    if _known_latin_phrase_word(value, stem):
        return
    foreign_context = spanish_word_context(
        value,
        key,
        word,
        owner_locale=owner_locale,
        dictionary=dictionaries.get(owner_locale),
        spanish_dictionary=dictionaries.get("es"),
    )
    if foreign_context and dictionary_locale == owner_locale:
        # A Spanish legal title or authority name embedded in an
        # English/Hungarian/Catalan cell is checked by Spanish.
        # Unknown words remain findings, but are attributed to the
        # language of the embedded phrase rather than to the page.
        if dictionaries["es"].lookup(word):
            return
        unknown_words.add(("es", word.casefold()))
        unknown_by_cell[owner_cell].add(word)
        return
    unknown_words.add((dictionary_locale, word.casefold()))
    unknown_by_cell[owner_cell].add(word)


def cache_spelling_cell_words(
    value: str,
    key: str,
    locale: str,
    cell: tuple[str, str],
    cell_words: dict[tuple[str, str], frozenset[str]],
    cell_words_by_language: dict[tuple[str, str], dict[str, frozenset[str]]],
    cell_excluded_structural_tokens: dict[tuple[str, str], int],
) -> None:
    """Cache spelling cell words."""
    language_segments = translation_spelling_segments(value, key, locale)
    language_words_mutable: dict[str, set[str]] = defaultdict(set)
    for language, words, _excluded in language_segments:
        language_words_mutable[language].update(word for word in words if len(word) > 1)
    language_words = {language: frozenset(words) for language, words in language_words_mutable.items()}
    cell_words_by_language[cell] = language_words
    cell_words[cell] = frozenset(word for words in language_words.values() for word in words)
    excluded_tokens = sum(excluded for _language, _words, excluded in language_segments)
    cell_excluded_structural_tokens[cell] = excluded_tokens
