from decimal import Decimal

import pytest

from ...calculations.registry.errors import RegistryValidationError
from ..m232_row_materialisation import M232_MAX_RELATED_PARTY_ROWS, m232_related_party_row_casilla_values
from ..row_models import Modelo232VinculadaRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_m232_row_mapping_error_too_many_rows() -> None:
    sample_row = Modelo232VinculadaRow(
        pais="ES",
        nif="12345678A",
        tipo_vinculacion="A",
        tipo_operacion="01",
        importe=Decimal("0"),
    )

    assert M232_MAX_RELATED_PARTY_ROWS == 5
    at_capacity = m232_related_party_row_casilla_values((sample_row,) * M232_MAX_RELATED_PARTY_ROWS)
    assert {casilla_id.split("-")[1] for casilla_id in at_capacity} == {"1", "2", "3", "4", "5"}

    with pytest.raises(RegistryValidationError):
        m232_related_party_row_casilla_values((sample_row,) * (M232_MAX_RELATED_PARTY_ROWS + 1))
