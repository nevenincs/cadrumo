"""Oracle tests for M100 casilla 0511 -- minimo del contribuyente (parte estatal).

Ground truth: Art. 57.1.b LIRPF + AEAT renta manual (both 2024 and 2025
editions).  Age is reckoned at 31 December of the filing year (year-end).

    Under 65         ->  5 550,00 EUR  (base only, Art. 57.1.a)
    Age 65-74        ->  6 700,00 EUR  (5 550 + 1 150, Art. 57.1.b primer tramo)
    Age >= 75        ->  8 100,00 EUR  (5 550 + 1 150 + 1 400, Art. 57.1.b segundo tramo)

Anti-tautology: a birth_date that crosses an age threshold must change the
computed 0511 value; the test verifies strict inequality so a broken formula
that always returns the same value cannot pass.

These tests use load_registry_tree + build_snapshot + calculate_registry_snapshot
directly, bypassing ValidatedRegistryAuthority corpus-citation validation.  The
goal is to verify that the age-at-year-end formula operator evaluates correctly
-- not to audit registry integrity.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from .....core import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .. import RegistrySnapshot, build_snapshot
from ..formula_runtime import calculate_registry_snapshot
from ..loader import load_registry_tree
from ._modelo_100_registry_support import _m100_2024_deduccion_maternidad_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_SOURCE_ROOT = bundled_path()
_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA: CasillaId = validated_casilla_id(
    "0511",
    surface="_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA",
)


@cache
def _registry():
    """Load the registry tree once for the session."""
    # Import for side-effect: cross-domain snapshot checks.

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    return {m.id: m for m in modelos}, catalogues


def _snapshot(filing_year: int) -> RegistrySnapshot:
    """Build an M100 snapshot for the given filing_year, bypassing corpus validation."""
    modelos_by_id, catalogues = _registry()
    return build_snapshot(
        modelos_by_id["100"],
        catalogues,
        source_root=_SOURCE_ROOT,
        filing_year=filing_year,
        period="0A",
    )


# Relation values required by the 2024 snapshot (zero - not exercised).
_REL_2024 = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}

# Relation values required by the 2025 snapshot (zero - not exercised).
_REL_2025 = {
    "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
}


def _calc_2024(birth_date: date) -> Mapping[CasillaId, Decimal]:
    """Run the 2024 snapshot calculation for a single-taxpayer scenario."""
    snap = _snapshot(2024)
    result = calculate_registry_snapshot(
        snap,
        inputs={},
        date_context={"filing_period": date(2024, 12, 31)},
        binding_values={
            "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
            # declaration_type = 1 (individual) -> 0461 computed = 0
            "renta-2024-profile-declaration-type": Decimal("1"),
            "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
            # Art. 81.2 LIRPF guarderia bindings (b7ad3a993): zero in non-guarderia scenarios.
            "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
            "renta-2024-profile-incremento-guarderia": Decimal("0"),
            "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
            "renta-2024-profile-descendientes-guarderia": Decimal("0"),
            **_m100_2024_deduccion_maternidad_bindings(),
            "renta-2024-profile-minimo-descendientes-estatal": Decimal("0"),
            "renta-2024-profile-minimo-descendientes-autonomico": Decimal("0"),
            "renta-2024-profile-marriage-full-year": Decimal("0"),
            "renta-2024-profile-marriage-month-start": Decimal("0"),
            "renta-2024-profile-marriage-month-end": Decimal("0"),
            # BIN-pendiente fresh-filer baseline.
            "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={"renta-2024-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2024,
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": birth_date},
    )
    return result.values


def _calc_2025(birth_date: date) -> Mapping[CasillaId, Decimal]:
    """Run the 2025 snapshot calculation for a single-taxpayer scenario."""
    snap = _snapshot(2025)
    result = calculate_registry_snapshot(
        snap,
        inputs={},
        date_context={"filing_period": date(2025, 12, 31)},
        binding_values={
            # Estimación directa normal filer -> declares economic activity;
            # the production profile resolver supplies this predicate as 1/0 from
            # taxpayer_type.irpf_income_categories, so a directa scenario is 1.
            "renta-2025-profile-has-economic-activity": Decimal("1"),
            "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            # declaration_type = 1 (individual) -> 0461 computed = 0
            "renta-2025-profile-declaration-type": Decimal("1"),
            "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-2025-profile-marriage-full-year": Decimal("0"),
            "renta-2025-profile-marriage-month-start": Decimal("0"),
            "renta-2025-profile-marriage-month-end": Decimal("0"),
            # BIN-pendiente fresh-filer baseline (2025 binding).
            "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
            # Madrid nacimiento/adopción deducción (casilla 1039) profile-derived
            # facts; neutral zero when the chain under test is unrelated.
            "renta-2025-profile-madrid-nacimiento-adopcion-eligible-count": Decimal("0"),
            "renta-2025-profile-unidad-familiar-otros-miembros-base": Decimal("0"),
            "renta-2025-profile-minimo-descendientes-estatal": Decimal("0"),
            "renta-2025-profile-minimo-descendientes-autonomico": Decimal("0"),
        },
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_2025,
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": birth_date},
    )
    return result.values


# ---------------------------------------------------------------------------
# 2024 oracle tests -- Art. 57.1.b LIRPF, three age brackets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("birth_date", "expected", "label"),
    [
        # Born 1959-03-15: turns 65 on 15 March 2024 -> age at year-end = 65
        (date(1959, 3, 15), Decimal("6700.00"), "age-65-primer-tramo"),
        # Born 1949-03-15: turns 75 on 15 March 2024 -> age at year-end = 75
        (date(1949, 3, 15), Decimal("8100.00"), "age-75-segundo-tramo"),
        # Born 1965-01-01: turns 59 in 2024 -> under 65, base only
        (date(1965, 1, 1), Decimal("5550.00"), "under-65-base-only"),
        # Born 1959-12-15: turns 65 on 15 Dec 2024, still 65 at year-end
        (date(1959, 12, 15), Decimal("6700.00"), "age-65-december-born"),
    ],
)
def test_0511_age_bracket_2024(birth_date: date, expected: Decimal, label: str) -> None:
    """Casilla 0511 returns the correct age-derived amount for 2024 filing year.

    Values are grounded in Art. 57.1.b LIRPF and the AEAT renta 2024 manual
    (section Minimo del contribuyente).  Base 5 550 EUR, +1 150 EUR for age >= 65,
    +1 400 EUR additional for age >= 75.
    """
    values = _calc_2024(birth_date)
    actual = values[_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA]
    assert actual == expected, (
        f"0511 ({label}): got {actual!r}, expected {expected!r} (birth_date={birth_date}, filing_year=2024)"
    )


# ---------------------------------------------------------------------------
# 2025 oracle tests -- same brackets apply under orden-hac-277-2026
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("birth_date", "expected", "label"),
    [
        (date(1960, 3, 15), Decimal("6700.00"), "age-65-primer-tramo"),
        (date(1950, 3, 15), Decimal("8100.00"), "age-75-segundo-tramo"),
        (date(1966, 1, 1), Decimal("5550.00"), "under-65-base-only"),
    ],
)
def test_0511_age_bracket_2025(birth_date: date, expected: Decimal, label: str) -> None:
    """Casilla 0511 returns the correct age-derived amount for 2025 filing year."""
    values = _calc_2025(birth_date)
    actual = values[_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA]
    assert actual == expected, (
        f"0511 ({label}): got {actual!r}, expected {expected!r} (birth_date={birth_date}, filing_year=2025)"
    )


# ---------------------------------------------------------------------------
# Anti-tautology: changing birth_date across a threshold changes 0511
# ---------------------------------------------------------------------------


def test_0511_birth_date_change_alters_value_2024() -> None:
    """Moving birth_date across the 65-year threshold changes casilla 0511.

    Proves the formula is genuinely age-sensitive and does not return a
    constant regardless of date input.
    """
    values_under_65 = _calc_2024(date(1965, 1, 1))  # 59 at year-end 2024
    values_over_65 = _calc_2024(date(1959, 3, 15))  # 65 at year-end 2024

    v_under = values_under_65[_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA]
    v_over = values_over_65[_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA]

    assert v_under != v_over, f"0511 must differ across the 65-year threshold: under-65={v_under}, over-65={v_over}"
