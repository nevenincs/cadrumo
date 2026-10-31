"""The tax CLI row parser accepts registered wire rows without local authority."""

import pytest
import typer

from ....application.modelo.edit_apply_row_contracts import Modelo184MemberRowWireV1, Modelo349RectificacionRowWireV1
from .._modelo_cli_support import parse_calculation_wire_row_spec

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_m349_rectification_row_parses_without_local_registry_or_profile_authority() -> None:
    row = parse_calculation_wire_row_spec(
        'rectificacion codigo_pais=DE nif_comunitario=DE123456789 razon_social="EU trader" '
        "clave_operacion=E ejercicio=2025 periodo=4T base_rectificada=25.00 base_anterior=30.00"
    )
    assert isinstance(row, Modelo349RectificacionRowWireV1)
    assert row.codigo_pais == "DE"
    assert row.periodo == "4T"


@pytest.mark.parametrize(
    "spec",
    [
        "afiliado nif=12345678A numero_afiliacion=1 cotizaciones=[]",
        "agrupacion_renta source_id=1 tipo_renta_code=01 importe=1 tipo_gravamen=1 "
        "pagador_mode=sin_pagador deriva_de_bien_derecho=false",
    ],
)
def test_cli_refuses_wire_variants_that_its_ingress_does_not_support(spec: str) -> None:
    with pytest.raises(typer.BadParameter):
        parse_calculation_wire_row_spec(spec)


@pytest.mark.usefixtures("authority_operation")
def test_m184_documented_example_reaches_the_validated_domain_row() -> None:
    row = parse_calculation_wire_row_spec("miembro nif=12345678A porcentaje=40 importe=10000 clave=D")
    assert isinstance(row, Modelo184MemberRowWireV1)
    assert row.to_row().clave == "D"
