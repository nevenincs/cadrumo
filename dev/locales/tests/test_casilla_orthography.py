"""Diacritic-loss detection over stored casilla values."""

from __future__ import annotations

import pytest

from dev.locales import casilla_orthography
from dev.locales.casilla_orthography import spanish_leftovers, unaccented_words
from dev.locales.modelo_casilla_catalogue import Values

pytestmark = [pytest.mark.hex_domain]

_KEY = "modelo.schema.100.casilla.continuidad.x.label"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("word", "table", "known", "expected"),
    [
        ("regimen", {"e": "é", "i": "í"}, {"régimen"}, ("régimen",)),
        ("anios", {"n": "ñ", "o": "ó"}, {"años"}, ("años",)),
        ("Codigo", {"o": "ó"}, {"Código"}, ("Código",)),
        ("tenyleges", {"e": "é"}, {"tényleges", "tényléges"}, ("tényleges", "tényléges")),
        ("sucesion", {"o": "ó"}, set(), ()),
    ],
)
def test_restorations_return_every_dictionary_form(
    word: str, table: dict[str, str], known: set[str], expected: tuple[str, ...]
) -> None:
    assert casilla_orthography._restorations(word, table, known.__contains__) == expected


@pytest.mark.integration
@pytest.mark.external_tool
def test_unaccented_words_are_reported_and_correct_text_is_not() -> None:
    values: Values = {
        "es": {
            _KEY: "Régimen de estimación objetiva",
            "modelo.schema.100.casilla.continuidad.y.label": "Regimen de estimacion objetiva",
            "modelo.schema.100.casilla.continuidad.z.label": None,
        },
        "ca": {_KEY: "Identificacio del declarant"},
        "hu": {_KEY: "Az adózó személy azonosítása"},
    }

    found = {(item.locale, item.key, item.word): item.candidates for item in unaccented_words(values)}

    assert found == {
        ("es", "modelo.schema.100.casilla.continuidad.y.label", "Regimen"): ("Régimen",),
        ("es", "modelo.schema.100.casilla.continuidad.y.label", "estimacion"): ("estimación",),
        ("ca", _KEY, "Identificacio"): ("Identificació",),
    }


@pytest.mark.integration
@pytest.mark.external_tool
def test_a_reviewed_word_is_not_reported() -> None:
    values: Values = {"es": {_KEY: "Regimen especial"}}

    assert {item.word for item in unaccented_words(values)} == {"Regimen"}
    found = {item.word for item in unaccented_words(values, reviewed={"es": frozenset({"Regimen"})})}

    assert found == set()


@pytest.mark.integration
@pytest.mark.external_tool
def test_quoted_identifiers_and_truncated_words_are_not_prose() -> None:
    values: Values = {"es": {_KEY: "Ver contraparte.pais-codigo y m131-modulos-coeficientes; ejerci... Codigo"}}

    assert {item.word for item in unaccented_words(values)} == {"Codigo"}


@pytest.mark.integration
@pytest.mark.external_tool
def test_untranslated_spanish_words_are_reported_outside_quotations() -> None:
    values: Values = {
        "en": {
            "modelo.schema.100.casilla.continuidad.a.label": "Deduction for obras realizadas in the home",
            "modelo.schema.100.casilla.continuidad.b.label": "Donations to «Fundación para obras sociales»",
            "modelo.schema.100.casilla.continuidad.c.label": "Box contraparte.importe of modelo 347",
            "modelo.schema.100.casilla.continuidad.d.label": "Applied - Deducción por inversión en beneficios",
        },
    }
    sources = {
        "en": {
            "modelo.schema.100.casilla.continuidad.a.label": frozenset(
                {"Deducción por obras realizadas en la vivienda"}
            ),
            "modelo.schema.100.casilla.continuidad.d.label": frozenset(
                {"Aplicado - Deducción por inversión en beneficios"}
            ),
        },
    }

    found = {(item.key, item.words) for item in spanish_leftovers(values, sources)}

    assert found == {("modelo.schema.100.casilla.continuidad.a.label", ("obras", "realizadas"))}


@pytest.mark.integration
@pytest.mark.external_tool
def test_the_shipped_interface_domains_keep_their_diacritics() -> None:
    """Every shipped non-Modelo value spells its language with diacritics.

    Repair with `python -m dev.locales casilla-orthography`, which reports the
    same finding over the interface domains and the casilla catalogue together.
    """
    from dev.locales._paths import LOCALES_DIR, SRC_DIR
    from dev.locales.manager import LocaleManager, _flatten_raw_locale_leaves

    manager = LocaleManager(src_dir=SRC_DIR, locales_dir=LOCALES_DIR)
    values: Values = {}
    for locale in ("es", "en", "ca", "hu"):
        leaves = _flatten_raw_locale_leaves(manager._load_raw_locale(LOCALES_DIR / locale))
        values[locale] = {
            key: value
            for key, value in leaves.items()
            if not key.startswith("modelo.schema.") and isinstance(value, str)
        }
    assert values["es"], "no interface values were read; the gate below would be vacuous"

    found = [
        f"{item.locale} {item.key} {item.word} -> {'/'.join(item.candidates)}" for item in unaccented_words(values)
    ]

    assert not found, found[:5]


@pytest.mark.integration
@pytest.mark.external_tool
def test_no_shipped_casilla_text_is_half_translated() -> None:
    """A translation states its label in its own language, apart from reviewed Spanish terms.

    Repair with `python -m dev.locales casilla-orthography`, which reports the
    same finding; record a term the product keeps in Spanish in
    ``REVIEWED_SPANISH_TERMS`` with its reason instead.
    """
    from dev.locales._paths import LOCALES_DIR
    from dev.locales.modelo_casilla_catalogue import ModeloCasillaCatalogue

    catalogue = ModeloCasillaCatalogue.published(LOCALES_DIR)
    sources = {locale: catalogue.served_sources(locale) for locale in catalogue.locales}
    assert sources["en"], "no English source was read; the gate below would be vacuous"

    found = [
        f"{item.locale} {item.key} {' '.join(item.words)}" for item in spanish_leftovers(catalogue.values, sources)
    ]

    assert not found, found[:5]


@pytest.mark.integration
@pytest.mark.external_tool
def test_the_spanish_word_for_a_box_is_reported_in_a_translation() -> None:
    """Every locale states the box in its own word, so `casilla` is a leftover."""
    values: Values = {"en": {_KEY: "Transfer the amount to casilla [1142] of annex B.7"}}
    sources = {"en": {_KEY: frozenset({"Traslade el importe a la casilla [1142] del anexo B.7"})}}

    assert [item.words for item in spanish_leftovers(values, sources)] == [("casilla",)]


@pytest.mark.integration
@pytest.mark.external_tool
@pytest.mark.parametrize(
    ("english", "reported"),
    [
        ("Reduction for certain insurance contracts (art. 130 LIS)", False),
        ("Deferred tax assets (AID) pending application", False),
        ("Prior net income (estimación directa simplificada)", True),
        ("Other capital gains (intereses indemnizatorios)", True),
    ],
)
def test_spanish_prose_inside_a_parenthesis_is_read_like_the_rest(english: str, reported: bool) -> None:
    """A parenthesis holding a citation or an acronym is skipped; one holding words is not."""
    spanish = (
        "Reducción aplicable a determinados contratos de seguro (art. 130 LIS) "
        "Activos por impuesto diferido (AID) pendientes de aplicación "
        "Rendimiento neto previo (estimación directa simplificada) "
        "Otras ganancias patrimoniales (intereses indemnizatorios)"
    )
    values: Values = {"en": {_KEY: english}}
    sources = {"en": {_KEY: frozenset({spanish})}}

    assert bool(list(spanish_leftovers(values, sources))) is reported
