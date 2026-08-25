"""Modelo 100 Art. 85 imputed real-estate income runtime checks."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from .._authority import ValidatedRegistryAuthority, bundled_authority
from .._errors import RegistryValidationError
from .._formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from .._schema import RegistrySnapshot
from ._modelo_100_registry_support import _m100_2024_deduccion_maternidad_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@cache
def _authority() -> ValidatedRegistryAuthority:
    return bundled_authority()


def _snapshot(year: int) -> RegistrySnapshot:
    return _authority().snapshot(
        "100",
        filing_year=year,
        period="0A",
        revision_id=str(year),
    )


def _binding_values(year: int) -> dict[str, Decimal]:
    values = {
        f"renta-{year}-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        f"renta-{year}-profile-declaration-type": Decimal("1"),
        f"renta-{year}-profile-family-minor-children-in-unit": Decimal("0"),
        f"renta-{year}-profile-marriage-full-year": Decimal("0"),
        f"renta-{year}-profile-marriage-month-start": Decimal("0"),
        f"renta-{year}-profile-marriage-month-end": Decimal("0"),
        f"renta-{year}-base-liquidable-negativa-general-anterior": Decimal("0"),
        f"renta-{year}-profile-minimo-descendientes-estatal": Decimal("0"),
        f"renta-{year}-profile-minimo-descendientes-autonomico": Decimal("0"),
    }
    if year == 2025:
        # The production profile resolver supplies this predicate as 1/0 from
        # taxpayer_type.irpf_income_categories; the scenario models a directa filer.
        values["renta-2025-profile-has-economic-activity"] = Decimal("1")
        values["renta-2025-modelo-184-atribucion-actividades-economicas"] = Decimal("0")
        # Madrid nacimiento/adopción deducción (casilla 1039) profile-derived
        # facts; neutral zero when the chain under test is unrelated.
        values["renta-2025-profile-madrid-nacimiento-adopcion-eligible-count"] = Decimal("0")
        values["renta-2025-profile-unidad-familiar-otros-miembros-base"] = Decimal("0")
    if year == 2024:
        values.update(
            {
                "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
                "renta-2024-profile-incremento-guarderia": Decimal("0"),
                "renta-2024-profile-descendientes-guarderia": Decimal("0"),
                "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
                # The maternity deducción's own profile fact, neutral zero for
                # the same reason as its four siblings above: this scenario is
                # an art. 85 imputed-real-estate example and claims no
                # maternity deducción. It joined the 2024 closure after the
                # others and was the only one left unsupplied.
                **_m100_2024_deduccion_maternidad_bindings(),
            },
        )
    return values


def _calculate(
    year: int,
    *,
    inputs: Mapping[str, Decimal],
    text_inputs: Mapping[str, str] | None = None,
) -> RegistryCalculationResult:
    return calculate_registry_snapshot(
        _snapshot(year),
        inputs=inputs,
        text_inputs=text_inputs,
        date_context={"filing_period": date(year, 12, 31)},
        binding_values=_binding_values(year),
        enum_binding_values={f"renta-{year}-profile-tax-residence-ccaa": "madrid"},
        relation_values={
            f"renta-{year}-rel-130-pagos-fraccionados": Decimal("0.00"),
            f"renta-{year}-rel-131-pagos-fraccionados": Decimal("0.00"),
        },
        date_binding_values={f"renta-{year}-profile-taxpayer-birth-date": date(1985, 6, 15)},
    )


@pytest.mark.parametrize(
    ("year", "expected_formula", "expected_legal_refs", "expected_source_refs"),
    (
        (
            2025,
            "renta-2025-inmobiliario-renta-imputada-art-85",
            ("ley-35-2006:art-22", "ley-35-2006:art-85", "orden-hac-277-2026:art-3"),
            ("aeat-dr-100-2025-dictionary", "aeat-renta-2025-manual-parte1", "boe-modelo-100-2025-form"),
        ),
        (
            2024,
            "renta-2024-inmobiliario-renta-imputada-art-85",
            ("ley-35-2006:art-22", "ley-35-2006:art-85"),
            ("aeat-dr-100-2024-dictionary", "aeat-renta-2024-manual-parte1", "boe-modelo-100-2024-form"),
        ),
    ),
)
def test_m100_art85_computes_manual_cadastral_example_for_revised_value(
    year: int,
    expected_formula: str,
    expected_legal_refs: tuple[str, ...],
    expected_source_refs: tuple[str, ...],
) -> None:
    """The bundled Renta manuals work 40,800 at 1.1% to 448.80."""

    result = _calculate(
        year,
        inputs={"0083": Decimal("40800.00"), "0085": Decimal("365")},
        text_inputs={"0084": "X"},
    )

    assert result.values["0089"] == Decimal("448.80")
    assert result.values["0155"] == Decimal("448.80")
    entry = next(item for item in result.entries if item.target_casilla_id == "0089")
    assert entry.formula_id == expected_formula
    assert entry.operand_refs == (
        "0083",
        "0085",
        "0086",
        "0087",
        "0088",
        "0084",
        f"renta-{year}-imputacion-inmobiliaria-year-days",
        f"renta-{year}-imputacion-inmobiliaria-rate-recent-revision",
        f"renta-{year}-imputacion-inmobiliaria-rate-old-or-no-revision",
    )
    assert entry.legal_refs == expected_legal_refs
    assert entry.source_refs == expected_source_refs


def test_m100_art85_rejects_no_catastral_branch_until_substitute_base_exists() -> None:
    with pytest.raises(RegistryValidationError, match="substitute-base casillas"):
        _calculate(2025, inputs={"0085": Decimal("62")}, text_inputs={"0084": "X"})


def test_m100_art85_rejects_non_official_revision_checkbox_value() -> None:
    with pytest.raises(RegistryValidationError, match="official X checkbox"):
        _calculate(
            2025,
            inputs={"0083": Decimal("40800.00"), "0085": Decimal("365")},
            text_inputs={"0084": "SI"},
        )


def test_m100_art85_casilla_0089_is_no_longer_manual_input() -> None:
    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied"):
        calculate_registry_snapshot(
            _snapshot(2025),
            inputs={"0089": Decimal("448.80")},
            date_context={"filing_period": date(2025, 12, 31)},
        )
