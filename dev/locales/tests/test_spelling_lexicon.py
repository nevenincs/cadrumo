"""Project vocabulary must not conceal unrecognised prose."""

from collections import defaultdict

import pytest

from dev.locales.signal_spelling import spellcheck_catalogues
from dev.locales.signal_spelling_enrollment import check_dictionary_spelling_words, is_project_spelling
from dev.locales.signal_spelling_segments import is_known_residence_region_label
from dev.locales.spelling import load_dictionaries
from dev.paths import REPO_ROOT

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


def test_attested_iva_territory_names_do_not_admit_typos() -> None:
    for name in ("Akrotiri", "Dhekelia", "Balears"):
        assert is_project_spelling("en", name)
        assert not is_project_spelling("en", name + "x")
    assert not is_project_spelling("en", "Illes")


def test_english_redaction_version_terms_are_exact() -> None:
    for word in ("redaction", "redactions"):
        assert is_project_spelling("en", word)
    assert not is_project_spelling("en", "redactionss")


def test_english_legal_roles_keep_case_possessive_and_typo_boundaries() -> None:
    for word in (
        "declarant",
        "Declarant",
        "declarants",
        "Declarants",
        "countersigner",
        "preadoptive",
        "Preadoptive",
        "deserialised",
        "Impatriate",
    ):
        assert is_project_spelling("en", word)
        assert not is_project_spelling("en", word + "x")
        for locale in ("ca", "es", "hu"):
            assert not is_project_spelling(locale, word)
    for word in ("declarant's", "Declarant's", "countersigner's"):
        assert is_project_spelling("en", word)
    for word in ("declerant", "declerant's", "countersingner's", "preadopptiv"):
        assert not is_project_spelling("en", word)


def test_attested_english_technical_words_remain_exact_and_language_scoped() -> None:
    words = (
        "updatable",
        "toolset",
        "cutover",
        "ungrouped",
        "stylesheet",
        "misconfigured",
        "unresolvable",
        "deregistered",
        "Deregistered",
        "scriptable",
        "unpromoted",
        "handoffs",
    )
    for word in words:
        assert is_project_spelling("en", word)
        assert not is_project_spelling("en", word + "x")
        for locale in ("ca", "es", "hu"):
            assert not is_project_spelling(locale, word)
    assert not is_project_spelling("en", "unresolveable")
    assert not is_project_spelling("en", "styleesheet")


def test_english_citation_retains_exact_aeat_terms_and_possessives() -> None:
    for word in ("casilla", "casilla's", "borrador", "borrador's"):
        assert is_project_spelling("en", word)
        assert not is_project_spelling("en", word + "x")


@pytest.mark.parametrize(
    "locale,words",
    [
        (
            "es",
            (
                "diferimiento",
                "sublímite",
                "heurística",
                "discrepante",
                "Discrepante",
                "manejador",
                "inicialización",
                "recompilación",
                "derivable",
                "multicomponente",
                "notarizada",
                "renderizó",
                "reescanea",
                "reclasifica",
                "previsualizarla",
            ),
        ),
        ("ca", ("notaritzada",)),
        ("hu", ("áthozata", "áthozatra", "áthozatokat", "alparancsok", "teendőlista")),
    ],
)
def test_reviewed_native_forms_keep_language_and_typo_boundaries(locale: str, words: tuple[str, ...]) -> None:
    for word in words:
        assert is_project_spelling(locale, word)
        assert not is_project_spelling(locale, word + "x")
        for other in {"ca", "en", "es", "hu"} - {locale}:
            assert not is_project_spelling(other, word)


def test_identifier_labels_are_exact_shared_technical_terms() -> None:
    for locale in ("ca", "en", "es", "hu"):
        for form in ("id", "Id", "ids", "Ids", "IDs"):
            assert is_project_spelling(locale, form)
        assert not is_project_spelling(locale, "idd")
        assert not is_project_spelling(locale, "idss")
        for territory in ("Álava", "Guipúzcoa", "Vizcaya", "Bizkaia", "Gipuzkoa"):
            assert is_project_spelling(locale, territory)
            assert not is_project_spelling(locale, territory + "x")
        for typo in ("bizkaia", "Bizkaiaa", "Gipuzkora", "GipuzkoaX"):
            assert not is_project_spelling(locale, typo)


@pytest.mark.parametrize("locale", ["ca", "en", "es", "hu"])
def test_software_proper_names_preserve_exact_case_and_stem_boundaries(locale: str) -> None:
    for name in (
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
    ):
        assert is_project_spelling(locale, name)
        assert not is_project_spelling(locale, name + "x")
    for bad in (
        "Appel",
        "apple",
        "Bizumm",
        "Diátaxiss",
        "Diataxis",
        "GitHup",
        "Linuz",
        "Markdwon",
        "OpenSSl",
        "Powershell",
        "Pydantci",
        "Sphinxx",
        "popplre",
        "reStructuredTex",
    ):
        assert not is_project_spelling(locale, bad)


def test_retained_persona_and_hungarian_payment_name_are_exact_and_scoped() -> None:
    for locale in ("ca", "hu"):
        assert is_project_spelling(locale, "Ana")
        assert is_project_spelling(locale, "García")
        for typo in ("Anas", "anaa", "Garciaa"):
            assert not is_project_spelling(locale, typo)
    assert is_project_spelling("hu", "López")
    assert is_project_spelling("hu", "Bizummal")
    for typo in ("Bizumval", "Bizumal", "bizummal", "Bizummall"):
        assert not is_project_spelling("hu", typo)
    for locale in ("ca", "en", "es"):
        assert not is_project_spelling(locale, "Bizummal")


def test_attested_spanish_technical_forms_are_bounded_by_language_and_spelling() -> None:
    words = (
        "Subpaquetes",
        "subpaquetes",
        "editables",
        "recompila",
        "serializa",
        "recapitulativo",
        "precalculado",
        "extrapolación",
        "rehidratación",
        "instalable",
        "reintentos",
        "reembolsos",
        "resolvedor",
        "automatizable",
        "renderice",
        "recalculada",
        "recalculando",
        "recalcules",
        "reclasificas",
        "modifícalos",
        "regenérala",
    )
    for word in words:
        assert is_project_spelling("es", word)
        assert not is_project_spelling("es", word + "x")
        for locale in ("ca", "en", "hu"):
            assert not is_project_spelling(locale, word)
    for typo in (
        "subpaqueetes",
        "editabless",
        "recompilla",
        "serialisa",
        "recapitulatibo",
        "reuna",
        "regenerala",
        "resolvedorr",
        "automatizabble",
        "renderize",
    ):
        assert not is_project_spelling("es", typo)


def test_attested_catalan_verb_and_technical_forms_keep_exact_language_and_spelling() -> None:
    for word in ("publiques", "especifiques", "recapitulatiu", "recomprovació", "enllaçable", "inclusives", "calcules"):
        assert is_project_spelling("ca", word)
        assert not is_project_spelling("ca", word + "x")
        for locale in ("en", "es", "hu"):
            assert not is_project_spelling(locale, word)
    for typo in ("publiquess", "especifiqes", "recapitulatiuu", "recomprovacio", "enllacable", "inclusivess"):
        assert not is_project_spelling("ca", typo)


def test_reference_hunspell_hungarian_forms_preserve_case_locale_and_typo_checks() -> None:
    # Each form was independently accepted by reference Hunspell using the
    # exact original dictionary whose digest is pinned in our source receipt.
    forms = (
        "Adatvédelmi",
        "Felülvizsgálati",
        "Késedelmi",
        "Nagyvállalati",
        "Pénzforgalmi",
        "adatbázisbájtjait",
        "adatvédelmi",
        "ellenőrzik",
        "ellenőrzöd",
        "ellenőrzöl",
        "előtakarékossági",
        "jövedelmi",
        "komponensbájtot",
        "nagyvállalati",
        "netót",
        "percentiliseit",
        "pozicionális",
        "pénzforgalmi",
        "áthozatot",
        "érintetti",
        "örökbefogadási",
    )
    for form in forms:
        assert is_project_spelling("hu", form)
        assert not is_project_spelling("hu", form + "x")
        for locale in ("ca", "en", "es"):
            assert not is_project_spelling(locale, form)
    for typo in ("barmit", "felülvizsgalati", "pénzforgalmii", "ellenorzod", "felÜlvizsgálati"):
        assert not is_project_spelling("hu", typo)

    unknown, inventory, _ = spellcheck_catalogues(
        set(), {}, REPO_ROOT, additional_values={"hu": {"sentence": "ellenőrzik. ellenőrzöl. ellenorzodd."}}
    )
    assert not inventory["spelling_tool_failures"]
    assert unknown[("hu", "sentence")] == ("ellenorzodd.",)


@pytest.mark.parametrize("locale,word", [("ca", "declarables"), ("es", "heredables")])
def test_attested_native_plurals_are_exact_and_locale_scoped(locale: str, word: str) -> None:
    assert is_project_spelling(locale, word)
    assert not is_project_spelling(locale, word + "s")
    assert not is_project_spelling(locale, word.capitalize())
    for other in {"ca", "en", "es", "hu"} - {locale}:
        assert not is_project_spelling(other, word)


def test_pydantic_brand_keeps_code_literal_and_adjacent_typo_distinct() -> None:
    values = {"ca": {"example": "Pydantic `pydantic` Pydantci"}}
    unknown, inventory, _ = spellcheck_catalogues(set(), {}, REPO_ROOT, additional_values=values)
    assert not inventory["spelling_tool_failures"]
    assert unknown[("ca", "example")] == ("Pydantci",)


@pytest.mark.parametrize("locale", ["ca", "en", "es", "hu"])
def test_facturae_format_name_is_exact_and_preserves_neighbouring_typos(locale: str) -> None:
    assert is_project_spelling(locale, "Facturae")
    assert not is_project_spelling(locale, "facturae")
    assert not is_project_spelling(locale, "Facturaee")
    values = {locale: {"example": "Facturae Facturaee"}}
    unknown, inventory, _ = spellcheck_catalogues(set(), {}, REPO_ROOT, additional_values=values)
    assert not inventory["spelling_tool_failures"]
    assert "Facturaee" in unknown[(locale, "example")]
    assert not is_project_spelling("ca", "pydantic")


@pytest.mark.parametrize(
    ("locale", "forms"),
    [
        (
            "en",
            (
                "approver",
                "checkable",
                "durations",
                "impatriate",
                "namespaces",
                "preadoptive",
                "prefill",
                "Prefill",
                "prefilled",
                "unassessed",
                "unindexed",
                "unlink",
                "unsupplied",
                "withholder",
                "withholders",
            ),
        ),
        ("es", ("idempotencia", "reintentos", "sectorizado", "serialización", "megabytes")),
        ("ca", ("declarable", "Preomple", "subpaquet", "subpaquets", "Subpaquets")),
        (
            "hu",
            (
                "bájtokkal",
                "bájtjait",
                "bájtnál",
                "bájtszámát",
                "megabájt",
                "felülvizsgálati",
                "kisvállalati",
                "tartalmi",
            ),
        ),
    ],
)
def test_attested_current_terms_are_exact_and_belong_to_their_locale(locale: str, forms: tuple[str, ...]) -> None:
    for form in forms:
        assert is_project_spelling(locale, form)
        assert not is_project_spelling(locale, form + "x")
        assert not is_project_spelling(locale, form.upper())
        for other in {"en", "es", "ca", "hu"} - {locale}:
            assert not is_project_spelling(other, form)


def test_attested_forms_do_not_hide_nearby_typos_or_untranslated_prose() -> None:
    values = {
        "en": {"message": "An approver checks an unindexed item with modificacion and misspeling."},
        "es": {"message": "Los reintentos requieren idempotencia y idempotensia."},
        "ca": {"message": "Preomple la dada declarable i declarabll."},
        "hu": {"message": "A bájtokkal és bájtjait mellett a bájtokkall hibás."},
    }
    unknown, inventory, _ = spellcheck_catalogues(set(), {}, REPO_ROOT, additional_values=values)
    assert not inventory["spelling_tool_failures"]
    assert {"modificacion", "misspeling"} <= set(unknown[("en", "message")])
    assert "idempotensia" in unknown[("es", "message")]
    assert "declarabll" in unknown[("ca", "message")]
    assert "bájtokkall" in unknown[("hu", "message")]


@pytest.mark.parametrize(
    "locale,region,label",
    [
        ("en", "cantabria", "Cantabria"),
        ("en", "castilla_la_mancha", "Castilla-La Mancha"),
        ("en", "castilla_la_mancha", "Castile-La Mancha"),
        ("en", "castilla_y_leon", "Castilla y León"),
        ("en", "castilla_y_leon", "Castile and León"),
        ("en", "ceuta", "Ceuta (autonomous city)"),
        ("en", "melilla", "Melilla (autonomous city)"),
        ("en", "comunidad_valenciana", "Valencian Community"),
        ("en", "extremadura", "Extremadura"),
        ("en", "galicia", "Galicia"),
        ("en", "la_rioja", "La Rioja"),
        ("hu", "castilla_la_mancha", "Kasztília-La Mancha"),
        ("hu", "asturias", "Asztúria"),
        ("hu", "cantabria", "Kantábria"),
        ("hu", "extremadura", "Extremadura"),
        ("hu", "galicia", "Galicia"),
        ("hu", "la_rioja", "La Rioja"),
        ("hu", "murcia", "Murcia"),
        ("hu", "ceuta", "Ceuta (autonóm város)"),
        ("hu", "melilla", "Melilla (autonóm város)"),
        ("es", "andalucia", "Andalucía"),
    ],
)
@pytest.mark.parametrize(
    "key_template",
    ["profile.schema.field.tax_residence.ccaa.choices.{}", "wizard.setup.residence.ccaa.choices.{}.label"],
)
def test_reviewed_residence_names_are_whole_labels_under_their_actual_region(
    locale: str, region: str, label: str, key_template: str
) -> None:
    from cadrumo.core.toml import parse_toml

    source = parse_toml(
        (REPO_ROOT / "src/cadrumo/_data/registry/aeat/facts/0129-renta-ccaa-tax-residence-catalogue.toml").read_text(
            encoding="utf-8"
        )
    )
    entries = {row["key"]: row["value"] for row in source["fact"]["variants"][0]["payload"]["entries"]}
    assert entries[f"ccaa.{region}.value"] == region
    key = key_template.format(region)
    assert is_known_residence_region_label(locale, key, label)
    assert not is_known_residence_region_label(locale, key, label + " misspellledd")
    assert not is_known_residence_region_label(locale, key, label + "x")
    assert not is_known_residence_region_label(locale, key, label.swapcase())
    assert not is_known_residence_region_label(locale, key_template.format("madrid"), label)
    assert not is_known_residence_region_label(locale, "application.test.prose", label)
    other_locale = "en" if locale == "es" else "es"
    assert not is_known_residence_region_label(other_locale, key, label)


def test_residence_name_recognition_does_not_hide_extra_or_misspelled_prose() -> None:
    key = "profile.schema.field.tax_residence.ccaa.choices.galicia"
    values = {"en": {key: "Galicia", "application.test.typo": "Galicia misspellledd"}}
    unknown, inventory, _ = spellcheck_catalogues(set(), {}, REPO_ROOT, additional_values=values)
    assert not inventory["spelling_tool_failures"]
    assert ("en", key) not in unknown
    assert "misspellledd" in unknown[("en", "application.test.typo")]


def test_hungarian_documentation_format_and_builder_names_keep_exact_case_and_typo_checks() -> None:
    names = ("Markdown", "reStructuredText", "Sphinx")
    for name in names:
        assert is_project_spelling("hu", name)
        assert not is_project_spelling("hu", name.lower())
        assert not is_project_spelling("hu", name.upper())
        assert not is_project_spelling("hu", name + "x")
    unknown: set[tuple[str, str]] = set()
    by_cell: dict[tuple[str, str], set[str]] = defaultdict(set)

    class EmptyDictionary:
        def lookup(self, word: str) -> bool:
            return False

    key = "parallel:docs/locales/hu/LC_MESSAGES/authoring-guide.po:test"
    words = (*names, "Markdwon", "reStructuredTex", "Sphinxx", "ordinaryenglish", "misspellledd")
    check_dictionary_spelling_words(
        "hu",
        {word: {("hu", key)} for word in words},
        {"hu": EmptyDictionary()},
        {("hu", key): " ".join(words)},
        unknown,
        by_cell,
    )
    assert by_cell[("hu", key)] == {"Markdwon", "reStructuredTex", "Sphinxx", "ordinaryenglish", "misspellledd"}


def test_evidence_format_and_source_names_preserve_nearby_typo_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    for locale in dictionaries:
        assert not dictionaries[locale].lookup("WebP")
        assert is_project_spelling(locale, "WebP")
        assert is_project_spelling(locale, "Gmail") == (locale != "ca")
        assert dictionaries[locale].lookup("Gmail") == (locale == "ca")
        for near_miss in ("WebbP", "Webp", "webP", "Gmaill", "GMail"):
            assert not is_project_spelling(locale, near_miss)
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"evidence"},
        {locale: {"evidence": "Gmail WebP WebbP Gmaill misspeling"} for locale in dictionaries},
        REPO_ROOT,
    )
    assert {cell: set(words) for cell, words in spelling.items()} == {
        (locale, "evidence"): {"WebbP", "Gmaill", "misspeling"} for locale in dictionaries
    }


def test_attested_tax_abbreviations_do_not_exempt_mixed_case_typos(monkeypatch: pytest.MonkeyPatch) -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    for locale, dictionary in dictionaries.items():
        for abbreviation in ("ITPyAJD", "LISyD"):
            assert not dictionary.lookup(abbreviation)
            assert is_project_spelling(locale, abbreviation)
        for near_miss in ("ITPyAJDD", "ITPyADJ", "LISyDD", "LISyyD", "itpyajd", "lisyd"):
            assert not is_project_spelling(locale, near_miss)
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"tax"},
        {locale: {"tax": "ITPyAJD LISyD ITPyAJDD LISyyD misspeling"} for locale in dictionaries},
        REPO_ROOT,
    )
    assert {cell: set(words) for cell, words in spelling.items()} == {
        (locale, "tax"): {"ITPyAJDD", "LISyyD", "misspeling"} for locale in dictionaries
    }


def test_input_tax_phrase_uses_spanish_without_hiding_adjacent_or_phrase_typos(monkeypatch: pytest.MonkeyPatch) -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"tax", "typo"},
        {locale: {"tax": "Cuota soportada misspeling", "typo": "cuota soportadaa"} for locale in ("en", "hu")},
        REPO_ROOT,
    )
    for locale in ("en", "hu"):
        assert spelling[(locale, "tax")] == ("misspeling",)
        assert "soportadaa" in spelling[(locale, "typo")]
    assert not is_project_spelling("en", "soportada")
    assert not is_project_spelling("hu", "soportada")


def test_bilingual_search_aliases_do_not_exempt_prose_or_misspelled_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    class Dictionary:
        def __init__(self, accepted: set[str]) -> None:
            self.accepted = accepted

        def lookup(self, word: str) -> bool:
            return word in self.accepted

    monkeypatch.setattr(
        "dev.locales.signal_spelling.load_dictionaries",
        lambda repository: {"en": Dictionary(set()), "es": Dictionary({"retenciones"})},
    )
    keys = (
        "desktop.ledger.category_keywords.ibi_local_afecto",
        "navigation.view.withholding.keywords",
        "navigation.view.withholding.label",
        "guide",
    )
    spelling, _inventory, _findings = spellcheck_catalogues(
        set(keys),
        {"en": {key: "ibi irpf retenciones ibii irpff retencioness misspeling" for key in keys}},
        REPO_ROOT,
    )
    for key in keys[:2]:
        assert set(spelling[("en", key)]) == {"ibii", "irpff", "retencioness", "misspeling"}
    for key in keys[2:]:
        assert set(spelling[("en", key)]) == {
            "ibi",
            "irpf",
            "retenciones",
            "ibii",
            "irpff",
            "retencioness",
            "misspeling",
        }
    assert not is_project_spelling("en", "ibi")
    assert not is_project_spelling("en", "irpf")


def test_observed_technical_spellings_keep_case_and_near_misses_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    dictionaries = load_dictionaries(REPO_ROOT)
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    forms = {"en": ("sectorised", "sectorisedd"), "es": ("Snapshots", "Snapshotss"), "ca": ("Snapshots", "Snapshotss")}
    for locale, (word, typo) in forms.items():
        assert not dictionaries[locale].lookup(word)
        assert is_project_spelling(locale, word)
        assert not is_project_spelling(locale, typo)
        assert not is_project_spelling(locale, word.upper())
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"technical"},
        {locale: {"technical": f"{word} {typo} misspeling"} for locale, (word, typo) in forms.items()},
        REPO_ROOT,
    )
    assert {cell: set(words) for cell, words in spelling.items()} == {
        (locale, "technical"): {typo, "misspeling"} for locale, (_word, typo) in forms.items()
    }
    assert not is_project_spelling("hu", "Snapshots")
    assert not is_project_spelling("es", "sectorised")


def test_json_lines_format_uses_english_without_exempting_ordinary_lines_or_typos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Dictionary:
        def __init__(self, accepted: set[str]) -> None:
            self.accepted = accepted

        def lookup(self, word: str) -> bool:
            return word in self.accepted

    dictionaries = {locale: Dictionary(set()) for locale in ("en", "es", "ca", "hu")}
    dictionaries["en"].accepted.add("Lines")
    dictionaries["hu"].accepted.add("fájl")
    monkeypatch.setattr("dev.locales.signal_spelling.load_dictionaries", lambda repository: dictionaries)
    spelling, _inventory, _findings = spellcheck_catalogues(
        {"format", "typo", "ordinary"},
        {
            locale: {
                "format": "JSON Lines-fájl misspeling" if locale == "hu" else "JSON Lines misspeling",
                "typo": "JSON Liness",
                "ordinary": "Lines",
            }
            for locale in ("es", "ca", "hu")
        },
        REPO_ROOT,
    )
    for locale in ("es", "ca", "hu"):
        assert spelling[(locale, "format")] == ("misspeling",)
        assert spelling[(locale, "typo")] == ("Liness",)
        assert spelling[(locale, "ordinary")] == ("Lines",)
    dictionaries["en"].accepted.clear()
    spelling, _inventory, _findings = spellcheck_catalogues({"format"}, {"es": {"format": "JSON Lines"}}, REPO_ROOT)
    assert spelling[("es", "format")] == ("Lines",)


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


def test_cli_provider_ids_are_exact_lowercase_and_language_scoped() -> None:
    for locale in ("ca", "es", "hu"):
        for provider in ("claude", "antigravity", "codex"):
            assert is_project_spelling(locale, provider)
        for near_miss in (
            "claudee",
            "antigravty",
            "codx",
            "Antigravity",
            "Codex",
        ):
            assert not is_project_spelling(locale, near_miss)

    # English already accepts these through its dictionary or enrollment;
    # codex itself needs no English project-spelling exception.
    for provider in ("claude", "antigravity"):
        assert is_project_spelling("en", provider)
    assert not is_project_spelling("en", "claudee")
    assert not is_project_spelling("en", "antigravty")
    assert not is_project_spelling("en", "codx")


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
    # The impatriate regime names are attested in those locales too.
    for locale in ("ca", "es"):
        assert all(not is_project_spelling(locale, term) for term in terms if term not in {"Beckham", "impatriado"})


def test_oauth_and_dehu_names_are_exact_and_scoped_to_attested_locales() -> None:
    for locale in ("en", "es", "ca", "hu"):
        assert is_project_spelling(locale, "OAuth")
        assert is_project_spelling(locale, "DEHú")
        assert not is_project_spelling(locale, "OAUTH")
        assert not is_project_spelling(locale, "OAutH")
        assert not is_project_spelling(locale, "DEHu")
        assert not is_project_spelling(locale, "DEHÚ")


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
        "asócialo",
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
        "asocialo",
        "asócialoo",
    ):
        assert not is_project_spelling("es", near_miss)

    for locale in ("ca", "en", "hu"):
        assert all(not is_project_spelling(locale, form) for form in forms)
