"""Property and lease records: what they accept, what they refuse and how their facts round-trip."""

from __future__ import annotations

from datetime import date

import pytest

from ....core.errors.hierarchy import ProfileAnswerTypeError
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..arrendamiento_record import ArrendamientoRecord, InquilinoEdad
from ..inmueble_facts import (
    ARRENDAMIENTO_SECTION,
    INMUEBLE_SECTION,
    arrendamiento_from_row,
    arrendamiento_row_values,
    arrendamientos_from_facts,
    facts_for_row,
    inmueble_from_row,
    inmueble_row_values,
    inmuebles_from_facts,
    parse_inquilinos,
    parse_mejoras,
    parse_usos,
    parse_valores_catastrales,
    serialise_valores_catastrales,
)
from ..inmueble_record import (
    ImportesMovimientos,
    InmuebleRecord,
    InmuebleSituacion,
    TitularidadRegimen,
    UsoInmuebleTipo,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

YEAR = filing_year_envelope().horizon
CATASTRAL = "9872023VH5797S0001WX"
DAY = date(YEAR - 5, 1, 1).isoformat()
MIDDLE = date(YEAR - 5, 6, 1).isoformat()
LATER = date(YEAR - 5, 12, 31).isoformat()
TENANT = "X0001500M"


def _property_row() -> dict[str, str]:
    return {
        "situacion": "1",
        "referencia_catastral": CATASTRAL,
        "naturaleza": "urbana",
        "direccion": "Calle Sintetica 1, 2o A, Ciudad",
        "titularidad_regimen": "pleno_dominio",
        "titular": "primer_declarante",
        "porcentaje_propiedad": "50.00",
        "adquisicion_titulo": "onerosa",
        "fecha_adquisicion": date(YEAR - 12, 3, 4).isoformat(),
        "importe_adquisicion": "180000.00",
        "gastos_tributos_adquisicion": "14000.50",
        "valor_suelo": "60000.00",
        "mejoras": f"{date(YEAR - 6, 5, 1).isoformat()}:1500.00",
        "valores_catastrales": f"{YEAR}:90000.00:54000.00;{YEAR - 1}:88000.00:52800.00",
        "usos": f"vivienda_habitual:{date(YEAR - 12, 4, 1).isoformat()}:{date(YEAR - 8, 12, 31).isoformat()}",
        "inmueble_principal": "1",
        "importes_movimientos": "parte_propia",
        "amortizacion_acumulada": "21000.00",
        "amortizacion_acumulada_desde": date(YEAR, 1, 1).isoformat(),
    }


def _lease_row() -> dict[str, str]:
    return {
        "inmueble": "0",
        "fecha_contrato": date(YEAR - 1, 6, 20).isoformat(),
        "fecha_inicio": date(YEAR - 1, 7, 1).isoformat(),
        "uso_vivienda": "true",
        "inquilinos": f"{TENANT}:18_35:no;K1234567:no_aplica:si",
        "zona_tensionada": "true",
        "primer_arrendamiento_vivienda": "false",
        "renta_inicial": "850.00",
        "renta_ultima_contrato_anterior": "900.00",
        "arrendatario_pariente_art24": "false",
        "incumple_lau_17_6": "false",
    }


def test_a_property_round_trips_through_its_stored_facts() -> None:
    record = inmueble_from_row(3, _property_row())

    assert inmueble_row_values(record) == _property_row() | {
        "valores_catastrales": f"{YEAR - 1}:88000.00:52800.00;{YEAR}:90000.00:54000.00",
    }
    assert inmueble_from_row(3, inmueble_row_values(record)) == record
    assert record.titularidad is not None
    assert record.titularidad.regimen is TitularidadRegimen.PLENO_DOMINIO
    assert record.usos[0].tipo is UsoInmuebleTipo.VIVIENDA_HABITUAL
    assert record.inmueble_principal == 1
    assert record.importes_movimientos is ImportesMovimientos.PARTE_PROPIA


def test_a_lease_round_trips_through_its_stored_facts() -> None:
    record = arrendamiento_from_row(1, _lease_row())

    assert arrendamiento_row_values(record) == _lease_row()
    assert arrendamiento_from_row(1, arrendamiento_row_values(record)) == record
    assert [tenant.franja_edad for tenant in record.inquilinos] == [InquilinoEdad.DE_18_A_35, InquilinoEdad.NO_APLICA]
    assert [tenant.extranjero for tenant in record.inquilinos] == [False, True]


def test_rows_are_read_from_profile_facts_by_position_and_a_cleared_row_is_absent() -> None:
    values: dict[str, object] = {}
    values |= facts_for_row(INMUEBLE_SECTION, 0, _property_row())
    values |= facts_for_row(INMUEBLE_SECTION, 2, {"situacion": "5"})
    values |= {f"{INMUEBLE_SECTION}.1.situacion": None, f"{INMUEBLE_SECTION}.1.referencia_catastral": None}
    values |= facts_for_row(ARRENDAMIENTO_SECTION, 4, _lease_row())

    properties = inmuebles_from_facts(values)
    leases = arrendamientos_from_facts(values)

    assert [record.clave for record in properties] == [0, 2]
    assert properties[1].situacion is InmuebleSituacion.EXTRANJERO
    assert [record.clave for record in leases] == [4]


def test_a_minimal_property_states_nothing_it_was_not_told() -> None:
    record = inmueble_from_row(0, {"situacion": "4"})

    assert record.titularidad is None
    assert record.inmueble_principal is None
    assert record.importes_movimientos is None
    assert record.valores_catastrales == ()
    assert inmueble_row_values(record) == {"situacion": "4"}


@pytest.mark.parametrize(
    ("change", "leaf"),
    [
        ({"referencia_catastral": "SHORT"}, "referencia_catastral"),
        ({"situacion": "4"}, "referencia_catastral"),
        ({"porcentaje_propiedad": "50.001"}, "porcentaje_propiedad"),
        ({"porcentaje_propiedad": "100.01"}, "porcentaje_propiedad"),
        ({"porcentaje_usufructo": "10"}, "titularidad_regimen"),
        ({"titularidad_regimen": "usufructo"}, "titularidad_regimen"),
        ({"titular": "hijo"}, "titular"),
        ({"titular_hijo_ordinal": "1"}, "titular"),
        ({"valor_suelo": "180000.01"}, "valor_suelo"),
        ({"fecha_transmision": date(YEAR - 20, 1, 1).isoformat()}, "fecha_transmision"),
        ({"valores_catastrales": f"{YEAR}:100.00:200.00"}, "valores_catastrales"),
        ({"valores_catastrales": f"{YEAR}:100.00:50.00;{YEAR}:200.00:50.00"}, "valores_catastrales"),
        ({"usos": f"casa:{DAY}:"}, "tipo"),
        (
            {
                "usos": f"vivienda_habitual:{DAY}:{LATER};vivienda_habitual:{MIDDLE}:",
            },
            "usos",
        ),
        ({"amortizacion_acumulada_desde": ""}, "amortizacion_acumulada"),
        ({"importe_adquisicion": "1.234"}, "importe_adquisicion"),
        ({"fecha_adquisicion": "4 March"}, "fecha_adquisicion"),
        ({"inmueble_principal": "0"}, "inmueble_principal"),
        ({"inmueble_principal": "first"}, "inmueble_principal"),
        ({"importes_movimientos": ""}, "importes_movimientos"),
        ({"importes_movimientos": "mitad"}, "importes_movimientos"),
    ],
)
def test_a_property_that_does_not_cohere_is_refused_naming_the_leaf(change: dict[str, str], leaf: str) -> None:
    row = {leaf_key: value for leaf_key, value in (_property_row() | change).items() if value != ""}

    with pytest.raises(ProfileAnswerTypeError) as refusal:
        inmueble_from_row(0, row)

    assert (refusal.value.context or {}).get("key") == leaf


def test_a_property_without_a_situation_is_refused() -> None:
    with pytest.raises(ProfileAnswerTypeError):
        inmueble_from_row(0, {"referencia_catastral": CATASTRAL})


def test_the_ledger_scope_is_required_only_below_a_full_share() -> None:
    full = {"situacion": "5", "titularidad_regimen": "pleno_dominio", "titular": "primer_declarante"}

    assert inmueble_from_row(0, full | {"porcentaje_propiedad": "100"}).importes_movimientos is None
    with pytest.raises(ProfileAnswerTypeError) as refusal:
        inmueble_from_row(0, full | {"porcentaje_propiedad": "99.99"})
    assert (refusal.value.context or {}).get("key") == "importes_movimientos"
    shared = inmueble_from_row(0, full | {"porcentaje_propiedad": "50", "importes_movimientos": "inmueble_completo"})
    assert shared.importes_movimientos is ImportesMovimientos.INMUEBLE_COMPLETO


def test_a_titular_needs_its_regime() -> None:
    with pytest.raises(ProfileAnswerTypeError):
        inmueble_from_row(0, {"situacion": "5", "titular": "conyuge"})


def test_combined_holding_states_both_percentages_and_the_pair_cannot_exceed_one_hundred() -> None:
    combined = {
        "situacion": "5",
        "titularidad_regimen": "pleno_dominio_y_usufructo",
        "titular": "hijo",
        "titular_hijo_ordinal": "2",
        "porcentaje_propiedad": "60",
        "porcentaje_usufructo": "40",
        "importes_movimientos": "parte_propia",
    }

    assert inmueble_from_row(0, combined).titularidad is not None
    with pytest.raises(ProfileAnswerTypeError):
        inmueble_from_row(0, combined | {"porcentaje_usufructo": "40.01"})


@pytest.mark.parametrize(
    ("change", "leaf"),
    [
        ({"fecha_fin": date(YEAR - 5, 1, 1).isoformat()}, "fecha_fin"),
        ({"inquilinos": f"{TENANT}:18_35:no;{TENANT}:otra:no"}, "inquilinos"),
        ({"inquilinos": f"{TENANT}:30_40:no"}, "franja_edad"),
        ({"inquilinos": f"{TENANT}:18_35:quiza"}, "inquilinos"),
        ({"inquilinos": f"{TENANT}:18_35"}, "inquilinos"),
        ({"inquilinos": "AB:18_35:no"}, "inquilinos"),
        ({"arrendatario_entidad_finalidad": "otra"}, "arrendatario_entidad_finalidad"),
        ({"uso_vivienda": "yes"}, "uso_vivienda"),
        ({"renta_inicial": "850.123"}, "renta_inicial"),
    ],
)
def test_a_lease_that_does_not_cohere_is_refused_naming_the_leaf(change: dict[str, str], leaf: str) -> None:
    with pytest.raises(ProfileAnswerTypeError) as refusal:
        arrendamiento_from_row(0, _lease_row() | change)

    assert (refusal.value.context or {}).get("key") == leaf


@pytest.mark.parametrize("missing", ["inmueble", "fecha_contrato", "fecha_inicio"])
def test_a_lease_without_its_property_or_dates_is_refused(missing: str) -> None:
    row = {leaf: value for leaf, value in _lease_row().items() if leaf != missing}

    with pytest.raises(ProfileAnswerTypeError) as refusal:
        arrendamiento_from_row(0, row)

    assert (refusal.value.context or {}).get("key") == missing


def test_the_list_grammar_stores_one_canonical_form_whatever_order_was_typed() -> None:
    typed = f"{YEAR}:90000:54000;{YEAR - 1}:88000.5:52800"

    parsed = parse_valores_catastrales(typed, leaf="valores_catastrales")

    assert serialise_valores_catastrales(parsed) == f"{YEAR - 1}:88000.50:52800.00;{YEAR}:90000.00:54000.00"
    assert parse_mejoras(f"{MIDDLE}:10;{DAY}:5.5", leaf="mejoras")[0].fecha == date.fromisoformat(DAY)
    assert parse_usos(f"actividad_economica:{DAY}:", leaf="usos")[0].hasta is None
    assert parse_inquilinos(f"{TENANT.lower()}:otra:no", leaf="inquilinos")[0].nif == TENANT


@pytest.mark.parametrize(
    "raw", ["", f"{YEAR}:1:1;", ";", f"{YEAR}:1", "twenty:1:1", f"{YEAR}:1:1:{YEAR}:1", f"{YEAR}:1:1:twenty"]
)
def test_the_list_grammar_refuses_a_blank_or_malformed_entry_instead_of_dropping_it(raw: str) -> None:
    with pytest.raises(ProfileAnswerTypeError):
        parse_valores_catastrales(raw, leaf="valores_catastrales")


def test_a_cadastral_value_keeps_the_year_its_collective_valuation_entered_into_force() -> None:
    typed = f"{YEAR}:90000:54000:{YEAR - 9};{YEAR - 1}:88000:52800"

    parsed = parse_valores_catastrales(typed, leaf="valores_catastrales")

    assert [valor.vigor for valor in parsed] == [None, YEAR - 9]
    assert serialise_valores_catastrales(parsed) == f"{YEAR - 1}:88000.00:52800.00;{YEAR}:90000.00:54000.00:{YEAR - 9}"


def test_a_collective_valuation_cannot_enter_into_force_after_the_ibi_year_it_sets() -> None:
    with pytest.raises(ProfileAnswerTypeError) as refusal:
        parse_valores_catastrales(f"{YEAR}:90000:54000:{YEAR + 1}", leaf="valores_catastrales")

    assert (refusal.value.context or {}).get("key") == "valores_catastrales"


def test_a_fact_outside_a_row_position_is_refused_and_not_ignored() -> None:
    with pytest.raises(ProfileAnswerTypeError):
        inmuebles_from_facts({f"{INMUEBLE_SECTION}.situacion": "1"})


def test_records_hold_no_annual_total() -> None:
    forbidden = {"ingresos", "gastos", "rendimiento", "total_anual", "importe_anual"}

    for model in (InmuebleRecord, ArrendamientoRecord):
        assert not forbidden & set(model.model_fields)
