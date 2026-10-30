"""A taxpayer with incomplete asset data gets findings, through the real Modelo 100 and 130 resolvers.

Figures are hand-worked from the 12,000.00 mobiliario element at a 10% linear coefficient.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposal,
    ActivityAssetDisposalReason,
    PriorFreeDepreciationRegime,
)
from cadrumo.domain.renta.actividad_asset.lifecycle import (
    ActivityAssetRevision,
    OpeningAmortizationHistory,
    OpeningHistoryStatus,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact

from ...actividad_asset.history import ActivityAssetHistory
from ...modelo.calculation_notes import GATE_REFUSED_REASONS
from ...modelo.work_profile import ModeloWorkProfile
from .. import modelo_bindings_actividad_assets
from ..source_mesh import CalculationSourceResolution
from .test_modelo_source_mesh_ledger import (
    _BUCKET_ID,
    _create_profile_record_for_test,
    _m130_box,
    _profile_creation_context_for_test,
    _reasons,
    _register_claim,
    register_asset,
    resolve_m100,
    resolve_m130,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_TRANSACTION = "c" * 64


def _blocks(resolution: CalculationSourceResolution) -> set[str]:
    return set(_reasons(resolution)) & GATE_REFUSED_REASONS


def _opening_unknown(asset: ActivityAssetRevision) -> ActivityAssetRevision:
    return asset.model_copy(update={"opening_history": OpeningAmortizationHistory(status=OpeningHistoryStatus.MISSING)})


def _disposed_with_unknown_opening(
    reason: ActivityAssetDisposalReason,
    *,
    regime: PriorFreeDepreciationRegime | None = None,
) -> ActivityAssetHistory:
    asset = _opening_unknown(register_asset("furniture", transaction_id=_TRANSACTION))
    proceeds = Decimal("0.00") if reason is ActivityAssetDisposalReason.WITHDRAWAL else Decimal("5000.00")
    baja = ActivityAssetDisposal(
        disposal_date=date(2025, 6, 30),
        reason=reason,
        proceeds=proceeds,
        transmission_costs=Decimal("0.00"),
        prior_free_depreciation_regime=regime,
    )
    return ActivityAssetHistory(revisions=(asset, asset.with_disposal(baja)))


def _profile(operation, *facts: UserProfileFact) -> ModeloWorkProfile:
    return ModeloWorkProfile(
        record=_create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(UserProfileFact(path="identity.tax_id", value="X1234567L"), *facts),
            context=_profile_creation_context_for_test(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )


@pytest.mark.parametrize("period", ["1T", "2T", "4T"])
def test_a_withdrawal_with_an_unknown_opening_stops_nothing(period: str) -> None:
    history = _disposed_with_unknown_opening(ActivityAssetDisposalReason.WITHDRAWAL)

    assert _blocks(resolve_m100(history)) == set()
    assert "activity_asset_disposal_finding" not in _reasons(resolve_m100(history))
    assert _blocks(resolve_m130(history, period)) == set()


def test_a_sale_with_an_unknown_opening_is_an_unresolved_finding_in_the_annual_return() -> None:
    resolution = resolve_m100(_disposed_with_unknown_opening(ActivityAssetDisposalReason.SALE))

    assert _blocks(resolution) == set()
    (finding,) = (item for item in resolution.diagnostics if item.reason == "activity_asset_disposal_finding")
    assert "could not be worked out" in finding.message


def test_a_sale_with_an_unknown_opening_says_nothing_to_the_instalment() -> None:
    assert _blocks(resolve_m130(_disposed_with_unknown_opening(ActivityAssetDisposalReason.SALE), "2T")) == set()


def test_a_possible_excess_with_an_unknown_opening_is_a_finding_in_the_instalment() -> None:
    history = _disposed_with_unknown_opening(
        ActivityAssetDisposalReason.SALE,
        regime=PriorFreeDepreciationRegime.TRLIS_DT_37,
    )

    resolution = resolve_m130(history, "2T")

    assert _blocks(resolution) == set()
    assert any(
        item.reason == "activity_asset_disposal_finding" and "excess" in item.message for item in resolution.diagnostics
    )


def test_a_possible_excess_with_an_unknown_opening_still_stops_the_annual_return() -> None:
    history = _disposed_with_unknown_opening(
        ActivityAssetDisposalReason.SALE,
        regime=PriorFreeDepreciationRegime.TRLIS_DT_37,
    )

    resolution = resolve_m100(history)

    assert _blocks(resolution) == {"unrouted_observation"}


def test_a_registry_failure_behind_a_baja_is_an_unresolved_finding(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_bounds(_operation):
        def read(_revision, _tax_year):
            raise RegistryValidationError("the parameter row is unreadable")

        return read

    monkeypatch.setattr(modelo_bindings_actividad_assets, "pinned_disposal_bounds", failing_bounds)
    asset = register_asset("furniture", transaction_id=_TRANSACTION)
    baja = ActivityAssetDisposal(
        disposal_date=date(2025, 6, 30),
        reason=ActivityAssetDisposalReason.SALE,
        proceeds=Decimal("5000.00"),
        transmission_costs=Decimal("0.00"),
    )

    resolution = resolve_m100(ActivityAssetHistory(revisions=(asset, asset.with_disposal(baja))))

    assert _blocks(resolution) == set()
    assert "activity_asset_disposal_finding" in _reasons(resolution)


def _moved_to_navarra_in_2026(operation) -> ModeloWorkProfile:
    return _profile(
        operation,
        UserProfileFact(path="tax_residence.ccaa", value="madrid", valid_to=date(2025, 12, 31)),
        UserProfileFact(path="tax_residence.ccaa", value="navarra", valid_from=date(2026, 1, 1)),
    )


def test_a_move_to_foral_territory_in_2026_leaves_the_2025_returns_alone(operation) -> None:
    asset = register_asset("furniture", transaction_id=_TRANSACTION)
    claim = _register_claim(asset, amount=Decimal("1200.00"))
    history = ActivityAssetHistory(revisions=(asset,), claims=(claim,))
    profile = _moved_to_navarra_in_2026(operation)

    annual = resolve_m100(history, profile=profile)
    fourth_quarter = resolve_m130(history, "4T", profile=profile)

    assert Decimal("1200.00") in annual.binding_values.values()
    assert _blocks(annual) == set()
    assert _m130_box(fourth_quarter) == Decimal("1200.00")
    assert _blocks(fourth_quarter) == set()


def test_the_foral_refusal_holds_for_the_period_truly_in_foral_territory(operation) -> None:
    history = ActivityAssetHistory(revisions=(register_asset("furniture", transaction_id=_TRANSACTION),))

    profile = _profile(
        operation,
        UserProfileFact(path="tax_residence.ccaa", value="madrid", valid_to=date(2025, 6, 30)),
        UserProfileFact(path="tax_residence.ccaa", value="navarra", valid_from=date(2025, 7, 1)),
    )

    assert _reasons(resolve_m100(history, profile=profile)) == ["activity_asset_foral_territory"]
    assert _reasons(resolve_m130(history, "3T", profile=profile)) == ["activity_asset_foral_territory"]
    # 12,000 x 10% x 90 / 365 = 295.89, in the quarter still in common territory.
    assert _m130_box(resolve_m130(history, "1T", profile=profile)) == Decimal("295.89")


def test_a_residence_recorded_only_for_later_periods_is_a_finding_and_the_register_still_counts(operation) -> None:
    asset = register_asset("furniture", transaction_id=_TRANSACTION)
    profile = _profile(
        operation, UserProfileFact(path="tax_residence.ccaa", value="navarra", valid_from=date(2026, 1, 1))
    )

    resolution = resolve_m130(ActivityAssetHistory(revisions=(asset,)), "4T", profile=profile)

    assert _blocks(resolution) == set()
    assert "activity_asset_residence_period_unknown" in _reasons(resolution)
    assert _m130_box(resolution) == Decimal("1200.00")
