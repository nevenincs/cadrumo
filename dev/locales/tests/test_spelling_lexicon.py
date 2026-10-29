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

    for locale in ("en", "hu"):
        for term in ("snapshot", "snapshots", "bucket", "buckets"):
            assert not is_project_spelling(locale, term)


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
        "intracomunitarioo",
        "tipadoss",
        "autenticartee",
        "impatriadoos",
        "reintentarr",
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
    forms = ("inclusiva", "tipat", "tipats", "idempotència", "subpaquets", "subcomandament", "coteig", "indiques")
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
    ):
        assert not is_project_spelling("ca", near_miss)
    for locale in ("en", "es", "hu"):
        assert all(not is_project_spelling(locale, form) for form in forms)


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
    )
    dictionaries = load_dictionaries(REPO_ROOT)
    for form in forms:
        assert not dictionaries["hu"].lookup(form)
        assert is_project_spelling("hu", form)

    for near_miss in (
        "Intraközösségií",
        "intraközösségi",
        "ellenőrzii",
        "ellenörzi",
        "Ellenörzi",
        "szkripteltt",
        "szkripelt",
        "Ugráss",
        "ugrass",
        "szektorizáltt",
        "munkajegységg",
    ):
        assert not is_project_spelling("hu", near_miss)
    for locale in ("en", "es", "ca"):
        assert all(not is_project_spelling(locale, form) for form in forms)


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
