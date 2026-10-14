"""The tax CLI row parser accepts registered wire rows without local authority."""

import pytest

from ....application.modelo.edit_apply_row_contracts import Modelo349RectificacionRowWireV1
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
