"""Casilla 0150 resolves from the profile's lease through the real resolver and formula, every year.

The lease rows go into a real profile record; the profile binding resolver
derives the reduction's applicability and tier, and the registry's own 0150
formula applies them to the net income. The years come from the support
envelope and the dates that decide the regime from the regime fact.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.formula_expression import evaluate_expression
from ....domain.calculations.registry.rental_reduction import resolve_rental_reduction_art232_rules
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.authored_editions import supported_exercises_with_projection
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_snapshot,
)
from ....domain.renta.rental_reduction_derivation import RentalReductionArt232Rules
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ...aggregation.source_mesh import CalculationSourceDiagnostic
from ..profile_binding import resolve_profile_sourced_bindings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)
_PROFILE_ID = "10010010-0100-4100-8100-100100100150"
_NET = Decimal("6782.00")
_REDUCTION = validated_casilla_id("0150")


def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year, period="0A")


def _record(*lease_facts: tuple[str, object]) -> UserProfileRecord:
    facts = [
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="taxpayer_type.irpf_income_categories", value="capital_inmobiliario,pension"),
        *(UserProfileFact(path=f"renta_arrendamiento.0.{leaf}", value=value) for leaf, value in lease_facts),
    ]
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=tuple(facts),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=leased_profile_create_context(),
    )


def _lease(contract: date, **facts: object) -> UserProfileRecord:
    stated: dict[str, object] = {
        "inmueble": 0,
        "fecha_contrato": contract,
        "fecha_inicio": contract,
        "uso_vivienda": True,
        "zona_tensionada": False,
    }
    stated.update(facts)
    return _record(*((leaf, value) for leaf, value in stated.items() if value is not None))


def _reduction(
    year: int, record: UserProfileRecord, operation: PinnedAuthorityOperation
) -> tuple[Decimal | None, tuple[CalculationSourceDiagnostic, ...]]:
    """Resolve the profile bindings, then evaluate the edition's own 0150 formula over a positive net income."""
    snapshot = _snapshot(year)
    resolution = resolve_profile_sourced_bindings(
        snapshot, bucket_id=_PROFILE_ID, profile_record=record, operation=operation
    )
    casilla = next(row for row in snapshot.revision.casillas if row.id == _REDUCTION)
    formula = next(row for row in snapshot.revision.formulas if row.id == casilla.formula)
    try:
        value = evaluate_expression(
            formula.expression,
            values={validated_casilla_id("0100"): Decimal(1), validated_casilla_id("0149"): _NET},
            binding_values=resolution.binding_values,
            parameters={parameter.id: parameter for parameter in snapshot.revision.parameters},
            date_context={"filing_period": date(year, 12, 31)},
            relation_values={},
            unresolved_relation_ids=frozenset(),
            unresolved_casilla_ids=set(),
            operand_refs=[],
            operand_casilla_refs=[],
            operand_values=[],
            enum_binding_values=resolution.enum_binding_values,
            boolean_binding_values=resolution.boolean_binding_values,
            filing_year=year,
        )
    except RegistryValidationError:
        return None, _reduction_diagnostics(resolution.diagnostics)
    return value.quantize(Decimal("0.01")), _reduction_diagnostics(resolution.diagnostics)


def _reduction_diagnostics(
    diagnostics: tuple[CalculationSourceDiagnostic, ...],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Keep the diagnostics raised against the reduction box; the minimal profile leaves other boxes open."""
    return tuple(diagnostic for diagnostic in diagnostics if diagnostic.casilla_id == _REDUCTION)


def _rules(year: int, operation: PinnedAuthorityOperation) -> RentalReductionArt232Rules:
    return resolve_rental_reduction_art232_rules(
        revision_id=_snapshot(year).revision.id, devengo=date(year, 12, 31), operation=operation
    )


@pytest.mark.parametrize("year", supported_exercises_with_projection("100"))
def test_casilla_0150_resolves_for_a_lease_active_in_the_ejercicio_from_the_cut_off(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    rules = _rules(year, authority_operation)
    contract = rules.contract_cut_off if rules.contract_cut_off <= date(year, 12, 31) else date(year, 1, 1)
    value, diagnostics = _reduction(year, _lease(contract), authority_operation)
    legacy = date(year, 12, 31) < rules.regime_start or contract < rules.contract_cut_off
    rate = Decimal("0.60") if legacy else Decimal("0.50")
    assert value == (_NET * rate).quantize(Decimal("0.01")), year
    assert not diagnostics


@pytest.mark.parametrize("year", supported_exercises_with_projection("100"))
def test_a_legacy_contract_keeps_sixty_per_cent_every_year(
    year: int, authority_operation: PinnedAuthorityOperation
) -> None:
    rules = _rules(year, authority_operation)
    record = _lease(min(rules.contract_cut_off - timedelta(days=1), date(year, 1, 1)))
    value, _ = _reduction(year, record, authority_operation)
    assert value == (_NET * Decimal("0.60")).quantize(Decimal("0.01")), year


def test_a_lau_breach_reduces_nothing_and_an_unstated_fact_leaves_the_box_unresolved_with_its_door(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    year = supported_exercises_with_projection("100")[-1]
    rules = _rules(year, authority_operation)
    breach, _ = _reduction(
        year,
        _lease(rules.contract_cut_off, zona_tensionada=True, incumple_lau_17_6=True),
        authority_operation,
    )
    unstated, diagnostics = _reduction(year, _lease(rules.contract_cut_off, zona_tensionada=True), authority_operation)
    assert breach == Decimal("0.00")
    assert unstated is None
    assert [(diagnostic.reason, diagnostic.remedy) for diagnostic in diagnostics] == [
        ("source_issue", "aeat config profile arrendamiento edit")
    ]
