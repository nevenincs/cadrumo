"""Membership + round-trip tests for the Renta substrate enums.

Pins membership and round-trip semantics for :class:`RentaIncomeType`,
:class:`RentaCCAA`, and :class:`EstimacionDirectaModalidad` so accidental
additions or removals surface as test failures. Mirrors the
:mod:`aeat.domain.vat.test_categories` pattern.
"""

from __future__ import annotations

import pytest

from . import EstimacionDirectaModalidad, RentaCCAA, RentaIncomeType

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


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


def test_renta_ccaa_carries_17_autonomous_communities_plus_ceuta_melilla() -> None:
    """RentaCCAA must cover 17 comunidades + 2 ciudades autónomas = 19 members.

    Foral regimes (País Vasco, Navarra) are represented as single autonomous
    community members. Sub-territorial diputaciones forales (Álava, Bizkaia,
    Gipuzkoa) are NOT exposed at this granularity; consumers that need them
    must layer a separate selector.
    """
    expected = {
        "AND", "ARA", "AST", "BAL", "CAN", "CAB", "CLM", "CYL", "CAT", "EXT",
        "GAL", "MAD", "MUR", "NAV", "PVA", "LAR", "VAL", "CEU", "MEL",
    }
    assert {member.name for member in RentaCCAA} == expected


def test_renta_ccaa_values_roundtrip_through_strenum() -> None:
    """Every RentaCCAA value re-parses to the same member."""
    for member in RentaCCAA:
        assert RentaCCAA(member.value) is member


def test_renta_ccaa_values_are_lowercase_3_letter_codes() -> None:
    """Each RentaCCAA value is a lowercase 3-letter code, mirroring the EU member-state convention."""
    for member in RentaCCAA:
        assert len(member.value) == 3
        assert member.value.lower() == member.value


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
