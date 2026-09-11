from decimal import Decimal

import pytest

from ...calculations.registry.errors import RegistryValidationError
from ..m232_row_materialisation import m232_related_party_row_casilla_values
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

    assert m232_related_party_row_casilla_values(()) == {}
    with pytest.raises(RegistryValidationError, match="selected registry detail/binding declarations"):
        m232_related_party_row_casilla_values((sample_row,))
