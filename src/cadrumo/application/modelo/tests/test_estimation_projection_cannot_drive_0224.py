"""A stored estimation projection cannot decide Modelo 100 casilla 0224.

Casilla 0224 (rendimiento neto of the estimacion directa block) branches on two
engine-derived profile paths: whether the regime is a direct estimation, and
whether its modality is normal. Both are computed from the declared
``irpf.estimation_regime``. A profile can still hold a value at either path,
stored before the paths were declared derived, and the profile fact index
exposes every stored path. These tests prove such a value is inert.

The probe runs the real profile resolver (with its injectors) over a record
holding stale values that contradict the regime, then evaluates the published
0224 formula of every supported Modelo 100 year with exactly the channels that
resolver produced. A whole-return calculation is not used because Modelo 100
needs a complete bound-casilla input set before it evaluates at all, which
would test input assembly rather than this branch.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError, RegistryError
from ....domain.calculations.registry.formula_expression import evaluate_expression
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context,
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...aggregation.source_mesh import CalculationSourceResolution
from ..profile_binding import resolve_profile_sourced_bindings

pytestmark = [pytest.mark.integration, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_PROFILE_ID = "10000000-0000-4000-8000-000000000224"
_CLOCK = datetime(1980, 1, 1, 9, 0, 0, tzinfo=UTC)
_PERIOD = "0A"
_TARGET = "0224"
_DIRECT_BINDING = "renta-profile-estimacion-directa"
_NORMAL_BINDING = "renta-modelo-100-estimacion-directa-es-normal"

#: Distinct operands, so the normal branch (0180 - 0220) and the simplificada
#: branch (0180 - 0223) give different figures and the chosen branch is visible.
_CASILLA_VALUES = {"0180": Decimal("1000"), "0220": Decimal("100"), "0223": Decimal("300")}
_NORMAL_RESULT = Decimal("900")
_SIMPLIFICADA_RESULT = Decimal("700")

_STALE_PROJECTIONS = (
    UserProfileFact(path="irpf.estimation_directa", value=True),
    UserProfileFact(path="irpf.estimation_directa_normal", value=True),
)


def _supported_years() -> tuple[int, ...]:
    support = published_supported_filing_years()
    assert support is not None
    years: list[int] = []
    for year in sorted(support.years):
        try:
            published_snapshot("100", filing_year=year, period=_PERIOD)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        years.append(year)
    assert years
    return tuple(years)


def _record(*facts: UserProfileFact) -> object:
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            *facts,
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=leased_profile_create_context(),
    )


def _resolve(snapshot: RegistrySnapshot, operation: PinnedAuthorityOperation, *facts: UserProfileFact):
    return resolve_profile_sourced_bindings(
        snapshot,
        bucket_id=_PROFILE_ID,
        profile_record=_record(*facts),
        operation=operation,
    )


def _evaluate_0224(snapshot: RegistrySnapshot, resolution: CalculationSourceResolution) -> Decimal:
    formula = next(item for item in snapshot.revision.formulas if item.target_casilla_id == _TARGET)
    return evaluate_expression(
        formula.expression,
        values={validated_casilla_id(key): value for key, value in _CASILLA_VALUES.items()},
        binding_values=resolution.binding_values,
        parameters={parameter.id: parameter for parameter in snapshot.revision.parameters},
        date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
        relation_values={},
        unresolved_relation_ids=frozenset(),
        unresolved_casilla_ids=set(),
        operand_refs=[],
        operand_casilla_refs=[],
        operand_values=[],
        unresolved_binding_ids=frozenset(resolution.unresolved_binding_ids),
        enum_binding_values=resolution.enum_binding_values,
        date_binding_values=resolution.date_binding_values,
        boolean_binding_values=resolution.boolean_binding_values,
        filing_year=snapshot.filing_year,
    )


def test_with_no_regime_declared_a_stored_projection_leaves_0224_unresolved(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    for year in _supported_years():
        snapshot = published_snapshot("100", filing_year=year, period=_PERIOD)
        resolution = _resolve(snapshot, authority_operation, *_STALE_PROJECTIONS)

        assert _DIRECT_BINDING not in resolution.boolean_binding_values, year
        assert _NORMAL_BINDING not in resolution.boolean_binding_values, year
        with pytest.raises(RegistryError):
            _evaluate_0224(snapshot, resolution)


def test_without_the_stored_projection_0224_is_equally_unresolved(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Control: the unresolved answer above is the regime's absence, not the stale fact."""
    for year in _supported_years():
        snapshot = published_snapshot("100", filing_year=year, period=_PERIOD)
        with pytest.raises(RegistryError):
            _evaluate_0224(snapshot, _resolve(snapshot, authority_operation))


@pytest.mark.parametrize(
    ("regime", "expected"),
    [("directa_normal", _NORMAL_RESULT), ("directa_simplificada", _SIMPLIFICADA_RESULT)],
)
def test_a_declared_regime_decides_0224_over_a_contradicting_stored_projection(
    authority_operation: PinnedAuthorityOperation, regime: str, expected: Decimal
) -> None:
    contradicting = (
        UserProfileFact(path="irpf.estimation_directa", value=False),
        UserProfileFact(path="irpf.estimation_directa_normal", value=regime != "directa_normal"),
    )
    for year in _supported_years():
        snapshot = published_snapshot("100", filing_year=year, period=_PERIOD)
        stale = _resolve(
            snapshot,
            authority_operation,
            UserProfileFact(path="irpf.estimation_regime", value=regime),
            *contradicting,
        )
        clean = _resolve(snapshot, authority_operation, UserProfileFact(path="irpf.estimation_regime", value=regime))

        assert stale.boolean_binding_values[_DIRECT_BINDING] is True, year
        assert stale.boolean_binding_values[_NORMAL_BINDING] is (regime == "directa_normal"), year
        assert _evaluate_0224(snapshot, stale) == expected, year
        assert _evaluate_0224(snapshot, clean) == expected, year


def test_an_objetiva_regime_is_not_turned_into_a_direct_block_by_a_stored_projection(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    for year in _supported_years():
        snapshot = published_snapshot("100", filing_year=year, period=_PERIOD)
        resolution = _resolve(
            snapshot,
            authority_operation,
            UserProfileFact(path="irpf.estimation_regime", value="objetiva"),
            *_STALE_PROJECTIONS,
        )

        assert resolution.boolean_binding_values[_DIRECT_BINDING] is False, year
        assert _NORMAL_BINDING not in resolution.boolean_binding_values, year
        assert _evaluate_0224(snapshot, resolution) not in {_NORMAL_RESULT, _SIMPLIFICADA_RESULT}, year


def test_a_decided_absence_is_not_reported_as_a_missing_derived_value(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """An undeclared regime is not an engine gap, so no derived-binding advisory fires."""
    for year in _supported_years():
        snapshot = published_snapshot("100", filing_year=year, period=_PERIOD)
        resolution = _resolve(snapshot, authority_operation)

        assert not [item for item in resolution.diagnostics if item.reason == "unresolved_derived_binding"], year
