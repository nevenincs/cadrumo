"""Modelo 100 Art. 85 imputed real-estate income runtime checks."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from functools import cache

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition, revision_covering
from dev.registry.compiler.authority import compiled_bundled_authority

from .modelo_100_registry_support import (
    m100_second_newest_deduccion_maternidad_bindings,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The newest authored edition and the one before it, which the scenario supplies different profile facts for.
_NEWEST = newest_authored_edition("100")
_PREVIOUS = _NEWEST - 1


@cache
def _authority() -> ValidatedRegistryAuthority:
    return compiled_bundled_authority()


def _snapshot(year: int) -> RegistrySnapshot:
    return _authority().snapshot(
        "100",
        filing_year=year,
        period="0A",
        revision_id=str(revision_covering("100", year).id),
    )


def _binding_values(year: int) -> dict[str, Decimal]:
    values = {
        "renta-profile-has-economic-activity": Decimal("1"),
        "renta-profile-estimacion-directa": Decimal("1"),
        "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-profile-declaration-type": Decimal("1"),
        "renta-profile-family-minor-children-in-unit": Decimal("0"),
        "renta-profile-marriage-full-year": Decimal("0"),
        "renta-profile-marriage-month-start": Decimal("0"),
        "renta-profile-marriage-month-end": Decimal("0"),
        "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
        "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
        "renta-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
    }
    if year == _NEWEST:
        # The production profile resolver supplies this predicate as 1/0 from
        # taxpayer_type.irpf_income_categories; the scenario models a directa filer.
        values["renta-profile-has-economic-activity"] = Decimal("1")
        # Madrid nacimiento/adopción deducción (casilla 1039) profile-derived
        # facts; neutral zero when the chain under test is unrelated.
        values["renta-profile-madrid-nacimiento-adopcion-eligible-count"] = Decimal("0")
        values["renta-profile-unidad-familiar-otros-miembros-base"] = Decimal("0")
        # The Canarias maritime-registry exemption's three numeric facts, whose
        # boolean predicate is answered False beside them: a taxpayer claiming
        # nothing there still has to supply the facts, because an unsupplied
        # binding is a refusal rather than a zero.
        values["renta-maritime-gross-navigation-income"] = Decimal("0")
        values["renta-maritime-annual-salary"] = Decimal("0")
        values["renta-maritime-qualifying-days"] = Decimal("0")
        # The 2025 edition computes the maternity deducción as well; neutral
        # zero for the same reason as in 2024 below.
        values.update(m100_second_newest_deduccion_maternidad_bindings())
    if year == _PREVIOUS:
        values.update(
            {
                "renta-profile-incremento-guarderia": Decimal("0"),
                "renta-profile-cotizaciones-ss-madre": Decimal("0"),
                # The maternity deducción's own profile fact, neutral zero for
                # the same reason as its four siblings above: this scenario is
                # an art. 85 imputed-real-estate example and claims no
                # maternity deducción. It joined the 2024 closure after the
                # others and was the only one left unsupplied.
                **m100_second_newest_deduccion_maternidad_bindings(),
            },
        )
    return values


def _boolean_binding_values(year: int) -> dict[str, bool]:
    """Boolean profile predicates this scenario answers in the negative.

    The taxpayer in the Renta manual example is an ordinary resident with an
    imputed real-estate income, so the Canarias maritime-registry exemption path
    does not apply. It is supplied rather than left absent because an unsupplied
    binding is a refusal, not a false: the registry keeps "not claimed" and "no
    answer" apart, and this scenario is claiming nothing.
    """
    if year < _NEWEST:
        return {}
    return {"renta-maritime-path-rebeca": False}


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
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal("0.00"),
            "renta-modelo-131-pagos-fraccionados": Decimal("0.00"),
        },
        date_binding_values={"renta-profile-taxpayer-birth-date": date(1985, 6, 15)},
        boolean_binding_values=_boolean_binding_values(year),
    )


@pytest.mark.parametrize(
    ("year", "expected_formula", "expected_legal_refs", "expected_source_refs"),
    (
        (
            _NEWEST,
            "renta-inmobiliario-renta-imputada-art-85",
            ("ley-35-2006:art-22", "ley-35-2006:art-85", "orden-hac-277-2026:art-3"),
            (
                f"aeat-dr-100-{_NEWEST}-dictionary",
                f"aeat-renta-{_NEWEST}-manual-parte1",
                f"boe-modelo-100-{_NEWEST}-form",
            ),
        ),
        (
            _PREVIOUS,
            "renta-inmobiliario-renta-imputada-art-85",
            ("ley-35-2006:art-22", "ley-35-2006:art-85"),
            (
                f"aeat-dr-100-{_PREVIOUS}-dictionary",
                f"aeat-renta-{_PREVIOUS}-manual-parte1",
                f"boe-modelo-100-{_PREVIOUS}-form",
            ),
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
        "renta-imputacion-inmobiliaria-year-days",
        "renta-imputacion-inmobiliaria-rate-recent-revision",
        "renta-imputacion-inmobiliaria-rate-old-or-no-revision",
    )
    assert entry.legal_refs == expected_legal_refs
    assert entry.source_refs == expected_source_refs


def test_m100_art85_rejects_no_catastral_branch_until_substitute_base_exists() -> None:
    with pytest.raises(RegistryValidationError, match="substitute-base casillas"):
        _calculate(_NEWEST, inputs={"0085": Decimal("62")}, text_inputs={"0084": "X"})


def test_m100_art85_rejects_non_official_revision_checkbox_value() -> None:
    with pytest.raises(RegistryValidationError, match="official X checkbox"):
        _calculate(
            _NEWEST,
            inputs={"0083": Decimal("40800.00"), "0085": Decimal("365")},
            text_inputs={"0084": "SI"},
        )


def test_m100_art85_casilla_0089_is_no_longer_manual_input() -> None:
    with pytest.raises(RegistryValidationError, match="computed registry casillas cannot be supplied"):
        calculate_registry_snapshot(
            _snapshot(_NEWEST),
            inputs={"0089": Decimal("448.80")},
            date_context={"filing_period": date(_NEWEST, 12, 31)},
        )
