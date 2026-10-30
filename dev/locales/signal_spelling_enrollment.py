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
# Identifier labels occur as standalone technical terms in diagnostics and
# error prose across all locale catalogues. Preserve only observed casing.
_SHARED_SPELLINGS = frozenset({"Cadrumo", "AEAT", "id", "Id", "ids", "Ids", "IDs"})
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
            # Established CLI and application vocabulary, attested in the
            # English operator catalogues: provider names (claude,
            # antigravity), secure-storage and key terms (keychain,
            # unencrypted, keypair), and standard implementation concepts.
            # Preserve only the observed forms and casing.
            "claude",
            "antigravity",
            "keychain",
            "unencrypted",
            "keypair",
            "auditable",
            "backend",
            "Backend",
            "validator",
            "validators",
            "enum",
            "Enum",
            "datetime",
            "filesystem",
            "subcommand",
            "stdin",
            "json",
            "csv",
            "tsv",
            "xls",
            "xlsm",
            "xlsx",
            "loopback",
            # These exact lowercase names occur in translated operator
            # commands and English CLI diagnostics: ``aeat`` is the literal
            # command root, ``auth``/``config`` are command namespaces, and
            # Auth/Config are displayed diagnostic section labels.
            "aeat",
            "auth",
            "Auth",
            "config",
            "Config",
            # AEAT legal vocabulary is deliberately preserved in English
            # operator messages where the Spanish term names a filing
            # procedure, status, or tax concept. These exact forms occur in
            # adapters.yml, application.yml, common.yml, and cli.yml; keep
            # the enrollment narrow and language-scoped.
            "comparecencia",
            "Sede",
            "certificado",
            "autoliquidación",
            "rectificativa",
            "rectificación",
            "complementaria",
            "solicitud",
            "ejercicio",
            "cuota",
            "prorrata",
            "Reglamento",
            "apoderado",
            "foral",
            "Navarra",
            "Beckham",
            "impatriado",
            # The Spanish Modelo 130 adjustment term is retained verbatim in
            # translated operator guidance and official legal references.
            "minoración",
            "autoconsumo",
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
            # Spanish CLI and runtime prose uses ``arts.`` as the legal
            # abbreviation for artículos (LIVA/RIS citations), ``hash`` for
            # content and storage-state digests, and ``backend`` for the
            # encrypted calculation/storage implementation. These are exact
            # technical terms used in src/cadrumo/locales/es/{cli,application,
            # common,adapters}.yml; do not infer other English terms.
            "arts",
            "hash",
            "backend",
            "desactualizado",
            "Desactualizado",
            # Current filing-calendar prose uses the plural form
            # desactualizados for stale census facts; enroll the observed
            # inflection without admitting a general suffix rule.
            "desactualizados",
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
            "Minoración",
            # AEAT legal titles use the exact capitalized tax label
            # Minoración; the IVA and Spanish legal texts also use
            # autoconsumo as a standard tax-domain compound.
            "autoconsumo",
            "previsualiza",
            "sobrescritura",
            # The Spanish binding-resolution help and evidence reference use
            # sobrescrituras for user-supplied overrides.
            "sobrescrituras",
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
            # Repeated operator instructions attest these Spanish forms in
            # runtime catalogues: Reintentar as a retry action, Reintenta and
            # Configúralo in Cl@ve guidance, Previsualiza for dry-run help,
            # sectorizada in IVA prorrata errors, and contrafirma in review
            # package help. Enroll only the exact observed spellings.
            "Reintentar",
            "Reintenta",
            "Configúralo",
            "Previsualiza",
            "sectorizada",
            "contrafirma",
            "idempotente",
            "bloqueante",
            "bloqueantes",
            "tipado",
            "tipada",
            "previsualizar",
            # AEAT census-form values exposed by CLI period help are exact
            # token spellings (alta, modificacion, baja), not running prose.
            "alta",
            "modificacion",
            "baja",
            # Current Spanish CLI help uses token/tokens for AEAT period and
            # scope values, app as the literal command namespace, and ledger
            # as the literal subcommand. Keep these runtime forms exact.
            "token",
            "tokens",
            "Token",
            "Tokens",
            "app",
            "ledger",
            # Exact Spanish operator-catalogue forms: resolutor names a
            # registered resolver; Intro is the terminal's displayed key;
            # flags and config name CLI options and command namespaces.
            "resolutor",
            "Intro",
            "flags",
            "config",
            # Lowercase ``aeat`` is the literal command root retained in
            # Spanish operator help and command examples.
            "aeat",
            # ``auth`` is retained as a command namespace in CLI guidance.
            "auth",
            # Current Modelo 390 help and workbench guidance use the exact
            # AEAT tax-domain term exoneración.
            "exoneración",
            # Repeated Spanish operator and tax-domain prose uses these exact
            # forms: operandos in calculation explanations, fiscalmente in tax
            # rules, direccionado/a in content-addressing docs, cotitular in
            # account labels, subclave/atribuyente in Modelo 184 fields, and
            # pymes in legal-form guidance. Keep each observed form exact.
            "operandos",
            "Operandos",
            "fiscalmente",
            "direccionado",
            "direccionados",
            "cotitular",
            "Cotitular",
            "subclave",
            "Subclave",
            "atribuyente",
            "pymes",
            "reintentarlo",
            "reintentado",
            # These exact informal imperatives and clitic forms recur in
            # operator instructions across the Spanish runtime and translated
            # how-to pages (application.yml, cli.yml, common.yml, and the
            # Spanish how-to catalogue). Enroll observed casing only; this
            # does not admit other clitic or imperative forms.
            "configurarlo",
            "Escríbelo",
            "escríbelo",
            "reintenta",
            "revísala",
            "Revísala",
            "escríbela",
            "Escríbela",
            "actívala",
            "regístrala",
            "Regístrala",
            "impórtalo",
            "Impórtalo",
            "confírmala",
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
            # The Spanish Modelo 130 guide retains the tax label minoración.
            "minoración",
            "inclusiva",
            "tipat",
            "tipats",
            "idempotència",
            "subpaquets",
            "subcomandament",
            "coteig",
            "indiques",
            # practiques is the second-person singular present of practicar,
            # used in cli.yml's Catalan guidance about withholding practice.
            # It is not the accented noun pràctiques.
            "practiques",
            # recapitulativa is standard Catalan terminology, attested by the
            # Modelo 349 catalogue and its translated operator documentation.
            "recapitulativa",
            # The CLI documents AEAT's literal census period values; preserve
            # these Spanish protocol spellings alongside Catalan explanation.
            "alta",
            "modificacion",
            "baja",
            "comunicacion",
            "variacion",
            # Catalan CLI help names the ledger subcommand in its command
            # examples and operator instructions; preserve that exact token.
            "ledger",
            # Runtime catalogue prose and command examples use these exact
            # technical tokens: `aeat`/`config`/`flags`/`status` in setup and
            # authentication instructions; `hash`/`payload` in storage errors;
            # `backend` and `runtime` in repository and storage diagnostics.
            # Keep the observed lowercase forms and language scope. These are
            # not spelling families or exceptions to ordinary Catalan prose.
            "aeat",
            "config",
            "flags",
            "status",
            "hash",
            "payload",
            "backend",
            "runtime",
            # The AEAT CLI namespace is written ``auth`` in command examples.
            "auth",
            # These exact Catalan forms are valid but absent from the pinned
            # dictionary: sublímit in a reduction warning, preomplert in
            # filing-record guidance, and reanomenament in work guidance.
            # reprenable describes a session that can be resumed.
            "sublímit",
            "preomplert",
            "reanomenament",
            "reprenable",
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
            # Modelo 130 documentation retains this Spanish tax label in
            # explanatory prose and legal citations.
            "minoración",
            # Spanish legal and jurisdiction names are retained in Hungarian
            # tax guidance: Navarra in common.yml/profile.yml/Modelo schemas,
            # Beckham in wizard.yml/profile.yml and the Modelo catalogue.
            # Keep the proper names exact and Hungarian-scoped.
            "Navarra",
            "Beckham",
            # The official Spanish AEAT name is retained in Hungarian docs;
            # the final Hungarian case ending is part of the observed token.
            "Agencia",
            "Estatal",
            "Administración",
            "Tributariánál",
            # Exact Hungarian terminology used in the current localized tax
            # catalogues: the compound stem hozzáadottérték, the adapted
            # prorrata inflections, HÉA's lowercase prose form, the common
            # intraközösségi adjective, and Baleár as part of Baleár-szigetek.
            # Keep these observed forms exact; they do not admit arbitrary
            # inflections or spelling variants.
            "hozzáadottérték",
            "Hozzáadottérték",
            "prorratája",
            "prorratájának",
            "héa",
            "intraközösségi",
            "Baleár",
            # Exact Hungarian catalogue forms that preserve the AEAT's
            # Spanish filing vocabulary (alta/modificacion, filing classes,
            # official document titles and tax-law terms). These spellings
            # are repeated across cli.yml, application.yml, errors.yml,
            # categories.yml and wizard.yml; retain the authored source form.
            "alta",
            "modificacion",
            "complementaria",
            "rectificativa",
            "Rectificativa",
            "cuota",
            "Reglamento",
            "Censal",
            "censal",
            "Certificado",
            "certificado",
            "Situación",
            "Sede",
            "sede",
            "retenciones",
            "Retenciones",
            "autoliquidación",
            "estimación",
            "compensación",
            # Project storage/ledger terminology occurs in Hungarian operator
            # text and CLI identifiers. Hungarian suffixes attach directly;
            # admit only the exact forms observed by this audit batch.
            "bucket",
            "bucket.",
            "bucketjéhez",
            "bucketet",
            "bucketje",
            "bucketjével",
            "bucketjével.",
            "buckethez",
            "bucketben",
            "bucketben.",
            "bucketnek",
            "bucketek",
            "ledger",
            "Ledger",
            "ledgerbe",
            "ledgerbe.",
            "ledgert",
            "ledgerben",
            "ledgerből.",
            "registry",
            "Registry",
            "registryben",
            "registryt",
            "registryjét",
            "registryje",
            "hash",
            "hashje",
            "sidecar",
            "sidecarja",
            "sidecarját.",
            "sidecarokat",
            "payload",
            "payloadját.",
            # ``atomikusan`` is an ordinary Hungarian adverb in local object
            # storage error prose; the pinned dictionary omits this valid form.
            "atomikusan",
            # Repeated Hungarian operator and calculation terms absent from
            # the pinned dictionary. Preserve only forms present in the
            # current audit; in particular, casilla remains the AEAT's
            # authority-named box term with attested Hungarian case endings.
            "alparancs",
            "többműszakos",
            "őrzésben",
            "őrzési",
            "profilőrzési",
            "imputációs",
            "casillához",
            "casillához.",
            "casillákat",
            "casillák",
            "casillát",
            "bájtjai",
            "kompozálódnak",
            # Exact Hungarian forms found in operator prose and the tax
            # catalogue. A manifest is called a manifeszt in Hungarian IT
            # usage; admit only the inflections actually present in source.
            "manifeszt",
            "manifesztjét",
            "manifesztjének",
            "manifesztje",
            "manifesztet",
            "manifesztjének.",
            "kisméretű",
            "forális",
            "Forális",
            "intrakomunitáris",
            "társaságiadó",
            "Társaságiadó",
            "gyorsparancs",
            # These are literal values or names in Hungarian CLI/help text:
            # option values and the command namespace stay untranslated.
            "aeat",
            "compensar",
            "devolver",
            "ingreso",
            "domiciliación",
            "config",
            # ``auth`` is a literal runtime command namespace in help text.
            "auth",
            "relation",
            "notifications",
            "LongPathsEnabled",
            "Decimal",
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


def _spanish_legal_note_word(
    dictionary_locale: str, key: str, word: str, dictionaries: Mapping[str, DictionaryLike]
) -> bool:
    """Recognize Spanish source wording on the bilingual legal-reference surface."""
    return (
        dictionary_locale == "en"
        and key.startswith("parallel:docs/_generated/legal/")
        and ".rst:line[" in key
        and dictionaries["es"].lookup(word)
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
            if _spanish_legal_note_word(dictionary_locale, key, word, dictionaries):
                continue
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
