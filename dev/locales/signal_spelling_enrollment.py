"""Spelling enrollment for the authoritative locale audit."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping

from .signal_contracts import DictionaryLike, ExcludedStructuralInventory
from .signal_policy import LOCALES, SPELLING_SURFACES
from .signal_spelling_segments import spanish_word_context, translation_spelling_segments

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
_SHARED_SPELLINGS = frozenset({"Cadrumo", "AEAT"})
_LOCALE_SPELLINGS: dict[str, frozenset[str]] = {
    # These ordinary English technical/domain terms are absent from the pinned
    # dictionary-en-gb data, but are attested in the canonical English catalogue:
    # counterparty/withholdings in modelo/schema/347.yml and 220.yml,
    # lifecycle/namespace/preflight in errors.yml and application.yml,
    # cadastral in modelo/schema/714.yml, handoff in cli.yml, and OAuth in
    # adapters.yml. Keep only the observed spellings and capitalisation.
    "en": frozenset(
        {
            "modelo",
            "Modelo",
            "counterparty",
            "Counterparty",
            "withholdings",
            "Withholdings",
            "lifecycle",
            "Lifecycle",
            "namespace",
            "Namespace",
            "preflight",
            "Preflight",
            "cadastral",
            "Cadastral",
            "handoff",
            "Handoff",
            "OAuth",
            # These exact English forms occur in current operator catalogues:
            # counterparties/Counterparties and Depreciable in common.yml,
            # Recapitulative in Modelo 349's title, and deregistration in
            # common.yml, cli.yml and Modelo schemas. Retain observed case only.
            "counterparties",
            "Counterparties",
            "Recapitulative",
            "deregistration",
            "Deregistration",
            "Depreciable",
            # Genuine prose in adapters.yml (unparseable), application.yml
            # (idempotency, supersession, fileable), and cli.yml (reviewable,
            # resumable). reauthenticate also occurs as ordinary prose in
            # docs/how-to/authenticate-with-aeat.md, not only as a method name.
            "reauthenticate",
            "unparseable",
            "idempotency",
            "supersession",
            "reviewable",
            "fileable",
            "resumable",
        }
    ),
    "es": frozenset(
        {
            "Google",
            "Drive",
            "Python",
            "Enter",
            "Sheets",
            "Windows",
            "macOS",
            "Excel",
            "SQLite",
            "Homebrew",
            "Scoop",
            "PyPI",
            "Claude",
            "snapshot",
            "snapshots",
            "bucket",
            "buckets",
            "OAuth",
            "DEHú",
            "desactualizado",
            "Desactualizado",
            "recalcular",
            "Recalcular",
            "recálculo",
            "recalcula",
            "introdúcelo",
            "tributación",
            "contrafirmado",
            "intracomunitarias",
            "preadoptivo",
            "registral",
            "Confírmalo",
            "revísalo",
            "intracomunitaria",
            "recapitulativa",
            "minoración",
            "previsualiza",
            "sobrescritura",
            "intracomunitario",
            "tipados",
            "autenticarte",
            "impatriados",
            "reintentar",
            # Exact operator prose in application.yml and cli.yml: informal
            # imperatives confírmalo/Combínalo, idempotente for repeated writes,
            # bloqueante/bloqueantes for findings, tipado/tipada for contracts,
            # and previsualizar for inspecting proposed values before writing.
            "confírmalo",
            "Combínalo",
            "idempotente",
            "bloqueante",
            "bloqueantes",
            "tipado",
            "tipada",
            "previsualizar",
        }
    ),
    "ca": frozenset(
        {
            "Sheets",
            "Windows",
            "macOS",
            "Homebrew",
            "Scoop",
            "PyPI",
            "Claude",
            "snapshot",
            "snapshots",
            "bucket",
            "buckets",
            "OAuth",
            "DEHú",
            # These Catalan forms are used in current operator-facing locale
            # prose: impatriats in wizard.yml/profile.yml and modelo schemas;
            # reembolcallen and oblides in flows.yml; tipada/tipades in cli.yml,
            # application.yml and translated reference pages; bloquejants in
            # cli.yml/application.yml and verification-reports.po; Subclau in
            # profile.yml and modelo schemas. The pinned Catalan dictionary
            # rejects each exact form, so enroll only these observed spellings.
            "impatriats",
            "reembolcallen",
            "oblides",
            "tipada",
            "tipades",
            "bloquejants",
            "Subclau",
            # Current Catalan prose attests inclusiva in cli.yml, tipat in
            # application.yml, idempotència in application.yml, and
            # subcomandament/coteig/indiques in cli.yml and wizard.yml.
            # The documentation also uses tipats and subpaquets in
            # reference/registry-legal-api.po and architecture/index.po.
            "inclusiva",
            "tipat",
            "tipats",
            "idempotència",
            "subpaquets",
            "subcomandament",
            "coteig",
            "indiques",
        }
    ),
    "hu": frozenset(
        {
            "modelo",
            "Modelo",
            "Drive",
            "Sheets",
            "Windows",
            "macOS",
            "SQLite",
            "Homebrew",
            "Scoop",
            "PyPI",
            "Claude",
            "OAuth",
            "DEHú",
            # These exact Hungarian forms are attested in common.yml/errors.yml
            # and translated documentation: ellenőrzi/Ellenőrzi,
            # Intraközösségi (wizard.yml, profile.yml, cli.yml and common.yml),
            # szkriptelt (flows.yml and application.yml), Ugrás/ugrás,
            # szektorizált and munkajegység. Hungarian final vowel lengthening
            # is grammatical in Intraközösségi; enroll only the observed form.
            "Intraközösségi",
            "ellenőrzi",
            "Ellenőrzi",
            "szkriptelt",
            "Ugrás",
            "ugrás",
            "szektorizált",
            "munkajegység",
            # Direct Hungarian inflections of the product name and the AEAT
            # term "modelo" lengthen final o to ó (AkH. 216(a)). These are
            # the exact forms attested by the locale audit; do not infer other
            # roots or suffixes. Sentence-final periods are retained by the
            # Hungarian tokenizer and are enrolled only where observed.
            "Cadrumóban",
            "Cadrumónak",
            "Cadrumón",
            "Cadrumóban.",
            "Cadrumót",
            "Cadrumóhoz",
            "Cadrumóhoz.",
            "Cadrumóba",
            "Cadrumót.",
            "Cadrumóval",
            "Cadrumóból",
            "Cadrumóba.",
            "Cadrumóra",
            "modeló",
            "modelók",
            "modelót",
            "modelóknál",
            "modelóhoz",
            "modelónál",
            "Modelókon",
            "modelódat",
            "modelóval",
            "modelónként",
            "modelókat",
            "modelókhoz",
            "modelóra",
            "modelónak",
            "modelóig",
            "Modelók",
            "modelótól",
            "modelóra.",
            # Ordinary Hungarian words absent from the pinned dictionary:
            # téged/őt in operator prose, bájtokat/bájtos in byte-handling
            # messages, and összegzése/összegzésével in summaries. Keep these
            # exact observed forms; do not enroll broader inflection patterns.
            "téged",
            "őt",
            "bájtokat",
            "bájtos",
            "összegzése",
            "összegzésével",
            # Additional exact ordinary forms attested in the current operator
            # catalogue: a confirmation prompt (Ellenőrzöd), byte descriptions
            # (bájtok/bájtban/bájtra/bájtként), and review/update prose.
            "Ellenőrzöd",
            "bájtok",
            "bájtban",
            "bájtra",
            "bájtként",
            "priorizálhatók",
            "megkísérléséhez",
            # Common Hungarian vocabulary attested in operator labels and
            # prose: summary/preset names, free-text reasons, byte references,
            # and the noun látás used in the LLM capability label.
            "Összegzés",
            "Előbeállítások",
            "Szabadszöveges",
            "bájtjaik",
            "bájtjainak",
            "bájtokhoz",
            "látás",
        }
    ),
}


def is_project_spelling(locale: str, word: str) -> bool:
    """Accept only explicitly attested forms, without changing Hunspell data."""
    if locale == "en" and word.endswith("'s"):
        # A grammatical possessive does not change an exact enrolled name.
        # Other apostrophe forms and misspelled stems still need a dictionary.
        word = word[:-2]
    return word in _SHARED_SPELLINGS or word in _LOCALE_SPELLINGS.get(locale, frozenset())


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
        # Hungarian abbreviations such as "pl." need their final period.
        # Ordinary sentence-final words instead need the unpunctuated stem;
        # neither path admits a form the dictionary does not recognise.
        stem = word.removesuffix(".") if dictionary_locale == "hu" else word
        if (
            is_project_spelling(dictionary_locale, stem)
            or dictionary.lookup(word)
            or (stem != word and dictionary.lookup(stem))
        ):
            continue
        for owner_locale, key in words[word]:
            record_unknown_spelling_word(
                owner_locale, key, word, dictionary_locale, dictionaries, cell_text, unknown_words, unknown_by_cell
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
