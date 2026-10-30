"""A year before the registry's floor leaves the minimum unresolved rather than understating it.

Figures use 2,000.00 at the published information-equipment minimum.  The registry's
floor is 2022, so an element in service from 2020 has two years no edition covers.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.application.actividad_asset.activity_asset_read_models import ActivityAssetClaimState
from cadrumo.application.actividad_asset.disposal_calculation import project_disposal_calculation
from cadrumo.application.actividad_asset.operations import ActivityAssetOperations
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.renta.actividad_asset.disposal import (
    ActivityAssetDisposal,
    ActivityAssetDisposalFindingKind,
    ActivityAssetDisposalReason,
)
from cadrumo.domain.renta.actividad_asset.election import DirectEstimationRegime
from cadrumo.domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from cadrumo.domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge

from .ledger_support import MemoryLedger
from .register_support import MemoryRepository, memory_register_authority
from .test_register import _ACQUISITION, _NAME, _forecast, _full_year, _operations, _revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ASSET = "laptop-1"
_SALE = ActivityAssetDisposal(
    disposal_date=date(2023, 12, 31),
    reason=ActivityAssetDisposalReason.SALE,
    proceeds=Decimal("100.00"),
    transmission_costs=Decimal("0.00"),
)


def _pre_floor() -> ActivityAssetOperations:
    operations, _ = _operations(today=date(2024, 6, 30))
    operations.create(_revision(in_service=date(2020, 1, 1)), _NAME)
    return operations


def test_a_year_no_edition_covers_leaves_the_minimum_unresolved_without_blocking() -> None:
    operations = _pre_floor()

    _, calculation = operations.disposal_calculation(_ASSET, _SALE)

    assert calculation.minimum is None
    assert [year.minimum_through for year in calculation.years] == [None, None, None, None]
    unresolved = [
        finding.tax_year
        for finding in calculation.findings
        if finding.kind is ActivityAssetDisposalFindingKind.MINIMUM_UNRESOLVED
    ]
    assert unresolved == [2020, 2021]
    assert not any(
        finding.kind is ActivityAssetDisposalFindingKind.NO_MINIMUM_AUTHORITY for finding in calculation.findings
    )
    # The known years still reduce cost, so the result stays a figure.
    assert calculation.result is not None
    assert calculation.reduction > Decimal("0")


def test_the_public_view_carries_the_unresolved_minimum_as_null_with_its_word() -> None:
    operations = _pre_floor()

    disposal, calculation = operations.disposal_calculation(_ASSET, _SALE)
    view = project_disposal_calculation(disposal, calculation)

    assert view.minimum is None
    assert view.years[-1].minimum_through is None
    assert "ledger.actividad_asset.disposal_finding.minimum_unresolved" in {
        finding.label_key for finding in view.findings
    }


def test_a_covered_element_keeps_a_stated_minimum() -> None:
    operations, _ = _operations(today=date(2026, 6, 30))
    operations.create(_revision(in_service=date(2025, 1, 1)), _NAME)
    sale = _SALE.model_copy(update={"disposal_date": date(2025, 12, 31)})

    _, calculation = operations.disposal_calculation(_ASSET, sale)

    assert calculation.minimum is not None
    assert calculation.years[-1].minimum_through == calculation.minimum


def _forecast_from_the_floor(
    revision: ActivityAssetRevision,
    *,
    covered_from: date,
    covered_until: date,
    history: AssetScheduleHistory,
    requested_free_amount: Decimal | None = None,
) -> ScheduledAmortizationCharge:
    if covered_from.year < 2022:
        raise RegistryError("no edition covers this year")
    return _forecast(
        revision,
        covered_from=covered_from,
        covered_until=covered_until,
        history=history,
        requested_free_amount=requested_free_amount,
    )


def test_a_year_no_edition_covers_is_distinct_from_a_missing_claim_in_the_plan() -> None:
    operations = ActivityAssetOperations(
        repository=MemoryRepository(),
        ledger=MemoryLedger(_ACQUISITION),
        forecast_operation=_forecast_from_the_floor,
        taxpayer_modality=lambda: DirectEstimationRegime.SIMPLIFIED,
        register_authority=memory_register_authority(today=date(2024, 6, 30)),
    )
    operations.create(_revision(in_service=date(2020, 1, 1)), _NAME)

    rows = {row.tax_year: row for row in operations.plan(_ASSET)}

    assert rows[2020].claim_state is ActivityAssetClaimState.EDITION_UNAVAILABLE
    assert rows[2021].claim_state is ActivityAssetClaimState.EDITION_UNAVAILABLE
    assert rows[2022].claim_state is ActivityAssetClaimState.MISSING
    assert rows[2020].minimum_complete is False
    assert rows[2022].minimum_complete is False
    # 2022, 2023 and 2024 can be claimed; 2020 and 2021 have no edition to claim under.
    assert operations.list_elements()[0].findings.missing == 3


def test_an_uncovered_opening_year_is_a_gap_and_a_covered_one_is_not() -> None:
    operations, _ = _operations(today=date(2027, 6, 30))
    base = _revision(in_service=date(2025, 1, 1))
    facts = {name: getattr(base, name) for name in type(base).model_fields}
    facts["opening_history"] = base.opening_history.model_copy(
        update={"accumulated_amount": Decimal("520.00"), "covered_through_tax_year": 2025},
    )
    operations.create(type(base)(**facts), _NAME)
    sale = _SALE.model_copy(update={"disposal_date": date(2027, 3, 31)})

    _, calculation = operations.disposal_calculation(_ASSET, sale)

    gaps = [f.tax_year for f in calculation.findings if f.kind is ActivityAssetDisposalFindingKind.CLAIM_GAP]
    assert gaps == [2026, 2027]
    assert _full_year(operations, 2026).amount == Decimal("520.00")
