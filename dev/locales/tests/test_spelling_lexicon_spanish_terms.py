"""Spanish imperative and attested tax term spelling checks."""

from collections import defaultdict
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.locales._spelling import load_dictionaries
from dev.locales.signal_spelling import spellcheck_catalogues
from dev.locales.signal_spelling_enrollment import check_dictionary_spelling_words, is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_reviewed_spanish_imperatives_keep_stress_and_check_the_whole_stem() -> None:
    forms = (
        "elimínalo",
        "Actualízalo",
        "archívalo",
        "exclúyelo",
        "restáuralo",
        "vacíalos",
        "clasifícala",
        "revísalos",
        "adjúntalo",
        "autentícate",
        # Different object gender and number on the same reviewed imperative.
        "elimínalas",
        "exclúyela",
        "vacíalo",
    )
    for form in forms:
        assert is_project_spelling("es", form)
        assert all(not is_project_spelling(locale, form) for locale in ("ca", "en", "hu"))

    for typo in (
        "eliminalo",
        "elimínallo",
        "elíminalo",
        "elimína",
        "elimínate",
        "actualizálo",
        "archívallo",
        "exclúielo",
        "restáuralaX",
        "vacÍalos",
        "clasifícalaaa",
        "adjúntalolo",
        "autentícatez",
        "autentícalo",
        "inventálo",
    ):
        assert not is_project_spelling("es", typo)


def test_spanish_imperative_spelling_flows_through_the_locale_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return False

    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: {"es": Dictionary()})
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"guide"}, {"es": {"guide": "elimínalo eliminalo elimínallo"}}, Path(".")
    )
    assert set(spelling[("es", "guide")]) == {"eliminalo", "elimínallo"}


def test_attested_spanish_tax_and_runtime_terms_are_exact_and_language_scoped() -> None:
    forms = (
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
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["es"].lookup(form)
        assert is_project_spelling("es", form)

    for near_miss in (
        "operandoss",
        "fiscalmentee",
        "direccionadoo",
        "cotitulaar",
        "subclavee",
        "atribuyentee",
        "pymess",
        "reintentarloo",
        "reintentadoo",
    ):
        assert not is_project_spelling("es", near_miss)
    for locale in ("ca", "en", "hu"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_attested_catalan_ui_forms_are_exact_and_language_scoped() -> None:
    forms = (
        "impatriats",
        "reembolcallen",
        "oblides",
        "tipada",
        "tipades",
        "bloquejants",
        "Subclau",
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["ca"].lookup(form)
        assert is_project_spelling("ca", form)

    for near_miss in (
        "impatriatss",
        "reembolcallenn",
        "oblidess",
        "tipadaa",
        "tipadess",
        "bloquejantsx",
        "Subclaus",
    ):
        assert not is_project_spelling("ca", near_miss)

    for locale in ("en", "es", "hu"):
        # Spanish independently uses the identical feminine form tipada.
        assert all(not is_project_spelling(locale, form) for form in forms if (locale, form) != ("es", "tipada"))


def test_attested_english_domain_forms_are_exact_and_language_scoped() -> None:
    forms = ("counterparties", "Counterparties", "Recapitulative", "deregistration", "Deregistration", "Depreciable")
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["en"].lookup(form)
        assert is_project_spelling("en", form)

    for near_miss in (
        "counterpartys",
        "CounterpartieS",
        "Recapitulativee",
        "deregistraton",
        "Deregistrations",
        "Depreciabble",
    ):
        assert not is_project_spelling("en", near_miss)
    for locale in ("ca", "es", "hu"):
        assert all(not is_project_spelling(locale, form) for form in forms)


@pytest.mark.parametrize(
    ("locale", "forms", "near_misses"),
    [
        (
            "en",
            ("reauthenticate", "unparseable", "idempotency", "supersession", "reviewable", "fileable", "resumable"),
            ("reauthentcate", "unparsablee", "idempotancy", "supercession", "reveiwable", "fileabble", "resumeable"),
        ),
        (
            "es",
            (
                "confírmalo",
                "Combínalo",
                "idempotente",
                "bloqueante",
                "bloqueantes",
                "tipado",
                "tipada",
                "previsualizar",
            ),
            (
                "confirmalo",
                "Combinalo",
                "idempotiente",
                "bloqueantte",
                "bloqueantess",
                "tipaddo",
                "tipadda",
                "previzualizar",
            ),
        ),
    ],
)
def test_reviewed_dictionary_gaps_remain_exact_and_language_scoped(
    locale: str, forms: tuple[str, ...], near_misses: tuple[str, ...]
) -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries[locale].lookup(form)
        assert is_project_spelling(locale, form)
    for near_miss in near_misses:
        assert not is_project_spelling(locale, near_miss)
    for other_locale in {"en", "es", "ca", "hu"} - {locale}:
        # tipada is independently attested in both Spanish and Catalan prose.
        assert all(
            not is_project_spelling(other_locale, form) for form in forms if (other_locale, form) != ("ca", "tipada")
        )


def test_reviewed_prose_enrollment_does_not_accept_related_identifiers() -> None:
    for locale in ("en", "es", "ca", "hu"):
        for identifier in ("AeatAuthenticator", "reauthenticate()", "idempotency_key", "fetch_gated"):
            assert not is_project_spelling(locale, identifier)


def test_attested_catalan_technical_forms_are_exact_and_language_scoped() -> None:
    forms = (
        "inclusiva",
        "tipat",
        "tipats",
        "idempotència",
        "subpaquets",
        "subcomandament",
        "coteig",
        "indiques",
        "practiques",
        "recapitulativa",
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["ca"].lookup(form)
        assert is_project_spelling("ca", form)

    for near_miss in (
        "inclusivaa",
        "tipatt",
        "tipatss",
        "idempotencia",
        "subpaquetss",
        "subcomandamentt",
        "coteigg",
        "indiquess",
        "practiquess",
        "recapitullativa",
    ):
        assert not is_project_spelling("ca", near_miss)
    for locale in ("en", "es", "hu"):
        # Catalan and Spanish both use the standard form recapitulativa.
        assert all(
            not is_project_spelling(locale, form) for form in forms if (locale, form) != ("es", "recapitulativa")
        )


def test_catalan_runtime_tokens_are_exact_and_language_scoped() -> None:
    forms = ("aeat", "config", "flags", "status", "hash", "payload", "backend", "runtime")
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["ca"].lookup(form)
        assert is_project_spelling("ca", form)

    for near_miss in (
        "aeatt",
        "confg",
        "flagss",
        "stauts",
        "hahs",
        "payloadd",
        "backkend",
        "runtme",
    ):
        assert not is_project_spelling("ca", near_miss)

    independently_attested = {
        "en": {"aeat", "config", "backend"},
        "es": {"aeat", "config", "flags", "hash", "backend"},
        "hu": {"aeat", "config", "hash", "payload"},
    }
    for locale, shared_forms in independently_attested.items():
        assert all(not is_project_spelling(locale, form) for form in forms if form not in shared_forms)


def test_attested_catalan_forms_are_enrolled_exactly() -> None:
    forms = ("sublímit", "preomplert", "reanomenament", "reprenable")
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["ca"].lookup(form)
        assert is_project_spelling("ca", form)

    for misspelling in ("sublimit", "preomplertaX", "reanomenamentt", "reprenible"):
        assert not is_project_spelling("ca", misspelling)
    for locale in ("en", "es", "hu"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_aeat_census_period_tokens_are_exact_and_language_scoped() -> None:
    forms_by_locale = {
        "es": ("alta", "modificacion", "baja"),
        "ca": ("alta", "modificacion", "baja", "comunicacion", "variacion"),
    }
    dictionaries = load_dictionaries(REPO_ROOT)
    for locale, forms in forms_by_locale.items():
        for form in forms:
            # Some literal AEAT values are already in the locale dictionary;
            # only dictionary gaps need an explicit project spelling entry.
            if not dictionaries[locale].lookup(form):
                assert is_project_spelling(locale, form)
        for near_miss in ("altasx", "modificacionx", "bajaa", "comunicacionx", "variacionx"):
            assert not is_project_spelling(locale, near_miss)
        other_locales = {"en", "hu"}
        for other_locale in other_locales:
            assert all(
                not is_project_spelling(other_locale, form)
                for form in forms
                if not (other_locale == "hu" and form in {"alta", "modificacion"})
            )


def test_attested_hungarian_forms_are_exact_and_language_scoped() -> None:
    forms = (
        "Intraközösségi",
        "ellenőrzi",
        "Ellenőrzi",
        "szkriptelt",
        "Ugrás",
        "ugrás",
        "szektorizált",
        "munkajegység",
        "hozzáadottérték",
        "Hozzáadottérték",
        "prorratája",
        "prorratájának",
        "héa",
        "intraközösségi",
        "Baleár",
    )
    for form in forms:
        assert is_project_spelling("hu", form)

    for near_miss in (
        "Intraközösségií",
        "ellenőrzii",
        "ellenörzi",
        "Ellenörzi",
        "szkripteltt",
        "szkripelt",
        "Ugráss",
        "ugrass",
        "szektorizáltt",
        "munkajegységg",
        "hozzáadottértékk",
        "prorratájánakk",
        "héá",
        "Baleárr",
    ):
        assert not is_project_spelling("hu", near_miss)
    for locale in ("en", "es", "ca"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_hungarian_aeat_names_and_jurisdictions_are_exact_and_scoped() -> None:
    forms = ("Navarra", "Beckham", "Agencia", "Estatal", "Administración", "Tributariánál")
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
        assert is_project_spelling("hu", form)

    for near_miss in ("Navara", "Becham", "Agenciaa", "Estatall", "Administracion", "Tributarianál"):
        assert not is_project_spelling("hu", near_miss)
    for locale in ("en", "es", "ca"):
        shared_legal_names = {"Navarra", "Beckham"} if locale == "en" else {"Beckham"}
        assert all(not is_project_spelling(locale, form) for form in forms if form not in shared_legal_names)


@pytest.mark.parametrize("locale", ["es", "ca"])
def test_impatriate_regime_surname_keeps_its_exact_spelling(locale: str) -> None:
    dictionary = load_dictionaries(REPO_ROOT)[locale]
    assert not dictionary.lookup("Beckham")
    assert is_project_spelling(locale, "Beckham")
    for near_miss in ("Becham", "Beckam", "Beckhamm", "beckham", "BECKHAM"):
        assert not is_project_spelling(locale, near_miss)
    term = "impatriado" if locale == "es" else "impatriat"
    assert not dictionary.lookup(term)
    assert is_project_spelling(locale, term)
    assert not is_project_spelling(locale, term + "x")


def test_audit_hungarian_terms_and_cli_tokens_are_exact_and_language_scoped() -> None:
    forms = (
        "manifeszt",
        "manifesztjét",
        "manifesztjének",
        "manifesztje",
        "manifesztet",
        "kisméretű",
        "forális",
        "Forális",
        "intrakomunitáris",
        "társaságiadó",
        "Társaságiadó",
        "gyorsparancs",
        "aeat",
        "compensar",
        "devolver",
        "ingreso",
        "domiciliación",
        "config",
        "relation",
        "notifications",
        "LongPathsEnabled",
        "Decimal",
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
        assert is_project_spelling("hu", form)

    for near_miss in (
        "manifesztjétt",
        "kisméretűű",
        "forálisx",
        "társaságiadós",
        "gyorsparancszz",
        "compensarr",
        "LongPathsEnabledd",
        "Decimall",
    ):
        assert not is_project_spelling("hu", near_miss)

    independently_attested = {
        "en": {"aeat", "config"},
        "es": {"aeat", "config"},
        "ca": {"aeat", "config"},
    }
    for locale in ("en", "es", "ca"):
        allowed = independently_attested.get(locale, set())
        assert all(not is_project_spelling(locale, form) for form in forms if form not in allowed)


def test_audit_cli_roots_and_auth_config_labels_are_exact_and_language_scoped() -> None:
    expected = {
        "en": {"aeat", "auth", "Auth", "config", "Config"},
        "es": {"aeat", "auth", "config"},
        "ca": {"aeat", "auth", "config"},
        "hu": {"aeat", "auth", "config"},
    }
    for locale, forms in expected.items():
        for form in forms:
            assert is_project_spelling(locale, form)

    for locale in ("en", "es", "ca", "hu"):
        assert not is_project_spelling(locale, "autth")
        assert not is_project_spelling(locale, "confg")
        assert not is_project_spelling(locale, "aeatt")
        assert all(not is_project_spelling(locale, form) for form in {"Auth", "Config"} - expected.get(locale, set()))


def test_audit_attested_hungarian_aeat_and_runtime_terms_are_exact_and_language_scoped() -> None:
    forms = (
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
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
        assert is_project_spelling("hu", form)

    for near_miss in (
        "altá",
        "modificacioon",
        "complementariaa",
        "rectificativaa",
        "cuotaa",
        "Reglamentoo",
        "Censál",
        "Certificádo",
        "Situacióñ",
        "Sedea",
        "retencioness",
        "autoliquidaciónn",
        "estimacíon",
        "compensacióon",
        "buckett",
        "bucketjévelx",
        "ledgerr",
        "registryyx",
        "hashjeee",
        "sidecarjaaa",
        "payloadjátx.",
    ):
        assert not is_project_spelling("hu", near_miss)

    shared_runtime_forms = {
        "en": {
            "alta",
            "modificacion",
            "bucket",
            "ledger",
            # English AEAT explanations retain these Spanish legal terms;
            # Hungarian uses them independently in its localized catalogues.
            "complementaria",
            "rectificativa",
            # The English filing-kind label is capitalised as AEAT names it.
            "Rectificativa",
            "cuota",
            "Reglamento",
            "certificado",
            "Sede",
            "autoliquidación",
        },
        # The Spanish runtime uses hash as the term for content/storage
        # digests, independently of Hungarian's inflected storage vocabulary.
        "es": {"alta", "modificacion", "bucket", "ledger", "hash"},
        "ca": {"alta", "modificacion", "bucket", "ledger", "hash", "payload"},
    }
    for locale, shared_forms in shared_runtime_forms.items():
        # These exact forms have independent runtime attestations in the
        # indicated locale; all other Hungarian entries remain locale-scoped.
        assert all(not is_project_spelling(locale, form) for form in forms if form not in shared_forms)


def test_repeated_hungarian_operator_and_tax_forms_are_exact_and_language_scoped() -> None:
    forms = (
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
    )
    for form in forms:
        assert is_project_spelling("hu", form)

    for near_miss in (
        "alparancss",
        "többműszakoss",
        "őrzésbenn",
        "őrzésii",
        "profilőrzésii",
        "imputációss",
        "casilláhóz",
        "casillákatx",
        "casillákk",
        "casillátt",
        "bájtjaikk",
        "kompozálódnakx",
    ):
        assert not is_project_spelling("hu", near_miss)

    for locale in ("en", "es", "ca"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_hungarian_local_storage_adverb_is_exact_and_language_scoped() -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    assert not dictionaries["hu"].lookup("atomikusan")
    assert is_project_spelling("hu", "atomikusan")
    assert not is_project_spelling("hu", "atomikusann")
    for locale in ("en", "es", "ca"):
        assert not is_project_spelling(locale, "atomikusan")


def test_audit_attested_hungarian_name_inflections_are_exact_and_language_scoped() -> None:
    forms = (
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
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
        assert is_project_spelling("hu", form)

    for near_miss in (
        "cadrumóban",
        "Cadrumöban",
        "Cadrumóbank",
        "Cadrumóbaan",
        "Cadrumóhöz",
        "modelókk",
        "modelótt",
        "modellók",
        "modelótólx",
        "MODELÓK",
    ):
        assert not is_project_spelling("hu", near_miss)
    for locale in ("en", "es", "ca"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_attested_hungarian_ordinary_vocabulary_gaps_are_exact_and_language_scoped() -> None:
    # Attested in contact/auth-provider prose (téged), snapshot/error prose
    # (őt), byte-consent and key-size messages (bájtokat/bájtos), and
    # aggregation/CLI-summary prose (összegzése/összegzésével).
    forms = ("téged", "őt", "bájtokat", "bájtos", "összegzése", "összegzésével")
    for form in forms:
        assert is_project_spelling("hu", form)

    for near_miss in (
        "tége",
        "őtő",
        "bájtoakt",
        "bájtosz",
        "összegzésee",
        "összegzéséveel",
    ):
        assert not is_project_spelling("hu", near_miss)
    for locale in ("en", "es", "ca"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_additional_hungarian_operator_forms_are_exact_and_language_scoped() -> None:
    # Attested in an AEAT sync confirmation (Ellenőrzöd), byte-size/evidence
    # messages (bájt*), review queue prose (priorizálhatók), and update help
    # (megkísérléséhez).
    forms = ("Ellenőrzöd", "bájtok", "bájtban", "bájtra", "bájtként", "priorizálhatók", "megkísérléséhez")
    for form in forms:
        assert is_project_spelling("hu", form)

    for near_miss in (
        "Ellenörzöd",
        "bájttok",
        "bájtbanx",
        "bájtrra",
        "bájtkéntt",
        "priorizálhatókx",
        "megkísérléséhezz",
    ):
        assert not is_project_spelling("hu", near_miss)
    for locale in ("en", "es", "ca"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_hungarian_summary_preset_and_prose_forms_are_exact_and_language_scoped() -> None:
    # Attested in desktop summary/preset labels, free-text help, byte-related
    # custody/evidence messages, and the LLM capability description.
    forms = (
        "Összegzés",
        "Előbeállítások",
        "Szabadszöveges",
        "bájtjaik",
        "bájtjainak",
        "bájtokhoz",
        "látás",
    )
    for form in forms:
        assert is_project_spelling("hu", form)

    for near_miss in (
        "Összegzéss",
        "Előbeállításokk",
        "Szabadszövegess",
        "bájtjaikk",
        "bájtjainakk",
        "bájtokhozz",
        "látáss",
    ):
        assert not is_project_spelling("hu", near_miss)
    for locale in ("en", "es", "ca"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_hungarian_iso_year_mask_is_exact_and_language_scoped() -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    assert not dictionaries["hu"].lookup("ÉÉÉÉ")
    assert is_project_spelling("hu", "ÉÉÉÉ")
    assert not is_project_spelling("hu", "ÉÉÉÉÉ")
    assert all(not is_project_spelling(locale, "ÉÉÉÉ") for locale in ("en", "es", "ca"))


def test_spelling_enrollment_preserves_unknown_words() -> None:
    class EmptyDictionary:
        def lookup(self, word: str) -> bool:
            return False

    words = {word: {("en", "test.key")} for word in ("Cadrumo", "modelo", "reciept")}
    unknown_words: set[tuple[str, str]] = set()
    unknown_by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)
    check_dictionary_spelling_words(
        "en",
        words,
        {"en": EmptyDictionary(), "es": EmptyDictionary()},
        {("en", "test.key"): "Cadrumo modelo reciept"},
        unknown_words,
        unknown_by_cell,
    )
    assert unknown_words == {("en", "reciept")}
    assert unknown_by_cell == {("en", "test.key"): {"reciept"}}


def test_spanish_tax_terms_are_dictionary_checked_with_adjacent_prose(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def __init__(self, accepted: set[str]) -> None:
            self.accepted = accepted

        def lookup(self, word: str) -> bool:
            return word in self.accepted

    dictionaries = {"en": Dictionary({"Read"}), "es": Dictionary({"bienes", "de"})}
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    spelling, inventory, _findings = spellcheck_catalogues(
        {"guide"}, {"en": {"guide": "Read bienes de inversión misspeling"}}, Path(".")
    )

    assert set(spelling[("en", "guide")]) == {"inversión", "misspeling"}
    assert inventory["spelling_unknown_words"] == 2


def test_category_search_keywords_allow_only_dictionary_backed_accentless_spanish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Dictionary:
        def __init__(self, accepted: set[str]) -> None:
            self.accepted = accepted

        def lookup(self, word: str) -> bool:
            return word in self.accepted

    dictionaries = {
        "en": Dictionary(set()),
        "es": Dictionary({"amortización", "vivienda"}),
    }
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    key = "desktop.ledger.category_keywords.amortizacion_vivienda_afecto"
    spelling, inventory, _findings = spellcheck_catalogues(
        {key}, {"en": {key: "amortizacion vivienda vvienda"}}, Path(".")
    )

    assert spelling == {("en", key): ("vvienda",)}
    assert inventory["spelling_unknown_words"] == 1


@pytest.mark.parametrize("locale", ("en", "ca", "es", "hu"))
@pytest.mark.parametrize(
    ("category", "alias", "mutated"),
    (
        ("asesoria_contable", "gestoria", "gestorria"),
        ("asesoria_fiscal", "gestoria", "gestorria"),
        ("subcontratacion", "subcontratacion", "subcontrattacion"),
        ("suministros_home_office_gas", "butano", "buttano"),
    ),
)
def test_attested_category_aliases_require_the_exact_key_and_token(
    monkeypatch: pytest.MonkeyPatch, locale: str, category: str, alias: str, mutated: str
) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return False

    monkeypatch.setattr(
        "dev.locales.signal_spelling.load_dictionaries",
        lambda repository: {language: Dictionary() for language in ("en", "ca", "es", "hu")},
    )
    key = f"desktop.ledger.category_keywords.{category}"
    other_keys = (
        key + ".extra",
        key + "_other",
        "desktop.ledger.category_keywords.unrelated",
        f"desktop.ledger.categories.{category}",
        "guide",
    )
    text = f"{alias} {mutated} misspeling"
    values: dict[str, object] = {candidate: text for candidate in (key, *other_keys)}
    spelling, _inventory, _findings = spellcheck_catalogues(set(values), {locale: values}, REPO_ROOT)

    assert set(spelling[(locale, key)]) == {mutated, "misspeling"}
    for candidate in other_keys:
        assert set(spelling[(locale, candidate)]) == {alias, mutated, "misspeling"}
    assert not is_project_spelling(locale, alias)


def test_hungarian_abbreviations_require_the_complete_dictionary_form(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word == "pl."

    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: {"hu": Dictionary()})
    spelling, _inventory, _findings = spellcheck_catalogues({"guide"}, {"hu": {"guide": "pl. pl hibásszó."}}, Path("."))

    assert set(spelling[("hu", "guide")]) == {"pl", "hibásszó."}


def test_real_dictionaries_check_names_abbreviations_and_sentence_ends(monkeypatch: pytest.MonkeyPatch) -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"guide", "name", "typo"},
        {
            "hu": {"guide": "őket. sorok. összeget. pl. pl hibásszó."},
            "en": {"name": "Cl@ve Móvil misspeling", "typo": "Cl@ve Móvill Cl@vee Móvil"},
        },
        REPO_ROOT,
    )

    assert set(spelling[("hu", "guide")]) == {"pl", "hibásszó."}
    assert spelling[("en", "name")] == ("misspeling",)
    assert set(spelling[("en", "typo")]) == {"Móvill", "vee", "Móvil"}


@pytest.mark.parametrize(
    ("locale", "word"),
    [("en", word) for word in ("transitorily", "unseizable", "registrable", "uncollectible", "unapplied", "sublessee")]
    + [
        ("es", word)
        for word in (
            "caución",
            "tautológica",
            "enrutado",
            "autoritativo",
            "exoneraciones",
            "improcedentemente",
            "reinvertida",
            "enchufables",
            "indisponible",
            "autorrepercusión",
            "cofinanciadoras",
        )
    ],
)
def test_attested_legal_note_words_keep_their_language_and_reject_typos(locale: str, word: str) -> None:
    assert is_project_spelling(locale, word)
    assert not is_project_spelling(locale, word + "qq")
    for other in {"en", "ca", "es", "hu"} - {locale}:
        assert not is_project_spelling(other, word)


def test_us_english_behavior_is_recognized_without_accepting_a_typo() -> None:
    assert is_project_spelling("en", "behavior")
    assert not is_project_spelling("en", "behavor")
    assert not is_project_spelling("es", "behavior")


def test_english_possessives_require_a_real_dictionary_base() -> None:
    values = {"en": {"example": "descriptor's resolver’s someone else's descriptorr's resolvver's"}}
    unknown, inventory, _ = spellcheck_catalogues(set(), {}, REPO_ROOT, additional_values=values)
    assert not inventory["spelling_tool_failures"]
    assert set(unknown[("en", "example")]) == {"descriptorr's", "resolvver's"}


def test_reviewed_technical_nouns_keep_bounded_plural_and_case() -> None:
    for word in (
        "codebase",
        "codebases",
        "entrypoint",
        "entrypoints",
        "Entrypoints",
        "docstring",
        "Docstrings",
        "subpackage",
        "subcommands",
        "checksums",
        "Checksums",
        "lookups",
        "Wireframe",
        "rulebook",
        "enums",
        "parsers",
        "Filesystem",
        "ciphertext",
        "toolchains",
        "ruleset",
        "basename",
        "allowlist",
        "walkthrough",
    ):
        assert is_project_spelling("en", word)
        for locale in ("ca", "es", "hu"):
            assert not is_project_spelling(locale, word)
    for typo in (
        "codebasse",
        "entrypointss",
        "ENTrypoints",
        "docstrngs",
        "subpackege",
        "subcommandss",
        "checksumss",
        "wireframme",
        "enumss",
        "ciphertex",
        "walkthruogh",
    ):
        assert not is_project_spelling("en", typo)
    assert is_project_spelling("en", "ZIPs")
    assert is_project_spelling("en", "UUIDs")
    assert is_project_spelling("en", "uploadable")
    for word in ("untagged", "recoverability", "reachability", "decrypts", "rescans", "rehydration", "untyped"):
        assert is_project_spelling("en", word)
        assert not is_project_spelling("en", word + "x")
    for typo in ("ZIPss", "zipS", "UUIDss", "UuidS", "uploadible"):
        assert not is_project_spelling("en", typo)


def test_reference_us_english_forms_are_exact_and_do_not_accept_nearby_typos() -> None:
    forms = (
        "Adapters",
        "afterward",
        "amortized",
        "authorizes",
        "capitalized",
        "categorized",
        "center",
        "color",
        "enrollments",
        "finalizes",
        "judgment",
        "memorize",
        "modeled",
        "notarized",
        "personalized",
        "recognizable",
        "serializes",
        "specialized",
        "specialty",
        "summarizes",
    )
    for form in forms:
        assert is_project_spelling("en", form)
        assert not is_project_spelling("en", form + "x")
        for locale in ("ca", "es", "hu"):
            assert not is_project_spelling(locale, form)
    for typo in ("authorizess", "categorizd", "enrollmentss", "personallized", "sumarizes"):
        assert not is_project_spelling("en", typo)


def test_reviewed_technical_forms_keep_exact_spelling_and_language_scope() -> None:
    forms = (
        "discardable",
        "undecryptable",
        "unhandled",
        "untrusted",
        "Unmapped",
        "computable",
        "Telecoms",
        "upgrader",
        "Subcode",
        "Sectorised",
        "Foral",
        "unremitted",
        "Unremitted",
        "unbundled",
        "derogations",
        "domiciliation",
        "ungrounded",
        "regenerable",
    )
    for form in forms:
        assert is_project_spelling("en", form)
        assert not is_project_spelling("en", form + "x")
        for locale in ("ca", "es", "hu"):
            # The same adjective is independently attested in Spanish.
            assert is_project_spelling(locale, form) == (locale == "es" and form == "regenerable")
    for typo in (
        "discardible",
        "undecryptible",
        "unhandld",
        "untrustted",
        "Unmaped",
        "Sectorizedd",
        "Forall",
        "unremited",
        "domicilliation",
        "ungroundded",
        "regenerible",
    ):
        assert not is_project_spelling("en", typo)


def test_hungarian_attested_name_and_tax_term_inflections_remain_exact() -> None:
    forms = (
        "Cadrumóról",
        "Bizkaiának",
        "Gipuzkoának",
        "Navarrának",
        "Navarrában",
        "Anától",
        "Anának",
        "Anára",
        "Rentánál",
        "Rentára",
        "Rentához",
        "Tributariának",
        "Tributariával",
        "Tributariához",
        "Timbrével",
        "Macre",
        "prorratának",
        "prorratához",
        "prorratájára",
        "altával",
        "complementariát",
        "soportadót",
    )
    for form in forms:
        assert is_project_spelling("hu", form)
        assert not is_project_spelling("hu", form + "x")
        for locale in ("en", "ca", "es"):
            assert not is_project_spelling(locale, form)
    for typo in ("Cadrumoról", "Bizkaiánakx", "Gipuzkoanak", "Anatól", "Rentanal", "Tributarianak"):
        assert not is_project_spelling("hu", typo)


def test_hungarian_attested_native_technical_forms_keep_typo_checks() -> None:
    forms = (
        "ellenaláírás",
        "imputáció",
        "imputációhoz",
        "bájtokból",
        "főrovat",
        "borostyánsárgára",
        "Szkriptelt",
        "szkriptelhető",
        "szkriptelheted",
        "gyorsítótárazza",
        "regularizációs",
    )
    for form in forms:
        assert is_project_spelling("hu", form)
        assert not is_project_spelling("hu", form + "x")
        for locale in ("en", "ca", "es"):
            assert not is_project_spelling(locale, form)
    for typo in ("ellenalairas", "imputaciohoz", "bajtokbol", "forovat", "szkriptelhetó"):
        assert not is_project_spelling("hu", typo)
