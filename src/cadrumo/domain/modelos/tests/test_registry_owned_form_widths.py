"""The record designs' codes and widths reach these rows from the registry, and still refuse."""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...calculations.registry.authority import bundled_indexed_authority
from ..m156_rows import Modelo156AfiliadoRow, Modelo156MonthlyContribution
from ..row_models import Modelo232VinculadaRow

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _vinculada(**codes: str) -> Modelo232VinculadaRow:
    return Modelo232VinculadaRow(nif="B12345674", pais="ES", importe=Decimal("1"), **codes)


def _afiliado(numero: str) -> Modelo156AfiliadoRow:
    months = tuple(Modelo156MonthlyContribution(month=month, amount=Decimal("1")) for month in range(1, 13))
    return Modelo156AfiliadoRow(nif="12345678Z", numero_afiliacion=numero, cotizaciones=months)


def test_modelo_232_accepts_the_published_codes_and_a_blank() -> None:
    row = _vinculada(tipo_vinculacion="a", tipo_operacion="11", metodo="1e")
    assert (row.tipo_vinculacion, row.tipo_operacion, row.metodo) == ("A", "11", "1E")
    assert _vinculada().tipo_vinculacion == ""


@pytest.mark.parametrize(
    "codes",
    [{"tipo_vinculacion": "Z"}, {"tipo_operacion": "12"}, {"metodo": "CUP"}],
)
def test_modelo_232_refuses_a_code_the_design_does_not_publish(codes: dict[str, str]) -> None:
    with pytest.raises(ValidationError, match="must be blank or one of"):
        _vinculada(**codes)


def test_modelo_156_refuses_a_membership_number_of_another_width() -> None:
    assert _afiliado("0" * 12).numero_afiliacion == "0" * 12
    with pytest.raises(ValidationError):
        _afiliado("0" * 11)


def test_a_client_outside_every_scope_keeps_the_technical_bound_only() -> None:
    row = contextvars.Context().run(_vinculada, tipo_operacion="99")
    assert row.tipo_operacion == "99"
