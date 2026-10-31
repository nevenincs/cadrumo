"""Language ownership and structural notation in spelling input."""

from __future__ import annotations

import pytest

from ..signal_document_prose import visible_document_prose
from ..signal_spelling_segments import locale_spelling_words, spanish_word_context, translation_spelling_segments
from ..signal_tokens import filtered_translation_text, translation_words

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def words_by_language(value: str, locale: str = "en") -> dict[str, set[str]]:
    """Collect each dictionary's prose without masking duplicate segments."""
    words: dict[str, set[str]] = {}
    for language, segment, _excluded in translation_spelling_segments(value, "guide", locale):
        words.setdefault(language, set()).update(segment)
    return words


def test_rst_prose_omits_parser_diagnostics_but_keeps_authored_text(tmp_path) -> None:
    page = tmp_path / "index.rst"
    page.write_text(
        "Reference\n=========\n\n.. toctree::\n\n   child\n\n"
        "Unknown directive type toctree is a sentence with misspeling.\n",
        encoding="utf-8",
    )
    prose = {text for _line, text in visible_document_prose(page)}
    assert 'Unknown directive type "toctree".' not in prose
    assert "Unknown directive type toctree is a sentence with misspeling." in prose


def test_rst_escapes_restore_complete_identifiers_and_keep_surrounding_prose(tmp_path) -> None:
    page = tmp_path / "legal.rst"
    page.write_text(
        "The resident\\_irpf and fecha\\_notificacion values are checked.\n\n"
        "This ordinary misspeling is still visible.\n",
        encoding="utf-8",
    )
    prose = {text for _line, text in visible_document_prose(page)}
    identifier_line = next(text for text in prose if "resident" in text)
    assert "resident_irpf" in identifier_line and "fecha_notificacion" in identifier_line
    assert "\0" not in identifier_line
    assert "resident_irpf" not in filtered_translation_text(identifier_line)[0]
    assert "fecha_notificacion" not in filtered_translation_text(identifier_line)[0]
    assert "This ordinary misspeling is still visible." in prose


@pytest.mark.parametrize(
    "name,component",
    [
        ("Model Context Protocol", "Protocol"),
        ("Portable Document Format", "Portable"),
        ("Open Financial Exchange", "Financial"),
        ("Advanced Encryption Standard", "Encryption"),
        ("Tom's Obvious Minimal Language", "Minimal"),
        ("hash-based message authentication code", "authentication"),
        ("Google Cloud", "Cloud"),
        ("Google Sheet", "Sheet"),
        ("Google Sheets", "Sheets"),
        ("Apple silicon", "silicon"),
        ("Apple Developer ID", "Developer"),
        ("Apache License", "License"),
    ],
)
@pytest.mark.parametrize("locale", ["ca", "es", "hu"])
def test_complete_standard_names_keep_dictionary_ownership_and_adjacent_typos(
    name: str, component: str, locale: str
) -> None:
    result = words_by_language(name + " misspellledd", locale)
    assert component in result["en"]
    assert "misspellledd" in result[locale]
    assert "en" not in words_by_language(name + "x misspellledd", locale)
    assert "en" not in words_by_language("`" + name + "` misspellledd", locale)
    assert "en" not in words_by_language('<span lang="es">' + name + "</span>", "hu")


@pytest.mark.parametrize("locale", ["ca", "es", "hu"])
def test_standard_name_mutations_and_unpaired_product_words_stay_local(locale: str) -> None:
    for value in (
        "hash-based message authentlcation code",
        "Google Cloudd",
        "Apple siliccon",
        "Apache Licensse",
        "Cloud",
    ):
        assert "en" not in words_by_language(value, locale)


@pytest.mark.parametrize("locale", ["ca", "en", "hu"])
@pytest.mark.parametrize(
    "name,part",
    [
        ("Dirección Electrónica Habilitada Única", "Dirección"),
        ("Dirección Electrónica Habilitada única", "Dirección"),
        ("Fábrica Nacional de Moneda y Timbre", "Fábrica"),
        ("Impuesto sobre la Renta de las Personas Físicas", "Físicas"),
        ("Impuesto sobre el Valor Añadido", "Añadido"),
        ("Número de Identificación Fiscal", "Identificación"),
        ("Número de Identidad de Extranjero", "Extranjero"),
        ("Régimen Especial de Trabajadores del Mar", "Trabajadores"),
        ("pagos fraccionados anteriores", "fraccionados"),
        ("pago fraccionado", "fraccionado"),
        ("Diseño de registro", "Diseño"),
        ("diseño de registros", "diseño"),
        ("**Mis notificaciones**", "notificaciones"),
    ],
)
def test_official_spanish_names_are_checked_as_complete_phrases(locale: str, name: str, part: str) -> None:
    result = words_by_language(name + " misspellledd", locale)
    assert part in result["es"]
    assert "misspellledd" in result[locale]
    assert part + "x" in words_by_language(name.replace(part, part + "x"), locale)[locale]
    assert "es" not in words_by_language('<span lang="ca">' + name + "</span>", "hu")


def test_plain_notifications_are_not_assumed_to_be_the_official_label() -> None:
    assert "es" not in words_by_language("Mis notificaciones errror", "ca")


def test_catalan_elision_keeps_complete_spanish_tax_name_checked_in_spanish() -> None:
    result = words_by_language("de l'Impuesto sobre la Renta de las Personas Físicas errror", "ca")
    assert {"Impuesto", "Personas", "Físicas"} <= result["es"]
    assert "errror" in result["ca"]
    mutated = words_by_language("de l'Impuesto sobre la Renta de las Personas Físicasx errror", "ca")
    assert "Físicasx" in mutated["ca"]
    embedded = words_by_language("devil'Impuesto sobre la Renta de las Personas Físicas", "ca")
    assert "Personas" in embedded["ca"]


@pytest.mark.parametrize(
    "inflected,stem,owner",
    [
        ("GitHubon", "GitHub", "hu"),
        ("PowerShellben", "PowerShell", "hu"),
        ("Model Context Protocolt", "Protocol", "en"),
    ],
)
def test_hungarian_software_name_endings_preserve_exact_stems_and_language(
    inflected: str, stem: str, owner: str
) -> None:
    result = words_by_language(inflected + " misspellledd", "hu")
    assert stem in result[owner]
    assert "misspellledd" in result["hu"]
    assert inflected.split()[-1] in words_by_language(inflected, "es")["es"]
    for bad in (inflected + "x", "x" + inflected, inflected.replace("o", "q", 1)):
        assert bad.split()[-1] in words_by_language(bad, "hu")["hu"]


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


@pytest.mark.parametrize("locale", ["en", "es", "ca", "hu"])
def test_numbered_form_label_follows_its_actual_language(locale: str) -> None:
    result = words_by_language("Form 036 Modelo 100 misspellledd", locale)
    assert "Form" in result["en"]
    assert "Modelo" in result["es"]
    assert "misspellledd" in result[locale]


def test_numbered_form_label_respects_explicit_language_and_does_not_hide_typos() -> None:
    explicit = words_by_language('<span lang="es">Form 036 errro</span> misspellledd', "en")
    assert explicit == {"en": {"misspellledd"}, "es": {"Form", "errro"}}
    typo = words_by_language("Fomr 036 misspellledd", "en")
    assert typo == {"en": {"Fomr", "misspellledd"}}


def test_context_assignment_requires_the_same_interpolation_name() -> None:
    words, _ = filtered_translation_text("year={year}, period={period}; peroid={period} misspellledd")
    assert "year" not in words
    assert "period" not in words
    assert "peroid" in words
    assert "misspellledd" in words


def test_ledger_period_filter_requires_the_real_key_and_valid_period() -> None:
    words, _ = filtered_translation_text("period=1T; peroid=1T; period=9T; misspellledd")
    tokens = translation_words(words)
    assert tokens.count("period") == 1
    assert "peroid" in tokens
    assert "misspellledd" in tokens


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


def test_hungarian_clave_mobile_suffix_keeps_the_exact_service_name_and_near_misses() -> None:
    exact = words_by_language("Cl@ve Móvilhoz hibásszó", "hu")
    assert "Móvilhoz" not in exact["hu"]
    assert "hibásszó" in exact["hu"]
    assert "ve" in exact["es"]
    assert "Móvillhoz" in words_by_language("Cl@ve Móvillhoz hibásszó", "hu")["hu"]
    assert "Móvilhoz" in words_by_language("Cl@vee Móvilhoz hibásszó", "hu")["hu"]
    assert "Móvilhoz" in words_by_language("Cl@ve Móvilhoz misspeling", "en")["en"]


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


@pytest.mark.parametrize(
    "text",
    [
        "the dotaciones it moves",
        "these dotaciones again",
        "Overlapping dotaciones, all years",
        "Dotaciones after that day",
        "Dotaciones for this year",
        "Dotaciones in your tax returns",
        "Dotaciones that no longer match the schedule",
    ],
)
def test_plural_asset_register_term_is_checked_as_spanish_in_its_attested_context(text: str) -> None:
    words = words_by_language(f"Read {text} misspeling")
    assert {"Read", "misspeling"} <= words["en"]
    assert {word.casefold() for word in words["es"]} == {"dotaciones"}


@pytest.mark.parametrize(
    "text",
    [
        "the dotacioness",
        "these dotaciónes again",
        "Overlapping dotacines",
        "Dotacioness after that day",
        "Dotacines for this year",
        "Generic dotaciones prose",
    ],
)
def test_plural_register_term_typos_and_unrecognized_context_stay_checked_as_english(text: str) -> None:
    words = words_by_language(f"Read {text} misspeling")
    assert set(words) == {"en"}
    assert any("dotaci" in word.casefold() for word in words["en"])
