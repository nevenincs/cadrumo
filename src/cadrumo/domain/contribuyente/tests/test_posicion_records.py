"""Savings position records: what they accept, what they refuse and how their facts round-trip."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.errors.hierarchy import ProfileAnswerTypeError
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..inmueble_facts import facts_for_row
from ..posicion_facts import POSICION_SECTION, posicion_from_row, posicion_row_values, posiciones_from_facts
from ..posicion_record import PosicionTipo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

YEAR = filing_year_envelope().horizon
PAYER = "B00000000"


def _row() -> dict[str, str]:
    return {
        "tipo": "deposito",
        "pagador_nif": PAYER.lower(),
        "pagador_nombre": "  Banco Sintetico  ",
        "pais_origen": "es",
        "porcentaje_titularidad": "50",
        "fecha_inicio": date(YEAR - 3, 2, 1).isoformat(),
        "identificador": "1234",
    }


def _refused_leaf(row: dict[str, str]) -> str:
    with pytest.raises(ProfileAnswerTypeError) as refused:
        posicion_from_row(0, row)
    return str((refused.value.context or {})["key"])


def test_a_position_reads_into_its_typed_record() -> None:
    record = posicion_from_row(3, _row())

    assert record.clave == 3
    assert record.tipo is PosicionTipo.DEPOSITO
    assert record.pagador_nif == PAYER
    assert record.pagador_nombre == "Banco Sintetico"
    assert record.pais_origen == "ES"
    assert record.porcentaje_titularidad == Decimal(50)
    assert record.fecha_fin is None


def test_the_stored_form_is_canonical_and_round_trips() -> None:
    values = posicion_row_values(posicion_from_row(0, _row()))

    assert values == {
        "tipo": "deposito",
        "pagador_nif": PAYER,
        "pagador_nombre": "Banco Sintetico",
        "pais_origen": "ES",
        "porcentaje_titularidad": "50.00",
        "fecha_inicio": date(YEAR - 3, 2, 1).isoformat(),
        "identificador": "1234",
    }
    assert posicion_row_values(posicion_from_row(0, values)) == values


def test_an_unstated_optional_fact_has_no_stored_leaf() -> None:
    row = _row()
    del row["identificador"]

    assert set(posicion_row_values(posicion_from_row(0, row))) == {
        "tipo",
        "pagador_nif",
        "pagador_nombre",
        "pais_origen",
        "porcentaje_titularidad",
        "fecha_inicio",
    }


@pytest.mark.parametrize(
    "leaf", ["tipo", "pagador_nif", "pagador_nombre", "pais_origen", "porcentaje_titularidad", "fecha_inicio"]
)
def test_each_required_fact_is_required(leaf: str) -> None:
    row = _row()
    del row[leaf]

    assert _refused_leaf(row) == leaf


@pytest.mark.parametrize(
    ("leaf", "value"),
    [
        ("tipo", "fondo_inversion"),
        ("pagador_nif", "B-1"),
        ("pagador_nombre", "   "),
        ("pais_origen", "ESP"),
        ("porcentaje_titularidad", "0"),
        ("porcentaje_titularidad", "100.01"),
        ("porcentaje_titularidad", "33.333"),
        ("porcentaje_titularidad", "medio"),
        ("fecha_inicio", date(YEAR - 3, 2, 1).strftime("%d/%m/%Y")),
        ("identificador", " "),
    ],
)
def test_a_malformed_fact_is_refused_naming_its_leaf(leaf: str, value: str) -> None:
    assert _refused_leaf(_row() | {leaf: value}) == leaf


def test_the_whole_share_and_a_closed_interval_are_accepted() -> None:
    end = date(YEAR - 1, 12, 31)

    record = posicion_from_row(0, _row() | {"porcentaje_titularidad": "100", "fecha_fin": end.isoformat()})

    assert record.porcentaje_titularidad == Decimal(100)
    assert record.fecha_fin == end


def test_a_share_cannot_end_before_it_starts() -> None:
    row = _row() | {"fecha_fin": date(YEAR - 4, 1, 1).isoformat()}

    assert _refused_leaf(row) == "fecha_fin"


def test_positions_read_from_profile_facts_ascending_by_row_key() -> None:
    facts = {
        **facts_for_row(POSICION_SECTION, 4, _row()),
        **facts_for_row(POSICION_SECTION, 1, _row() | {"tipo": "cuenta"}),
        f"{POSICION_SECTION}.7.tipo": None,
    }

    records = posiciones_from_facts(facts)

    assert [record.clave for record in records] == [1, 4]
    assert records[0].tipo is PosicionTipo.CUENTA
