"""The Modelo 720 obligation block of an asset is read at the ejercicio's year end, never at the run date."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind, ForeignAssetClass
from ....core.period import Period
from ....core.time.clock import frozen_clock
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.schema_references import TemporalSupportEnvelope
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..foreign_assets import ForeignAssetClassRollup, ForeignAssetsAggregation, declarable_asset_classes_720

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _DateRecordingSource:
    """Delegate every governed-fact read to the pinned operation, keeping the date each one asked for."""

    def __init__(self, inner: PinnedAuthorityOperation) -> None:
        self._inner = inner
        self.asked: list[date] = []

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        self.asked.append(query.effective_date)
        return self._inner.resolve_governed_fact(query)

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        return self._inner.supported_filing_years()


def _account_aggregation(filing_year: int, valuation_eur: Decimal) -> ForeignAssetsAggregation:
    rollup = ForeignAssetClassRollup(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        asset_class=ForeignAssetClass.ACCOUNT,
        assets_count=1,
        held_at_year_end_count=1,
        total_valuation_eur=valuation_eur,
        countries=("AD",),
    )
    return ForeignAssetsAggregation(
        modelo="720",
        period=Period.from_year_and_code(filing_year, "0A"),
        rollups=(rollup,),
        total_assets=1,
        total_valuation_eur=valuation_eur,
    )


@pytest.mark.parametrize("filing_year", filing_year_envelope().years)
def test_the_obligation_block_is_read_at_the_ejercicio_year_end_whatever_the_run_date(
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> None:
    recorder = _DateRecordingSource(operation)
    aggregation = _account_aggregation(filing_year, Decimal("50000.01"))
    run_date_outside_the_envelope = datetime(filing_year_envelope().floor - 3, 6, 15, 12, tzinfo=UTC)

    with frozen_clock(run_date_outside_the_envelope), validating_governed_facts(recorder):
        declarable = declarable_asset_classes_720(aggregation, operation=operation)

    assert declarable == frozenset({ForeignAssetClass.ACCOUNT})
    assert recorder.asked
    assert set(recorder.asked) == {date(filing_year, 12, 31)}
