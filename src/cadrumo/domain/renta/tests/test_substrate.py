"""Membership + round-trip tests for the Renta substrate enums.

Pins membership and round-trip semantics for :class:`RentaIncomeType`
and :class:`EstimacionDirectaModalidad` so accidental additions or
removals surface as test failures.  Mirrors the
:mod:`cadrumo.domain.iva.test_categories` pattern.

The former ``RentaCCAA`` enum has been removed; the canonical CCAA type is
:class:`cadrumo.domain.contribuyente.CCAA`.  Tests for that enum (including the
ISO-code mapping) live in :mod:`cadrumo.domain.contribuyente.test_model`.
"""

from __future__ import annotations

import pytest

from .._substrate import EstimacionDirectaModalidad, RentaIncomeType

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_renta_income_type_carries_every_top_level_lirpf_branch() -> None:
    """RentaIncomeType must carry exactly the 11 top-level LIRPF income axes.

    Each axis maps to a distinct branch of LIRPF article 6: trabajo (art.
    17), capital mobiliario split into the base-general fraction (art. 25.4)
    and the base-ahorro fraction (art. 25.1, 25.2, 25.3), capital
    inmobiliario (art. 22), actividades económicas in three modalities
    (directa normal, directa simplificada, objetiva), ganancias y pérdidas
    patrimoniales split into base-general / base-ahorro (art. 33-37),
    imputación de rentas (art. 85, 91-95), atribución de rentas (art. 88-90).
    """
    expected = {
        "TRABAJO",
        "CAPITAL_MOBILIARIO_GENERAL",
        "CAPITAL_MOBILIARIO_AHORRO",
        "CAPITAL_INMOBILIARIO",
        "ACTIVIDADES_ECONOMICAS_DIRECTA_NORMAL",
        "ACTIVIDADES_ECONOMICAS_DIRECTA_SIMPLIFICADA",
        "ACTIVIDADES_ECONOMICAS_OBJETIVA",
        "GANANCIAS_PERDIDAS_GENERAL",
        "GANANCIAS_PERDIDAS_AHORRO",
        "IMPUTACION_RENTAS",
        "ATRIBUCION_RENTAS",
    }
    assert {member.name for member in RentaIncomeType} == expected


def test_renta_income_type_values_roundtrip_through_strenum() -> None:
    """Every RentaIncomeType value re-parses to the same member."""
    for member in RentaIncomeType:
        assert RentaIncomeType(member.value) is member


def test_estimacion_directa_modalidad_carries_normal_and_simplificada() -> None:
    """EstimacionDirectaModalidad must carry exactly the two LIRPF art. 30 modalities."""
    assert {member.name for member in EstimacionDirectaModalidad} == {"NORMAL", "SIMPLIFICADA"}


def test_estimacion_directa_modalidad_values_roundtrip() -> None:
    """Every EstimacionDirectaModalidad value re-parses to the same member."""
    for member in EstimacionDirectaModalidad:
        assert EstimacionDirectaModalidad(member.value) is member


def test_estimacion_directa_modalidad_normal_distinguishable_from_simplificada() -> None:
    """The two modalities must be distinct objects (sanity check for downstream branching)."""
    assert EstimacionDirectaModalidad.NORMAL is not EstimacionDirectaModalidad.SIMPLIFICADA
    assert EstimacionDirectaModalidad.NORMAL.value != EstimacionDirectaModalidad.SIMPLIFICADA.value
