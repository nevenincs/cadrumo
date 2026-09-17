from decimal import Decimal

import pytest

from ...calculations.registry.errors import RegistryValidationError
from ..m232_row_materialisation import m232_related_party_row_casilla_values
from ..row_models import Modelo232VinculadaRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


def _row(nif: str, importe: str) -> Modelo232VinculadaRow:
    return Modelo232VinculadaRow(
        pais="ES",
        nif=nif,
        tipo_vinculacion="A",
        tipo_operacion="01",
        importe=Decimal(importe),
    )


def test_no_rows_materialise_nothing() -> None:
    assert m232_related_party_row_casilla_values(()) == {}


def test_rows_fill_the_declared_slots_in_order() -> None:
    values = m232_related_party_row_casilla_values((_row("12345678Z", "100.50"), _row("87654321X", "7")))

    assert values["vinculada-1-nif"] == "12345678Z"
    assert values["vinculada-1-tipo-vinculacion"] == "A"
    assert values["vinculada-1-tipo-operacion"] == "01"
    assert values["vinculada-1-importe"] == Decimal("100.50")
    assert values["vinculada-2-nif"] == "87654321X"
    assert values["vinculada-2-importe"] == Decimal("7")
    assert not any(casilla_id.startswith("vinculada-3-") for casilla_id in values)


def test_rows_beyond_the_declared_capacity_are_refused() -> None:
    rows = tuple(_row("12345678Z", str(index)) for index in range(6))

    with pytest.raises(RegistryValidationError, match="at most 5 related-party rows"):
        m232_related_party_row_casilla_values(rows)
