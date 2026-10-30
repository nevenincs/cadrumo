"""Language ownership and structural notation in spelling input."""

from __future__ import annotations

import pytest

from ..signal_spelling_segments import locale_spelling_words, spanish_word_context, translation_spelling_segments
from ..signal_tokens import filtered_translation_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def words_by_language(value: str, locale: str = "en") -> dict[str, set[str]]:
    """Collect each dictionary's prose without masking duplicate segments."""
    words: dict[str, set[str]] = {}
    for language, segment, _excluded in translation_spelling_segments(value, "guide", locale):
        words.setdefault(language, set()).update(segment)
    return words


@pytest.mark.parametrize("target", ["https://www.boe.es/example", "https://sede.agenciatributaria.gob.es/example"])
@pytest.mark.parametrize("markup", ["[{label}]({target})", "`{label} <{target}>`_"])
def test_authority_destination_preserves_english_label(target: str, markup: str) -> None:
    value = "See " + markup.format(label="Official guidance with misspeling", target=target)
    assert words_by_language(value) == {"en": {"See", "Official", "guidance", "with", "misspeling"}}


@pytest.mark.parametrize("markup", ["[{label}]({target})", "`{label} <{target}>`_"])
def test_spanish_official_label_routes_its_typos_to_spanish(markup: str) -> None:
    value = "Read " + markup.format(label="Ley 37/1992 de diciembree", target="https://www.boe.es/example")
    assert words_by_language(value) == {"en": {"Read"}, "es": {"Ley", "de", "diciembree"}}


def test_explicit_language_inside_link_controls_only_annotated_words() -> None:
    value = '[Read <span lang="es">texto errro</span> here](https://www.boe.es/example)'
    assert words_by_language(value) == {"en": {"Read", "here"}, "es": {"texto", "errro"}}


def test_english_legal_title_stays_english() -> None:
    assert words_by_language("Royal Decree 1/2026 guidance") == {"en": {"Royal", "Decree", "guidance"}}


def test_html_source_filename_with_anchor_is_structural_but_standalone_html_is_checked() -> None:
    words, excluded = filtered_translation_text("Grounded in ley-37-1992.html#a105; html prose remains visible")

    assert "ley-37-1992.html#a105" not in words
    assert "html" in words
    assert "prose" in words
    assert excluded == 1


@pytest.mark.parametrize(
    "identifier",
    [
        "AeatAuthenticator",
        "BindingId",
        "CasillaId",
        "CasillaObservation",
        "CounterpartObservation",
        "DiagnosticCheck",
        "ForeignAssetObservation",
        "InputClassification",
        "InvoiceWithholdingEvidenceRequest",
        "LedgerPaymentWithholdingEvidenceRequest",
        "LongPathsEnabled",
        "RelationId",
        "SetupAnswers",
    ],
)
def test_pascal_case_code_identifiers_are_structural_without_hiding_ordinary_prose(identifier: str) -> None:
    words, excluded = filtered_translation_text(f"Set {identifier}; a misconfigured setting may still fail")

    assert identifier not in words
    assert "misconfigured" in words
    assert excluded == 1


def test_pascal_case_domain_names_remain_dictionary_input() -> None:
    words, excluded = filtered_translation_text("GitHub and PowerShell")

    assert words == "GitHub and PowerShell"
    assert excluded == 0


def test_misspelled_pascal_case_identifier_remains_dictionary_input() -> None:
    words, excluded = filtered_translation_text("AccesRequest")

    assert words == "AccesRequest"
    assert excluded == 0


@pytest.mark.parametrize("notation", ["ÉÉÉÉ-HH-NN", "ÉÉÉÉ-HH-NNTÓÓ:PP:MMZ"])
def test_hungarian_date_notation_excludes_structure_and_preserves_prose(notation: str) -> None:
    segments = translation_spelling_segments(f"Dátum ({notation}) hibásszó", "date", "hu")
    assert segments == (("hu", ("Dátum", "hibásszó"), 1),)


def test_hungarian_acronym_suffix_keeps_the_acronym_inside_existing_identifier_rules() -> None:
    segments = translation_spelling_segments("Az AEAT-nál hibásszó", "filing", "hu")
    assert segments == (("hu", ("Az", "hibásszó"), 2),)


@pytest.mark.parametrize(
    ("token", "stem", "suffix"),
    [
        ("Sede-ről", "Sede", "ről"),
        ("Censal-tól", "Censal", "tól"),
        ("036-os", "036", "os"),
        ("110-es", "110", "es"),
        ("115-ös", "115", "ös"),
        ("2022-től", "2022", "től"),
        ("2025-ös", "2025", "ös"),
    ],
)
def test_hungarian_hyphenated_suffix_preserves_stem_and_excludes_only_suffix(
    token: str, stem: str, suffix: str
) -> None:
    words, excluded = locale_spelling_words(f"{token} hibásszó", "hu")
    if stem.isalpha():
        assert stem in words
    assert suffix not in words
    assert "hibásszó" in words
    assert excluded >= 1


def test_hungarian_hyphenated_suffix_does_not_hide_a_misspelled_alphabetic_stem() -> None:
    words = words_by_language("Censel-ről hibásszó", "hu")["hu"]
    assert {"Censel", "hibásszó"} <= words


@pytest.mark.parametrize("token", ["40 %-os", "100%-ot", "50%-ban", "33%-ig", "33%-tól"])
def test_hungarian_percentage_suffix_is_structural_but_surrounding_prose_is_checked(token: str) -> None:
    words, excluded = locale_spelling_words(f"{token} hibásszó", "hu")
    assert "hibásszó" in words
    assert not {"os", "ot", "ban", "ig", "tól"}.intersection(words)
    assert excluded >= 1


@pytest.mark.parametrize("token", ["40%-oss", "100%-ott", "50%-bann", "33%-igg", "33%-tóll"])
def test_malformed_hungarian_percentage_suffix_remains_spelling_input(token: str) -> None:
    words = words_by_language(f"{token} hibásszó", "hu")["hu"]
    assert "hibásszó" in words
    assert token.rsplit("-", 1)[1] in words


def test_malformed_date_and_suffix_are_not_suppressed() -> None:
    words = words_by_language("ÉÉÉÉ-HH-NNx AEAT-náll hibásszó", "hu")["hu"]
    assert {"ÉÉÉÉ", "náll", "hibásszó"} <= words


@pytest.mark.parametrize(
    "token",
    ["Sede-rőlx", "Sede-röle", "Sede-röl", "036-öös", "2025-tőll"],
)
def test_unattested_or_malformed_hungarian_suffix_tokens_remain_spelling_input(token: str) -> None:
    words = words_by_language(f"{token} hibásszó", "hu")["hu"]
    assert "hibásszó" in words
    assert any(part in words for part in token.replace("-", " ").split())


def test_hungarian_notation_rules_do_not_apply_to_other_languages() -> None:
    assert "nál" in words_by_language("AEAT-nál")["en"]
    words = words_by_language("AEAT-tól AEAT-től 2025-ös", "en")["en"]
    assert {"tól", "től", "ös"} <= words


def test_spanish_title_does_not_reassign_surrounding_english_typo() -> None:
    class Dictionary:
        def lookup(self, word: str) -> bool:
            return word == "Ley"

    assert not spanish_word_context(
        "Read Ley 37/1992 misspeling",
        "parallel:docs/_generated/legal/guide.rst:line[5]",
        "misspeling",
        owner_locale="en",
        dictionary=Dictionary(),
        spanish_dictionary=Dictionary(),
    )


@pytest.mark.parametrize("locale", ["en", "ca", "hu"])
def test_exact_spanish_tax_terms_own_their_words_only(locale: str) -> None:
    assert words_by_language("Read bienes de inversión and casillas misspeling", locale) == {
        locale: {"Read", "and", "misspeling"},
        "es": {"bienes", "de", "inversión", "casillas"},
    }


def test_tax_term_prepositions_and_near_misses_stay_in_the_surrounding_language() -> None:
    assert words_by_language("de bienes de inversióm casillass misspeling") == {
        "en": {"de", "bienes", "inversióm", "casillass", "misspeling"},
    }


def test_hyphen_connected_spanish_tax_phrase_is_not_reassigned() -> None:
    assert words_by_language("pre-situación catastral") == {
        "en": {"pre", "situación", "catastral"},
    }


@pytest.mark.parametrize(
    "term",
    [
        "domiciliación bancaria",
        "cuenta corriente tributaria",
        "autoliquidación conjunta",
        "referencia catastral",
        "situación catastral",
        "Diseño de Registros",
        "consulta de declaraciones presentadas",
        "Fichero BOE",
        "CSV cotejo",
    ],
)
def test_exact_aeat_terms_in_english_ui_copy_are_checked_as_spanish(term: str) -> None:
    expected_spanish = set(term.split()) - {"BOE", "CSV"}
    assert words_by_language(f"Select {term} below") == {
        "en": {"Select", "below"},
        "es": expected_spanish,
    }


@pytest.mark.parametrize(
    ("phrase", "spanish"),
    [
        ("rendimiento neto del trabajo", {"rendimiento", "neto", "del", "trabajo"}),
        ("rendimientos del capital mobiliario del ahorro", {"rendimientos", "del", "capital", "mobiliario", "ahorro"}),
        (
            "certificado de retenciones e ingresos a cuenta",
            {"certificado", "de", "retenciones", "e", "ingresos", "a", "cuenta"},
        ),
        ("mínimo por descendientes", {"mínimo", "por", "descendientes"}),
        ("anualidades por alimentos", {"anualidades", "por", "alimentos"}),
        ("régimen de atribución de rentas", {"régimen", "de", "atribución", "rentas"}),
        ("entrega intracomunitaria", {"entrega", "intracomunitaria"}),
        ("signos, índices, módulos", {"signos", "índices", "módulos"}),
        ("estimación directa", {"estimación", "directa"}),
        ("reales decretos", {"reales", "decretos"}),
        ("órdenes ministeriales", {"órdenes", "ministeriales"}),
        ("Concierto Económico", {"Concierto", "Económico"}),
    ],
)
def test_preserved_spanish_tax_phrases_route_only_the_phrase(phrase: str, spanish: set[str]) -> None:
    assert words_by_language(f"Read {phrase} below misspeling") == {
        "en": {"Read", "below", "misspeling"},
        "es": spanish,
    }


@pytest.mark.parametrize(
    ("text", "spanish"),
    [
        ("previous Modelo 303 compensación", {"Modelo", "compensación"}),
        ("withholding (retención)", {"retención"}),
        ("The AEAT sede", {"sede"}),
        ("Record baja", {"baja"}),
        ("from a baja in the register", {"baja"}),
        ("from censal certificate", {"censal"}),
        ("the dotación", {"dotación"}),
        ("per contribuyente", {"contribuyente"}),
        ("baja date", {"baja"}),
        ("dotación recorded", {"dotación"}),
    ],
)
def test_tax_terms_in_mixed_language_context_route_only_the_spanish_word(text: str, spanish: set[str]) -> None:
    segments = words_by_language(f"Read {text} misspeling")
    assert segments["es"] == spanish
    assert "misspeling" in segments["en"]
    if text == "from censal certificate":
        assert {"from", "certificate"} <= segments["en"]


@pytest.mark.parametrize(
    "text",
    [
        "rendimientos del capital mobilario",
        "mínimo por descendientees",
        "previous Modelo 303 compensacion",
        "withholding (retencion)",
        "The AEAT sedee",
        "Record bajaa",
        "the dotacion",
        "dotaciónx recorded",
        "estimacion directa",
        "per contribuyentee",
        "from a bajaa in the register",
    ],
)
def test_misspelled_or_unaccented_tax_terms_stay_in_english(text: str) -> None:
    segments = words_by_language(f"Read {text} misspeling")
    assert "misspeling" in segments["en"]
    assert not any(word.casefold() in segments.get("es", set()) for word in text.split())
    unaccented = {
        "compensacion",
        "retencion",
        "sedee",
        "bajaa",
        "dotacion",
        "dotaciónx",
        "mobilario",
        "descendientees",
        "estimacion",
        "contribuyentee",
    }
    assert unaccented.intersection(segments["en"])


@pytest.mark.parametrize(
    "term",
    [
        "domiciliación bancariaa",
        "cuenta corriente tributariaa",
        "autoliquidación conjuntas",
        "referencia catastrala",
        "diseño de registrosx",
        "consulta de declaraciones presentadax",
        "fichero BOEx",
        "csv cotejoo",
        "situación catastrall",
    ],
)
def test_near_miss_aeat_terms_remain_english_spelling_input(term: str) -> None:
    assert words_by_language(f"Select {term} below") == {
        "en": {"Select", *term.split(), "below"},
    }


def test_exact_tax_terms_inside_literals_do_not_add_prose() -> None:
    assert words_by_language("Read `bienes de inversión` misspeling") == {"en": {"Read", "misspeling"}}


@pytest.mark.parametrize("name", ["Cl@ve", "Cl@ve Móvil", "Cl@ve PIN", "Cl@ve Permanente"])
def test_exact_clave_service_names_are_checked_as_spanish(name: str) -> None:
    words = words_by_language(f"Read {name} misspeling")
    assert words["en"] == {"Read", "misspeling"}
    assert "ve" in words["es"]


def test_misspelled_clave_service_names_keep_unknown_fragments() -> None:
    assert "Móvill" in words_by_language("Cl@ve Móvill misspeling")["en"]
    assert "Móvilx" in words_by_language("Cl@ve Móvilx misspeling")["en"]
    assert "Móvil" in words_by_language("Cl@vee Móvil misspeling")["en"]


def test_explicit_language_wins_over_exact_tax_term_recognition() -> None:
    assert words_by_language('<span lang="ca">casillas errror</span> misspeling') == {
        "en": {"misspeling"},
        "ca": {"casillas", "errror"},
    }


def test_hungarian_abbreviation_keeps_dictionary_significant_period() -> None:
    assert words_by_language("pl. hibásszó. pl hibásszó", "hu") == {
        "hu": {"pl.", "hibásszó.", "pl", "hibásszó"},
    }


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_spanish_tax_words_inside_complete_commands_do_not_split_the_path(locale: str) -> None:
    assert words_by_language("aeat app modelo work verify misspeling", locale) == {
        locale: {"misspeling"},
    }


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_misspelled_commands_keep_the_verb_visible_to_spelling(locale: str) -> None:
    words = words_by_language("aeat app modelo work verfy misspeling", locale)
    assert {"verfy", "misspeling"} <= words[locale]


@pytest.mark.parametrize(
    "term",
    [
        "estimación objetiva",
        "estimación objetiva (módulos)",
        "tipo de renta",
        "libertad de amortización",
        "colegio concertado",
        "importe neto de la cifra de negocios",
        "Suministro Inmediato de Información",
        "acuse de recibo",
        "Número de rentas",
        "bien de inversión",
    ],
)
def test_complete_spanish_profile_and_filing_terms_keep_neighboring_prose_checked(term: str) -> None:
    words = words_by_language(f"Read {term} misspeling")
    assert words["en"] == {"Read", "misspeling"}
    assert words["es"]


@pytest.mark.parametrize("label", ["Objective assessment", "Objective estimation"])
def test_modulos_is_spanish_only_in_its_attested_assessment_label(label: str) -> None:
    assert words_by_language(f"{label} (módulos) misspeling") == {
        "en": {*label.split(), "misspeling"},
        "es": {"módulos"},
    }
    assert "módulos" in words_by_language("Generic módulos misspeling")["en"]


@pytest.mark.parametrize(
    ("term", "typo"),
    [
        ("estimacion objetiva", "estimacion"),
        ("estimación objetivaa", "objetivaa"),
        ("tipo de rentaa", "rentaa"),
        ("libertad de amortizacion", "amortizacion"),
        ("colegio concertadoo", "concertadoo"),
        ("importe neto de la cifra de negocioos", "negocioos"),
        ("Suministro Inmediato de Informacion", "Informacion"),
        ("acuse de reciboo", "reciboo"),
        ("Numero de rentas", "Numero"),
        ("bien de inversion", "inversion"),
    ],
)
def test_spanish_profile_and_filing_term_typos_remain_visible(term: str, typo: str) -> None:
    assert typo in words_by_language(f"Read {term} misspeling")["en"]


@pytest.mark.parametrize("quote", ["'", "’", "‘"])
def test_quoted_official_spanish_heading_keeps_surrounding_prose_checked(quote: str) -> None:
    closing = "’" if quote == "‘" else quote
    assert words_by_language(f"Read {quote}Número de rentas{closing} misspeling") == {
        "en": {"Read", "misspeling"},
        "es": {"Número", "de", "rentas"},
    }


def test_quoted_spanish_term_does_not_admit_a_partial_word_or_english_possessive() -> None:
    for text in ("'colegio concertadoo'", "'colegio concertado's", "prefix'colegio concertado'"):
        words = words_by_language(f"Read {text} misspeling")
        assert set(words) == {"en"}
        assert any("colegio" in word for word in words["en"])
        assert any("concertado" in word for word in words["en"])
