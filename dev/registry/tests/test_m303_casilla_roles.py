"""Modelo 303 role readers locate the boxes each published edition prints."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.m303_casilla_roles import (
    m303_importe_rectificacion_casilla,
    m303_resultado_final_casilla,
)
from cadrumo.domain.calculations.registry.schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Box numbers carried from the earlier fixed checks: box 71 states the result in every edition,
# and box 111 first appears in the edition applying from September and 3T of 2024.
_COORDINATES = (
    (2022, "4T", "71", None),
    (2023, "4T", "71", None),
    (2024, "2T", "71", None),
    (2024, "3T", "71", "111"),
    (2025, "4T", "71", "111"),
    (2026, "1T", "71", "111"),
)


def _revision(year: int, period: str) -> ModeloRevision:
    with bundled_indexed_authority().operation() as operation:
        return operation.revision_for_context("303", filing_year=year, period=period)


@pytest.mark.parametrize(("year", "period", "resultado", "rectificacion"), _COORDINATES)
def test_each_edition_declares_the_printed_boxes(
    year: int, period: str, resultado: str, rectificacion: str | None
) -> None:
    revision = _revision(year, period)
    assert m303_resultado_final_casilla(revision) == resultado
    assert m303_importe_rectificacion_casilla(revision) == rectificacion


def test_an_edition_without_the_result_role_is_refused() -> None:
    revision = _revision(2025, "4T")
    stripped = revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update={"semantic_role": None})
                if casilla.semantic_role == "iva_resultado_final"
                else casilla
                for casilla in revision.casillas
            )
        }
    )
    with pytest.raises(RegistryValidationError, match="iva_resultado_final"):
        m303_resultado_final_casilla(stripped)


def test_a_role_declared_on_two_boxes_is_refused() -> None:
    revision = _revision(2025, "4T")
    doubled = revision.model_copy(
        update={
            "casillas": tuple(
                casilla.model_copy(update={"semantic_role": "iva_importe_rectificacion"})
                if casilla.id == "71"
                else casilla
                for casilla in revision.casillas
            )
        }
    )
    with pytest.raises(RegistryValidationError, match="iva_importe_rectificacion"):
        m303_importe_rectificacion_casilla(doubled)
