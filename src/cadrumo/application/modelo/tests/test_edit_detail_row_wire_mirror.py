"""Every detail-row wire mirror translates back to a byte-identical domain row.

The mirrors exist so a detail-row edit can cross an operation payload, which
means the only thing that makes them safe is that nothing changes on the way
across. Each of the six is built from a real row, translated back, and compared
field by field against the row it came from.

The registry codes are the part worth guarding. Two of the six row types hydrate
their codes through validator metadata, and the mirrors deliberately carry those
codes unhydrated so the row type's own hydration runs during translation. That
only holds while there is exactly one hydration: the refusal parity below fails
the moment the wire path starts accepting a code the direct construction path
rejects.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import M210PayerMode
from ....domain.modelos import (
    Modelo184MemberRow,
    Modelo210AgrupacionRentaRow,
    Modelo232VinculadaRow,
    Modelo347ContraparteRow,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
)
from ..operation_definitions import (
    ModeloEditApply184MemberRowV1,
    ModeloEditApply210AgrupacionRentaRowV1,
    ModeloEditApply232VinculadaRowV1,
    ModeloEditApply347ContraparteRowV1,
    ModeloEditApply349OperadorRowV1,
    ModeloEditApply349RectificacionRowV1,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m184_pair() -> tuple[ModeloEditApply184MemberRowV1, Modelo184MemberRow]:
    """Build one M184 member row and the wire mirror carrying the same values."""
    mirror = ModeloEditApply184MemberRowV1(
        nif="11111111H",
        nombre="MIEMBRO UNO",
        pais="ES",
        porcentaje="33.33",
        importe="1234.56",
        clave="C",
        codigo_provincia="28",
        miembro_a_31_diciembre=True,
        dias_miembro=365,
        domicilio_fiscal="CALLE MAYOR 1",
        referencia_catastral="1234567AB1234C0001XY",
        porcentaje_titularidad_inmueble="50.00",
        dias_arrendamiento=120,
        reduccion="60.00",
        rendimiento_neto_previo_eo="900.10",
        rendimiento_neto_minorado_agricola_eo="800.20",
    )
    row = Modelo184MemberRow(
        nif="11111111H",
        nombre="MIEMBRO UNO",
        pais="ES",
        porcentaje=Decimal("33.33"),
        importe=Decimal("1234.56"),
        clave="C",
        codigo_provincia="28",
        miembro_a_31_diciembre=True,
        dias_miembro=365,
        domicilio_fiscal="CALLE MAYOR 1",
        referencia_catastral="1234567AB1234C0001XY",
        porcentaje_titularidad_inmueble=Decimal("50.00"),
        dias_arrendamiento=120,
        reduccion=Decimal("60.00"),
        rendimiento_neto_previo_eo=Decimal("900.10"),
        rendimiento_neto_minorado_agricola_eo=Decimal("800.20"),
    )
    return mirror, row


def _m232_pair() -> tuple[ModeloEditApply232VinculadaRowV1, Modelo232VinculadaRow]:
    """Build one M232 row whose three codes cross the wire unhydrated."""
    mirror = ModeloEditApply232VinculadaRowV1(
        nif="B12345674",
        nombre="VINCULADA SL",
        pais="ES",
        tipo_vinculacion="A",
        tipo_operacion="01",
        metodo="1A",
        importe="98765.43",
    )
    row = Modelo232VinculadaRow(
        nif="B12345674",
        nombre="VINCULADA SL",
        pais="ES",
        tipo_vinculacion="A",
        tipo_operacion="01",
        metodo="1A",
        importe=Decimal("98765.43"),
    )
    return mirror, row


def _m349_operador_pair() -> tuple[ModeloEditApply349OperadorRowV1, Modelo349OperadorRow]:
    """Build one M349 operador row and its wire mirror."""
    mirror = ModeloEditApply349OperadorRowV1(
        codigo_pais="DE",
        nif_comunitario="123456789",
        razon_social="OPERADOR GMBH",
        clave_operacion="E",
        importe="4500.00",
    )
    row = Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario="123456789",
        razon_social="OPERADOR GMBH",
        clave_operacion="E",
        importe=Decimal("4500.00"),
    )
    return mirror, row


def _m349_rectificacion_pair() -> tuple[ModeloEditApply349RectificacionRowV1, Modelo349RectificacionRow]:
    """Build one M349 rectificación row and its wire mirror."""
    mirror = ModeloEditApply349RectificacionRowV1(
        codigo_pais="FR",
        nif_comunitario="987654321",
        razon_social="RECTIFICADA SARL",
        clave_operacion="A",
        ejercicio="2025",
        periodo="2T",
        base_rectificada="1500.00",
        base_anterior="1200.00",
    )
    row = Modelo349RectificacionRow(
        codigo_pais="FR",
        nif_comunitario="987654321",
        razon_social="RECTIFICADA SARL",
        clave_operacion="A",
        ejercicio="2025",
        periodo="2T",
        base_rectificada=Decimal("1500.00"),
        base_anterior=Decimal("1200.00"),
    )
    return mirror, row


def _m347_pair() -> tuple[ModeloEditApply347ContraparteRowV1, Modelo347ContraparteRow]:
    """Build one M347 contraparte row with all four quarterly amounts set."""
    mirror = ModeloEditApply347ContraparteRowV1(
        nif="A12345674",
        nombre="CONTRAPARTE SA",
        importe_Q1="1000.01",
        importe_Q2="2000.02",
        importe_Q3="3000.03",
        importe_Q4="4000.04",
        clave_operacion="B",
        pais_codigo="PT",
    )
    row = Modelo347ContraparteRow(
        nif="A12345674",
        nombre="CONTRAPARTE SA",
        importe_Q1=Decimal("1000.01"),
        importe_Q2=Decimal("2000.02"),
        importe_Q3=Decimal("3000.03"),
        importe_Q4=Decimal("4000.04"),
        clave_operacion="B",
        pais_codigo="PT",
    )
    return mirror, row


def _m210_pair() -> tuple[ModeloEditApply210AgrupacionRentaRowV1, Modelo210AgrupacionRentaRow]:
    """Build one M210 agrupación row and its wire mirror."""
    mirror = ModeloEditApply210AgrupacionRentaRowV1(
        source_id="alquiler-2025-01",
        tipo_renta_code="01",
        importe="7500.00",
        tipo_gravamen="0.19",
        pagador_mode=M210PayerMode.SINGLE_PAYER,
        pagador_id="11111111H",
        deriva_de_bien_derecho=True,
        bien_derecho_id="inmueble-1",
    )
    row = Modelo210AgrupacionRentaRow(
        source_id="alquiler-2025-01",
        tipo_renta_code="01",
        importe=Decimal("7500.00"),
        tipo_gravamen=Decimal("0.19"),
        pagador_mode=M210PayerMode.SINGLE_PAYER,
        pagador_id="11111111H",
        deriva_de_bien_derecho=True,
        bien_derecho_id="inmueble-1",
    )
    return mirror, row


_PAIRS = {
    "m184_miembro": _m184_pair,
    "m232_vinculada": _m232_pair,
    "m349_operador": _m349_operador_pair,
    "m349_rectificacion": _m349_rectificacion_pair,
    "m347_contraparte": _m347_pair,
    "m210_agrupacion_renta": _m210_pair,
}


@pytest.mark.parametrize("kind", sorted(_PAIRS), ids=sorted(_PAIRS))
def test_each_detail_row_mirror_translates_to_an_identical_domain_row(kind: str) -> None:
    """Translation reproduces the domain row exactly, field for field."""
    mirror, expected = _PAIRS[kind]()

    translated = mirror.to_row()

    assert translated == expected
    assert translated.model_dump() == expected.model_dump()
    assert type(translated) is type(expected)


@pytest.mark.parametrize("kind", sorted(_PAIRS), ids=sorted(_PAIRS))
def test_every_domain_row_field_is_carried_by_its_mirror(kind: str) -> None:
    """No field is silently dropped: the mirror covers the row's whole shape."""
    mirror, expected = _PAIRS[kind]()

    missing = set(type(expected).model_fields) - set(type(mirror).model_fields)

    assert missing == set(), f"{kind} mirror omits domain row field(s): {sorted(missing)}"


def test_a_decimal_amount_crosses_the_wire_without_being_renormalised() -> None:
    """The exact characters submitted reach the domain row's Decimal unchanged.

    A trailing zero is significant to ``Decimal``: ``Decimal("10.50")`` and
    ``Decimal("10.5")`` compare equal but are distinguishable, so this is the
    assertion that catches a mirror that reformats an amount in passing.
    """
    mirror = ModeloEditApply349OperadorRowV1(
        codigo_pais="IT",
        nif_comunitario="55555555",
        razon_social="ESATTO SRL",
        clave_operacion="E",
        importe="10.50",
    )

    translated = mirror.to_row()

    assert str(translated.importe) == "10.50"
    assert translated.importe.as_tuple() == Decimal("10.50").as_tuple()


def test_the_wire_and_direct_paths_refuse_the_same_malformed_registry_code() -> None:
    """One malformed M232 code is refused identically however it is supplied.

    The wire mirror accepts the raw characters, so the refusal must come from
    the row type's own hydration during translation - the same hydration the
    CLI path runs. If the wire ever grew its own copy, this is where the two
    would start disagreeing.
    """
    malformed = "not-a-declared-code"

    with pytest.raises(ValidationError) as direct:
        Modelo232VinculadaRow(
            nif="B12345674",
            nombre="VINCULADA SL",
            pais="ES",
            tipo_vinculacion=malformed,
            tipo_operacion="01",
            metodo="1A",
            importe=Decimal("1.00"),
        )

    mirror = ModeloEditApply232VinculadaRowV1(
        nif="B12345674",
        nombre="VINCULADA SL",
        pais="ES",
        tipo_vinculacion=malformed,
        tipo_operacion="01",
        metodo="1A",
        importe="1.00",
    )
    with pytest.raises(ValidationError) as through_wire:
        mirror.to_row()

    direct_errors = [(error["loc"], error["type"]) for error in direct.value.errors()]
    wire_errors = [(error["loc"], error["type"]) for error in through_wire.value.errors()]
    assert wire_errors == direct_errors
