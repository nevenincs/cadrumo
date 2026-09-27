"""Oracle tests for M100 casilla 0511 -- minimo del contribuyente (parte estatal).

Ground truth: Art. 57.1.b LIRPF + AEAT renta manual (both authored
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

import pytest

from .....core.casilla_id import CasillaId, validated_casilla_id
from ..formula_runtime import calculate_registry_snapshot
from ..schema import RegistrySnapshot
from ._modelo_100_registry_support import M100_2024_EMPTY_MATERNIDAD_BINDINGS
from .authored_editions import newest_authored_editions
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

# The two newest Modelo 100 editions the registry authors; each carries its own
# binding set, so each has its own calculation helper below.
_PRIOR_EDITION, _REVIEWED_EDITION = newest_authored_editions("100", 2)

_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA: CasillaId = validated_casilla_id(
    "0511",
    surface="_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA",
)


def _snapshot(filing_year: int) -> RegistrySnapshot:
    """Load the committed M100 artifact for the requested filing year."""
    return published_snapshot("100", filing_year=filing_year, period="0A")


def _m100_2024_deduccion_maternidad_bindings() -> dict[str, Decimal]:
    return dict(M100_2024_EMPTY_MATERNIDAD_BINDINGS)


# Relation values required by the prior-edition snapshot (zero - not exercised).
_REL_PRIOR_EDITION = {
    "renta-modelo-111-retenciones-periodicas": Decimal("0"),
    "renta-modelo-123-retenciones-periodicas": Decimal("0"),
    "renta-modelo-193-retenciones-anuales": Decimal("0"),
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}

# Relation values required by the reviewed-edition snapshot (zero - not exercised).
_REL_REVIEWED_EDITION = {
    "renta-modelo-111-retenciones-periodicas": Decimal("0"),
    "renta-modelo-123-retenciones-periodicas": Decimal("0"),
    "renta-modelo-193-retenciones-anuales": Decimal("0"),
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}


def _calc_prior_edition(birth_date: date) -> Mapping[CasillaId, Decimal]:
    """Run the prior-edition snapshot calculation for a single-taxpayer scenario."""
    snap = _snapshot(_PRIOR_EDITION)
    result = calculate_registry_snapshot(
        snap,
        inputs={},
        date_context={"filing_period": date(_PRIOR_EDITION, 12, 31)},
        binding_values={
            "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-modelo-111-retenciones-periodicas": Decimal("0"),
            "renta-modelo-123-retenciones-periodicas": Decimal("0"),
            "renta-modelo-193-retenciones-anuales": Decimal("0"),
            # declaration_type = 1 (individual) -> 0461 computed = 0
            "renta-profile-declaration-type": Decimal("1"),
            "renta-profile-family-minor-children-in-unit": Decimal("0"),
            # Art. 81.2 LIRPF guarderia bindings (b7ad3a993): zero in non-guarderia scenarios.
            "renta-profile-guarderia-gastos-reales": Decimal("0"),
            "renta-profile-incremento-guarderia": Decimal("0"),
            "renta-profile-cotizaciones-ss-madre": Decimal("0"),
            "renta-profile-descendientes-guarderia": Decimal("0"),
            **_m100_2024_deduccion_maternidad_bindings(),
            "renta-profile-minimo-descendientes-estatal": Decimal("0"),
            "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
            "renta-profile-marriage-full-year": Decimal("0"),
            "renta-profile-marriage-month-start": Decimal("0"),
            "renta-profile-marriage-month-end": Decimal("0"),
            # BIN-pendiente fresh-filer baseline.
            "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
        },
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_PRIOR_EDITION,
        date_binding_values={"renta-profile-taxpayer-birth-date": birth_date},
    )
    return result.values


def _calc_reviewed_edition(birth_date: date) -> Mapping[CasillaId, Decimal]:
    """Run the reviewed-edition snapshot calculation for a single-taxpayer scenario."""
    snap = _snapshot(_REVIEWED_EDITION)
    result = calculate_registry_snapshot(
        snap,
        inputs={},
        date_context={"filing_period": date(_REVIEWED_EDITION, 12, 31)},
        binding_values={
            # Estimación directa normal filer -> declares economic activity;
            # the production profile resolver supplies this predicate as 1/0 from
            # taxpayer_type.irpf_income_categories, so a directa scenario is 1.
            "renta-profile-has-economic-activity": Decimal("1"),
            "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
            "renta-modelo-184-atribucion-actividades-economicas": Decimal("0"),
            # declaration_type = 1 (individual) -> 0461 computed = 0
            "renta-profile-declaration-type": Decimal("1"),
            "renta-profile-family-minor-children-in-unit": Decimal("0"),
            "renta-profile-marriage-full-year": Decimal("0"),
            "renta-profile-marriage-month-start": Decimal("0"),
            "renta-profile-marriage-month-end": Decimal("0"),
            # BIN-pendiente fresh-filer baseline (reviewed-edition binding).
            "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
            # Madrid nacimiento/adopción deducción (casilla 1039) profile-derived
            # facts; neutral zero when the chain under test is unrelated.
            "renta-profile-madrid-nacimiento-adopcion-eligible-count": Decimal("0"),
            # Art. 75 Ley 19/1994 / Art. 7.p) LIRPF maritime-worker exemption operands;
            # neutral zero when the chain under test is unrelated (the path itself is false).
            "renta-maritime-gross-navigation-income": Decimal("0"),
            "renta-maritime-annual-salary": Decimal("0"),
            "renta-maritime-qualifying-days": Decimal("0"),
            "renta-profile-unidad-familiar-otros-miembros-base": Decimal("0"),
            "renta-profile-minimo-descendientes-estatal": Decimal("0"),
            "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
        },
        boolean_binding_values={"renta-maritime-path-rebeca": False},
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        relation_values=_REL_REVIEWED_EDITION,
        date_binding_values={"renta-profile-taxpayer-birth-date": birth_date},
    )
    return result.values


_CALCULATORS = {
    _PRIOR_EDITION: _calc_prior_edition,
    _REVIEWED_EDITION: _calc_reviewed_edition,
}


# ---------------------------------------------------------------------------
# Oracle tests -- Art. 57.1.b LIRPF, three age brackets, both authored editions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filing_year", tuple(_CALCULATORS))
@pytest.mark.parametrize(
    ("age_at_year_end", "month", "day", "expected", "label"),
    [
        # Turns 65 in March of the exercise -> age at year-end = 65
        (65, 3, 15, Decimal("6700.00"), "age-65-primer-tramo"),
        # Turns 75 in March of the exercise -> age at year-end = 75
        (75, 3, 15, Decimal("8100.00"), "age-75-segundo-tramo"),
        # Turns 59 during the exercise -> under 65, base only
        (59, 1, 1, Decimal("5550.00"), "under-65-base-only"),
        # Turns 65 in mid-December, still 65 at year-end
        (65, 12, 15, Decimal("6700.00"), "age-65-december-born"),
    ],
)
def test_0511_age_bracket(
    filing_year: int,
    age_at_year_end: int,
    month: int,
    day: int,
    expected: Decimal,
    label: str,
) -> None:
    """Casilla 0511 returns the correct age-derived amount for each authored edition.

    Values are grounded in Art. 57.1.b LIRPF and the AEAT renta manual
    (section Minimo del contribuyente).  Base 5 550 EUR, +1 150 EUR for age >= 65,
    +1 400 EUR additional for age >= 75.
    """
    birth_date = date(filing_year - age_at_year_end, month, day)
    values = _CALCULATORS[filing_year](birth_date)
    actual = values[_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA]
    assert actual == expected, (
        f"0511 ({label}): got {actual!r}, expected {expected!r} (birth_date={birth_date}, filing_year={filing_year})"
    )


# ---------------------------------------------------------------------------
# Anti-tautology: changing birth_date across a threshold changes 0511
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("filing_year", tuple(_CALCULATORS))
def test_0511_birth_date_change_alters_value(filing_year: int) -> None:
    """Moving birth_date across the 65-year threshold changes casilla 0511.

    Proves the formula is genuinely age-sensitive and does not return a
    constant regardless of date input.
    """
    values_under_65 = _CALCULATORS[filing_year](date(filing_year - 59, 1, 1))
    values_over_65 = _CALCULATORS[filing_year](date(filing_year - 65, 3, 15))

    v_under = values_under_65[_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA]
    v_over = values_over_65[_MINIMO_CONTRIBUYENTE_ESTATAL_CASILLA]

    assert v_under != v_over, f"0511 must differ across the 65-year threshold: under-65={v_under}, over-65={v_over}"
