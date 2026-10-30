"""Project vocabulary must not conceal unrecognised prose."""

from collections import defaultdict
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.locales._spelling import load_dictionaries
from dev.locales.signal_spelling import spellcheck_catalogues
from dev.locales.signal_spelling_enrollment import check_dictionary_spelling_words, is_project_spelling

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_project_spelling_is_exact_and_language_scoped() -> None:
    for locale in ("ca", "en", "es", "hu"):
        assert is_project_spelling(locale, "Cadrumo")
        assert is_project_spelling(locale, "AEAT")
        assert not is_project_spelling(locale, "Cadrmu")
    for locale in ("en", "hu"):
        assert is_project_spelling(locale, "modelo")
        assert is_project_spelling(locale, "Modelo")
        assert not is_project_spelling(locale, "modello")
    assert not is_project_spelling("ca", "modelo")


def test_identifier_labels_are_exact_shared_technical_terms() -> None:
    for locale in ("ca", "en", "es", "hu"):
        for form in ("id", "Id", "ids", "Ids", "IDs"):
            assert is_project_spelling(locale, form)
        assert not is_project_spelling(locale, "idd")
        assert not is_project_spelling(locale, "idss")


def test_only_english_possessives_of_exact_project_stems_are_accepted() -> None:
    assert is_project_spelling("en", "Cadrumo's")
    assert is_project_spelling("en", "modelo's")
    assert not is_project_spelling("en", "Cadrmu's")
    assert not is_project_spelling("en", "modeloo's")
    assert not is_project_spelling("en", "Cadrumo'd")
    assert not is_project_spelling("hu", "Cadrumo's")


def test_provider_names_are_exact_and_only_fill_observed_dictionary_gaps() -> None:
    assert is_project_spelling("es", "Google")
    assert is_project_spelling("es", "Drive")
    assert is_project_spelling("hu", "Drive")
    for locale in ("ca", "en", "es", "hu"):
        assert not is_project_spelling(locale, "Gooogle")
        assert not is_project_spelling(locale, "Driev")
    assert not is_project_spelling("hu", "Google")
    assert not is_project_spelling("en", "Drive")


def test_product_and_technical_names_are_exact_and_language_scoped() -> None:
    for locale in ("ca", "es", "hu"):
        assert is_project_spelling(locale, "Sheets")
        assert not is_project_spelling(locale, "Sheet")
        assert not is_project_spelling(locale, "Sheeets")
    assert not is_project_spelling("en", "Sheets")

    assert is_project_spelling("es", "Python")
    assert not is_project_spelling("es", "Pythón")
    assert not is_project_spelling("ca", "Python")
    assert not is_project_spelling("hu", "Python")

    assert is_project_spelling("es", "Enter")
    assert not is_project_spelling("es", "Enteer")
    assert not is_project_spelling("ca", "Enter")
    assert not is_project_spelling("hu", "Enter")


def test_architecture_terms_are_exact_and_limited_to_spanish_and_catalan() -> None:
    for locale in ("es", "ca"):
        for term in ("snapshot", "snapshots", "bucket", "buckets"):
            assert is_project_spelling(locale, term)
        for near_miss in ("snapshott", "snapshotss", "buckett", "bucketss"):
            assert not is_project_spelling(locale, near_miss)

    for locale in ("en",):
        for term in ("snapshot", "snapshots", "bucket", "buckets"):
            assert not is_project_spelling(locale, term)
    assert is_project_spelling("hu", "bucket")
    for term in ("snapshot", "snapshots", "buckets"):
        assert not is_project_spelling("hu", term)


def test_cli_namespace_and_aeat_token_terms_are_exact_and_language_scoped() -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    for term in ("token", "tokens", "Token", "Tokens", "app", "ledger"):
        assert not dictionaries["es"].lookup(term)
        assert is_project_spelling("es", term)
    assert not dictionaries["ca"].lookup("ledger")
    assert is_project_spelling("ca", "ledger")

    for near_miss in ("tokenn", "tokenss", "Tokenn", "Tokenss", "appp", "ledgerr"):
        assert not is_project_spelling("es", near_miss)
    assert not is_project_spelling("ca", "ledgerr")
    for locale in ("ca", "en", "hu"):
        assert all(not is_project_spelling(locale, term) for term in ("token", "tokens", "Token", "Tokens", "app"))
    assert not is_project_spelling("en", "ledger")
    # Hungarian ledger forms are independently enrolled with their observed
    # suffixes, so they do not imply that the Spanish/Catalan entries are shared.
    assert is_project_spelling("hu", "ledger")


def test_spanish_cli_and_operator_terms_are_exact_and_language_scoped() -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    for term in ("resolutor", "Intro", "flags", "config"):
        assert not dictionaries["es"].lookup(term)
        assert is_project_spelling("es", term)
        # Catalan independently uses flags/config in CLI instructions and
        # Hungarian independently uses config in its runtime catalogue.
        assert not is_project_spelling("ca", term) or term in {"flags", "config"}
        assert not is_project_spelling("en", term) or term == "config"
        assert not is_project_spelling("hu", term) or term == "config"

    for near_miss in ("resolutorr", "Introo", "flagss", "configg"):
        assert not is_project_spelling("es", near_miss)


def test_platform_and_product_names_are_exact_and_language_scoped() -> None:
    for locale in ("es", "ca", "hu"):
        for name in ("Windows", "macOS", "Homebrew", "Scoop", "PyPI", "Claude"):
            assert is_project_spelling(locale, name)
        for near_miss in ("Windowss", "MacOS", "Homebreww", "Scooop", "PyP1", "Claudee"):
            assert not is_project_spelling(locale, near_miss)

    assert is_project_spelling("es", "Excel")
    assert not is_project_spelling("ca", "Excel")
    assert not is_project_spelling("hu", "Excel")
    assert not is_project_spelling("es", "Excell")

    for locale in ("es", "hu"):
        assert is_project_spelling(locale, "SQLite")
        assert not is_project_spelling(locale, "SQLlite")
    assert not is_project_spelling("ca", "SQLite")

    for locale in ("en", "ca", "hu"):
        assert not is_project_spelling(locale, "Codex")
    assert not is_project_spelling("es", "Codex")


def test_attested_english_domain_terms_are_exact_and_language_scoped() -> None:
    terms = (
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
    )
    for term in terms:
        assert is_project_spelling("en", term)
    for near_miss in (
        "counterpartyy",
        "Counterpartyy",
        "withholdinggs",
        "Withholdinggs",
        "lifecyle",
        "Lifecyle",
        "namespcae",
        "Namespcae",
        "prefight",
        "Prefight",
        "cadastrall",
        "Cadastrall",
        "handsoff",
        "Handofff",
    ):
        assert not is_project_spelling("en", near_miss)
    for locale in ("ca", "es", "hu"):
        assert all(not is_project_spelling(locale, term) for term in terms)


def test_attested_english_aeat_legal_terms_are_exact_and_language_scoped() -> None:
    terms = (
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
    )
    for term in terms:
        assert is_project_spelling("en", term)

    for near_miss in (
        "comparecensia",
        "Sedeh",
        "certificdo",
        "autoliquidacion",
        "rectifcativa",
        "rectificacion",
        "complementariaa",
        "solictud",
        "ejericio",
        "cuoat",
        "prorratta",
        "Reglamentoo",
        "apoderdao",
        "forall",
        "Navara",
        "Becham",
        "impatriadoo",
    ):
        assert not is_project_spelling("en", near_miss)

    # Hungarian independently uses several of these Spanish filing terms in
    # its localized AEAT catalogues, so only Catalan and Spanish are unscoped.
    for locale in ("ca", "es"):
        assert all(not is_project_spelling(locale, term) for term in terms)


def test_oauth_and_dehu_names_are_exact_and_scoped_to_attested_locales() -> None:
    for locale in ("es", "ca", "hu"):
        assert is_project_spelling(locale, "OAuth")
        assert is_project_spelling(locale, "DEHú")
        assert not is_project_spelling(locale, "OAUTH")
        assert not is_project_spelling(locale, "OAutH")
        assert not is_project_spelling(locale, "DEHu")
        assert not is_project_spelling(locale, "DEHÚ")

    for locale in ("en",):
        assert not is_project_spelling(locale, "DEHú")
    # OAuth is separately attested and enrolled for English above.
    assert is_project_spelling("en", "OAuth")


def test_attested_spanish_ui_forms_are_exact_and_language_scoped() -> None:
    forms = (
        "desactualizado",
        "Desactualizado",
        "desactualizados",
        "recalcular",
        "Recalcular",
        "recálculo",
        "recalcula",
        "introdúcelo",
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["es"].lookup(form)
        assert is_project_spelling("es", form)

    for near_miss in (
        "desactualizdo",
        "Desactualizdo",
        "desactualizadso",
        "recalcularr",
        "Recalcularr",
        "recaculo",
        "recalculaA",
        "introducelo",
    ):
        assert not is_project_spelling("es", near_miss)

    for locale in ("ca", "en", "hu"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_attested_spanish_tax_and_operator_forms_are_exact_and_language_scoped() -> None:
    forms = (
        "tributación",
        "contrafirmado",
        "intracomunitarias",
        "preadoptivo",
        "registral",
        "Confírmalo",
        "revísalo",
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["es"].lookup(form)
        assert is_project_spelling("es", form)

    for near_miss in (
        "tributacion",
        "contrafirmadoo",
        "intracomunitariaas",
        "preadoptivoo",
        "registrall",
        "Confirmalo",
        "revisalo",
    ):
        assert not is_project_spelling("es", near_miss)

    for locale in ("ca", "en", "hu"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_attested_spanish_runtime_and_documentation_forms_are_exact_and_language_scoped() -> None:
    forms = (
        "intracomunitaria",
        "recapitulativa",
        "minoración",
        "previsualiza",
        "sobrescritura",
        "sobrescrituras",
        "exoneración",
        "intracomunitario",
        "tipados",
        "autenticarte",
        "impatriados",
        "reintentar",
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["es"].lookup(form)
        assert is_project_spelling("es", form)

    for near_miss in (
        "intracomunitariaa",
        "recapitullativa",
        "minoracion",
        "previsualizaa",
        "sobrescrituraa",
        "sobrescrituraas",
        "exoneracion",
        "intracomunitarioo",
        "tipadoss",
        "autenticartee",
        "impatriadoos",
        "reintentarr",
    ):
        assert not is_project_spelling("es", near_miss)

    shared_legal_terms = {
        "ca": {"recapitulativa", "minoración"},
        "en": {"minoración"},
        "hu": {"minoración"},
    }
    for locale, shared_terms in shared_legal_terms.items():
        # recapitulativa and minoración are independently attested in Catalan;
        # the retained Spanish tax label minoración also occurs in English and
        # Hungarian Modelo 130 explanations.
        assert all(not is_project_spelling(locale, form) for form in forms if form not in shared_terms)
        assert not is_project_spelling(locale, "minoracion")
        assert not is_project_spelling(locale, "exoneración")


def test_frequent_attested_spanish_operator_forms_are_exact_and_language_scoped() -> None:
    forms = ("Reintentar", "Reintenta", "Configúralo", "Previsualiza", "sectorizada", "contrafirma")
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["es"].lookup(form)
        assert is_project_spelling("es", form)

    for near_miss in ("Reintentarr", "Reintentaa", "Configurálo", "Previsualizaa", "sectorizadda", "contrafirmaa"):
        assert not is_project_spelling("es", near_miss)
    for locale in ("ca", "en", "hu"):
        assert all(not is_project_spelling(locale, form) for form in forms)


def test_frequent_attested_spanish_clitic_imperatives_are_exact_and_language_scoped() -> None:
    forms = (
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
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["es"].lookup(form)
        assert is_project_spelling("es", form)

    for near_miss in (
        "configurarloo",
        "Escribelo",
        "escríbello",
        "reintentaa",
        "revisala",
        "Revísalaa",
        "escribela",
        "Escríbella",
        "activala",
        "registrala",
        "Regístralaa",
        "importalo",
        "Impórtallo",
        "confirmala",
    ):
        assert not is_project_spelling("es", near_miss)

    for locale in ("ca", "en", "hu"):
        assert all(not is_project_spelling(locale, form) for form in forms)


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
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
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
        shared_legal_names = {"Navarra", "Beckham"} if locale == "en" else set()
        assert all(not is_project_spelling(locale, form) for form in forms if form not in shared_legal_names)


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
    # The October audit found lowercase command roots and namespaces across
    # runtime catalogues, plus English diagnostic labels preserving title case.
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
    # The October locale batch repeatedly found AEAT filing terminology in
    # Hungarian prose, plus the exact inflected forms of project storage terms.
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
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
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
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
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
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
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
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
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


def test_us_english_behavior_is_recognized_without_accepting_a_typo() -> None:
    assert is_project_spelling("en", "behavior")
    assert not is_project_spelling("en", "behavor")
    assert not is_project_spelling("es", "behavior")
