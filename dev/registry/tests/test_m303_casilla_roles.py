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
from cadrumo.domain.calculations.registry.tests.authored_editions import authored_revisions, split_exercise_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Box numbers carried from the earlier fixed checks: box 71 states the result in every edition,
# and box 111 first appears in the edition applying from September and 3T of 2024.
_AUTHORED = authored_revisions("303")
_EDITION_APPLYING_FROM_SEPTEMBER = split_exercise_revisions("303", early_period="2T", late_period="3T")[1]
_FIRST_WITH_RECTIFICACION = _AUTHORED.index(_EDITION_APPLYING_FROM_SEPTEMBER)


def _coordinate(index: int) -> tuple[int, str, str, str | None]:
    """The exercise and last quarter of one authored edition, with the boxes it prints."""
    revision = _AUTHORED[index]
    year = revision.valid_from.year
    quarter = next(period for period in reversed(revision.period_selector.periods_for_year(year)) if period[-1] == "T")
    return year, quarter, "71", ("111" if index >= _FIRST_WITH_RECTIFICACION else None)


_COORDINATES = tuple(_coordinate(index) for index in range(len(_AUTHORED)))
_NEWEST = _COORDINATES[-1][:2]


def _revision(year: int, period: str) -> ModeloRevision:
    with bundled_indexed_authority().operation() as operation:
        return operation.revision_for_context("303", filing_year=year, period=period)


@pytest.mark.parametrize(("year", "period", "resultado", "rectificacion"), _COORDINATES)
def test_each_edition_declares_the_printed_boxes(
    year: int, period: str, resultado: str, rectificacion: str | None
) -> None:
    revision = _revision(year, period)
    assert str(revision.id) == str(_AUTHORED[_COORDINATES.index((year, period, resultado, rectificacion))].id)
    assert m303_resultado_final_casilla(revision) == resultado
    assert m303_importe_rectificacion_casilla(revision) == rectificacion


def test_an_edition_without_the_result_role_is_refused() -> None:
    revision = _revision(*_NEWEST)
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
    revision = _revision(*_NEWEST)
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
