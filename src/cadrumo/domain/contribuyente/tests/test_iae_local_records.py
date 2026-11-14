"""IAE premises, surface-class and tax-element records: what they accept, refuse and how their facts round-trip."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.errors.hierarchy import ProfileAnswerTypeError
from ..iae_local_facts import (
    IAE_ELEMENTO_TRIBUTARIO_SECTION,
    IAE_LOCAL_SECTION,
    IAE_LOCAL_SUPERFICIE_SECTION,
    iae_elemento_from_row,
    iae_elemento_row_values,
    iae_elementos_from_facts,
    iae_local_from_row,
    iae_local_row_values,
    iae_locales_from_facts,
    iae_superficie_from_row,
    iae_superficie_row_values,
    iae_superficies_from_facts,
)
from ..iae_local_record import IaeLocalAfectacion, SuperficieRegla14Clase
from ..inmueble_facts import facts_for_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _local_row(**overrides: str) -> dict[str, str]:
    row = {
        "actividad": "0",
        "afectacion": "ejercicio",
        "via_sg": "CL",
        "via_nombre": "Sintetica",
        "numero": "12",
        "postcode": "28001",
        "province_code": "28",
        "municipality_code": "28079",
        "municipality_name": "Ciudad Sintetica",
        "superficie_total": "120",
        "superficie_rectificada": "96",
        "superficie_computable": "90",
    }
    row.update(overrides)
    return row


def _class_row(**overrides: str) -> dict[str, str]:
    row = {"local": "0", "clase": "5.0", "total": "40", "rectificada": "22", "computable": "21"}
    row.update(overrides)
    return row


def test_a_local_keeps_total_rectificada_and_computable_apart() -> None:
    record = iae_local_from_row(3, _local_row())

    assert (record.clave, record.actividad, record.afectacion) == (3, 0, IaeLocalAfectacion.EJERCICIO)
    assert (record.superficie_total, record.superficie_rectificada, record.superficie_computable) == (120, 96, 90)


def test_a_local_round_trips_to_its_canonical_row() -> None:
    row = _local_row()

    assert iae_local_row_values(iae_local_from_row(0, row)) == row


def test_an_unstated_surface_stays_absent_and_a_stated_zero_stays_zero() -> None:
    row = _local_row(superficie_rectificada="0")
    del row["superficie_total"]

    record = iae_local_from_row(0, row)

    assert (record.superficie_total, record.superficie_rectificada) == (None, 0)
    assert "superficie_total" not in iae_local_row_values(record)


def test_a_minimal_local_states_only_its_activity_and_afectacion() -> None:
    record = iae_local_from_row(0, {"actividad": "1", "afectacion": "indirecta"})

    assert iae_local_row_values(record) == {"actividad": "1", "afectacion": "indirecta"}


@pytest.mark.parametrize(
    ("leaf", "value"),
    [
        ("province_code", "8"),
        ("province_code", "-8"),
        ("municipality_code", "2807"),
        ("municipality_code", "28O79"),
        ("postcode", "2800"),
        ("telefono", "91234567"),
        ("via_sg", "C"),
        ("via_nombre", "x" * 26),
        ("municipality_name", "   "),
        ("superficie_total", "-1"),
        ("superficie_total", "100000"),
        ("superficie_rectificada", "12.5"),
        ("numero", "123456"),
        ("afectacion", "directa"),
        ("actividad", "-1"),
    ],
)
def test_a_negative_or_malformed_local_leaf_refuses_and_names_its_leaf(leaf: str, value: str) -> None:
    with pytest.raises(ProfileAnswerTypeError) as refused:
        iae_local_from_row(0, _local_row(**{leaf: value}))

    assert refused.value.context == {"key": leaf}


def test_only_a_local_afecto_indirectamente_states_its_uso_o_destino() -> None:
    indirect = iae_local_from_row(
        0, _local_row(afectacion="indirecta", uso_destino_code="01", uso_destino_description="Almacen")
    )
    assert (indirect.uso_destino_code, indirect.uso_destino_description) == ("01", "Almacen")

    with pytest.raises(ProfileAnswerTypeError) as refused:
        iae_local_from_row(0, _local_row(uso_destino_code="01"))
    assert refused.value.context == {"key": "uso_destino_code"}


def test_a_surface_class_row_keeps_its_three_figures_apart_and_round_trips() -> None:
    row = _class_row()

    record = iae_superficie_from_row(4, row)

    assert (record.clave, record.local, record.clase) == (4, 0, SuperficieRegla14Clase.ALMACEN)
    assert (record.total, record.rectificada, record.computable) == (40, 22, 21)
    assert iae_superficie_row_values(record) == row


def test_an_unstated_class_figure_stays_absent_and_a_stated_zero_stays_zero() -> None:
    row = _class_row(clase="2.0", computable="0")
    del row["total"]
    del row["rectificada"]

    record = iae_superficie_from_row(0, row)

    assert (record.total, record.rectificada, record.computable) == (None, None, 0)
    assert iae_superficie_row_values(record) == {"local": "0", "clase": "2.0", "computable": "0"}


def test_every_regla_14_class_of_the_design_is_admitted() -> None:
    assert [clase.value for clase in SuperficieRegla14Clase] == [
        "0.1",
        "0.2",
        "1.1",
        "1.2",
        "1.3",
        "2.0",
        "3.1",
        "3.2",
        "4.0",
        "5.0",
        "6.0",
    ]
    for clase in SuperficieRegla14Clase:
        assert iae_superficie_from_row(0, _class_row(clase=clase.value)).clase is clase


@pytest.mark.parametrize(
    ("leaf", "value"),
    [
        ("clase", "7.0"),
        ("clase", "5"),
        ("total", "-4"),
        ("rectificada", "x"),
        ("computable", "100000"),
        ("computable", "1.5"),
        ("local", "-1"),
    ],
)
def test_a_negative_or_malformed_class_leaf_refuses_and_names_its_leaf(leaf: str, value: str) -> None:
    with pytest.raises(ProfileAnswerTypeError) as refused:
        iae_superficie_from_row(0, _class_row(**{leaf: value}))

    assert refused.value.context == {"key": leaf}


def test_a_class_row_without_its_local_or_class_refuses() -> None:
    for missing in ("local", "clase"):
        row = _class_row()
        del row[missing]
        with pytest.raises(ProfileAnswerTypeError) as refused:
            iae_superficie_from_row(0, row)
        assert refused.value.context == {"key": missing}


def test_a_local_states_each_surface_class_once() -> None:
    facts = {
        **facts_for_row(IAE_LOCAL_SUPERFICIE_SECTION, 0, _class_row()),
        **facts_for_row(IAE_LOCAL_SUPERFICIE_SECTION, 1, _class_row(total="1")),
    }

    with pytest.raises(ProfileAnswerTypeError) as refused:
        iae_superficies_from_facts(facts)

    assert refused.value.context == {"key": "clase"}
    other_local = {**facts, **facts_for_row(IAE_LOCAL_SUPERFICIE_SECTION, 1, _class_row(local="1"))}
    assert [(record.local, record.clase.value) for record in iae_superficies_from_facts(other_local)] == [
        (0, "5.0"),
        (1, "5.0"),
    ]


def test_locales_are_read_from_profile_facts_by_their_never_reused_row_position() -> None:
    facts = {
        **facts_for_row(IAE_LOCAL_SECTION, 0, _local_row()),
        **facts_for_row(IAE_LOCAL_SECTION, 2, {"actividad": "1", "afectacion": "indirecta"}),
        f"{IAE_LOCAL_SECTION}.1.actividad": None,
        "contact.postcode": "28001",
    }

    records = iae_locales_from_facts(facts)

    assert [record.clave for record in records] == [0, 2]
    assert [record.actividad for record in records] == [0, 1]


def test_a_tax_element_line_round_trips_with_its_two_decimal_units() -> None:
    row = {"actividad": "0", "linea": "2", "code": "01", "description": "Obreros", "numero": "3.50"}

    record = iae_elemento_from_row(5, row)

    assert (record.clave, record.linea, record.code, record.numero) == (5, 2, "01", Decimal("3.50"))
    assert iae_elemento_row_values(record) == row


@pytest.mark.parametrize(
    ("leaf", "value"),
    [("linea", "5"), ("linea", "0"), ("numero", "-1"), ("numero", "1.234"), ("numero", "10000000"), ("code", "1")],
)
def test_a_tax_element_refuses_a_line_outside_the_design_or_malformed_units(leaf: str, value: str) -> None:
    row = {"actividad": "0", "linea": "1", "code": "01", "numero": "1"}

    with pytest.raises(ProfileAnswerTypeError) as refused:
        iae_elemento_from_row(0, {**row, leaf: value})

    assert refused.value.context == {"key": leaf}


def test_an_activity_states_each_tax_element_line_once() -> None:
    line = {"actividad": "0", "linea": "1", "code": "01", "numero": "1"}
    facts = {
        **facts_for_row(IAE_ELEMENTO_TRIBUTARIO_SECTION, 0, line),
        **facts_for_row(IAE_ELEMENTO_TRIBUTARIO_SECTION, 1, {**line, "code": "02"}),
    }

    with pytest.raises(ProfileAnswerTypeError) as refused:
        iae_elementos_from_facts(facts)

    assert refused.value.context == {"key": "linea"}
    other_activity = {**facts, **facts_for_row(IAE_ELEMENTO_TRIBUTARIO_SECTION, 1, {**line, "actividad": "1"})}
    assert [record.actividad for record in iae_elementos_from_facts(other_activity)] == [0, 1]
