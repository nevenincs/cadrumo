"""Tests for the Modelo 720 foreign-assets aggregator."""

from __future__ import annotations

from decimal import Decimal

import pytest

import aeat.application.aggregation as aggregation_api
from aeat.application.aggregation import (
    THRESHOLD_720_EUR_PER_CLASS,
    ForeignAssetClass,
    ForeignAssetClassRollup,
    ForeignAssetObservation,
    ForeignAssetsAggregation,
    aggregate_foreign_assets_720,
    declarable_asset_classes_720,
    declarable_class,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _obs(
    *,
    asset_class: ForeignAssetClass,
    valuation: str,
    asset_external_id: str = "ASSET-001",
    country: str = "AD",
    source_kind: str = "ledger_transaction",
    source_id: str = "tx-001",
    held: bool = True,
    acquisition: str = "2023-01-15",
) -> ForeignAssetObservation:
    return ForeignAssetObservation(
        source_kind=source_kind,
        source_object_id=source_id,
        asset_class=asset_class,
        asset_external_id=asset_external_id,
        country=country,
        valuation_eur=Decimal(valuation),
        acquisition_date=acquisition,
        held_at_year_end=held,
    )


class TestObservationContract:
    def test_bare_invoice_source_kind_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="unsupported source_kind"):
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", source_kind="invoice")

    def test_noncanonical_source_kind_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="collectible_invoice"):
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", source_kind="foreign_account_statement")

    @pytest.mark.parametrize(
        "source_kind",
        [
            "ledger_transaction",
            "purchase_invoice_evidence",
            "payable_invoice",
            "collectible_invoice",
        ],
    )
    def test_canonical_source_kinds_are_accepted(self, source_kind: str) -> None:
        observation = _obs(
            asset_class=ForeignAssetClass.ACCOUNT,
            valuation="1000",
            source_kind=source_kind,
        )
        assert observation.source_kind == source_kind

    def test_lowercase_country_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="uppercase ISO-3166"):
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", country="ad")

    def test_non_alpha_country_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="uppercase ISO-3166"):
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", country="1!")

    def test_non_ascii_country_letters_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="uppercase ISO-3166"):
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="1000", country="ÑÑ")

    def test_foreign_asset_api_is_publicly_exported(self) -> None:
        assert "ForeignAssetObservation" in aggregation_api.__all__
        assert aggregation_api.ForeignAssetObservation is ForeignAssetObservation
        assert "aggregate_foreign_assets_720" in aggregation_api.__all__


class TestAggregateBasic:
    def test_empty_observations_produce_zero_totals(self) -> None:
        result = aggregate_foreign_assets_720((), period="2025")
        assert result.modelo == "720"
        assert result.rollups == ()
        assert result.total_assets == 0
        assert result.total_valuation_eur == Decimal("0")

    def test_single_observation_creates_one_rollup(self) -> None:
        obs = _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="12345.67", country="AD")
        result = aggregate_foreign_assets_720((obs,), period="2025")
        assert len(result.rollups) == 1
        row = result.rollups[0]
        assert row.asset_class is ForeignAssetClass.ACCOUNT
        assert row.assets_count == 1
        assert row.held_at_year_end_count == 1
        assert row.total_valuation_eur == Decimal("12345.67")
        assert row.countries == ("AD",)

    def test_multiple_classes_yield_separate_rollups(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="10000", asset_external_id="A1"),
            _obs(asset_class=ForeignAssetClass.SECURITY, valuation="20000", asset_external_id="S1"),
            _obs(asset_class=ForeignAssetClass.REAL_ESTATE, valuation="30000", asset_external_id="R1"),
        )
        result = aggregate_foreign_assets_720(observations, period="2025")
        assert len(result.rollups) == 3
        classes = {row.asset_class for row in result.rollups}
        assert classes == {
            ForeignAssetClass.ACCOUNT,
            ForeignAssetClass.SECURITY,
            ForeignAssetClass.REAL_ESTATE,
        }
        assert result.total_assets == 3
        assert result.total_valuation_eur == Decimal("60000")

    def test_multiple_assets_same_class_sum(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="20000", asset_external_id="A1", country="AD"),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="30000", asset_external_id="A2", country="CH"),
        )
        result = aggregate_foreign_assets_720(observations, period="2025")
        assert len(result.rollups) == 1
        row = result.rollups[0]
        assert row.assets_count == 2
        assert row.source_kind == "ledger_transaction"
        assert row.total_valuation_eur == Decimal("50000")
        assert row.countries == ("AD", "CH")

    def test_same_asset_class_different_source_kinds_yield_separate_rollups(self) -> None:
        observations = (
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="20000",
                asset_external_id="A1",
                source_kind="purchase_invoice_evidence",
            ),
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="30000",
                asset_external_id="A2",
                source_kind="payable_invoice",
            ),
        )
        result = aggregate_foreign_assets_720(observations, period="2025")
        assert [(row.source_kind, row.asset_class, row.total_valuation_eur) for row in result.rollups] == [
            ("payable_invoice", ForeignAssetClass.ACCOUNT, Decimal("30000")),
            ("purchase_invoice_evidence", ForeignAssetClass.ACCOUNT, Decimal("20000")),
        ]

    def test_rollups_sort_by_asset_class_value(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.VIRTUAL_CURRENCY, valuation="1000", asset_external_id="V1"),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="2000", asset_external_id="A1"),
            _obs(asset_class=ForeignAssetClass.SECURITY, valuation="3000", asset_external_id="S1"),
        )
        result = aggregate_foreign_assets_720(observations, period="2025")
        values = [row.asset_class.value for row in result.rollups]
        assert values == sorted(values)

    def test_held_count_tracks_year_end_flag(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="10000", asset_external_id="A1", held=True),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="10000", asset_external_id="A2", held=False),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="10000", asset_external_id="A3", held=True),
        )
        result = aggregate_foreign_assets_720(observations, period="2025")
        row = result.rollups[0]
        assert row.assets_count == 3
        assert row.held_at_year_end_count == 2


class TestThreshold720:
    def test_threshold_is_canonical_50000(self) -> None:
        assert Decimal("50000.00") == THRESHOLD_720_EUR_PER_CLASS

    def test_declarable_strict_above_50000(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="50000.01", asset_external_id="A1"),
        )
        result = aggregate_foreign_assets_720(observations, period="2025")
        assert declarable_class(result, asset_class=ForeignAssetClass.ACCOUNT) is True

    def test_not_declarable_at_exactly_50000(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="50000.00", asset_external_id="A1"),
        )
        result = aggregate_foreign_assets_720(observations, period="2025")
        assert declarable_class(result, asset_class=ForeignAssetClass.ACCOUNT) is False

    def test_not_declarable_below_threshold(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="49999.99", asset_external_id="A1"),
        )
        result = aggregate_foreign_assets_720(observations, period="2025")
        assert declarable_class(result, asset_class=ForeignAssetClass.ACCOUNT) is False

    def test_threshold_sums_all_source_kind_cohorts_per_asset_class(self) -> None:
        observations = (
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="25000",
                asset_external_id="A1",
                source_kind="purchase_invoice_evidence",
            ),
            _obs(
                asset_class=ForeignAssetClass.ACCOUNT,
                valuation="25000.01",
                asset_external_id="A2",
                source_kind="payable_invoice",
            ),
            _obs(
                asset_class=ForeignAssetClass.SECURITY,
                valuation="50000.00",
                asset_external_id="S1",
                source_kind="collectible_invoice",
            ),
        )
        result = aggregate_foreign_assets_720(observations, period="2025")
        assert all(row.total_valuation_eur <= THRESHOLD_720_EUR_PER_CLASS for row in result.rollups)
        assert declarable_asset_classes_720(result) == frozenset({ForeignAssetClass.ACCOUNT})
        assert declarable_class(result, asset_class=ForeignAssetClass.ACCOUNT) is True
        assert declarable_class(result, asset_class=ForeignAssetClass.SECURITY) is False


class TestInvariants:
    def test_aggregation_input_order_invariance(self) -> None:
        observations = (
            _obs(asset_class=ForeignAssetClass.SECURITY, valuation="5000", asset_external_id="S1"),
            _obs(asset_class=ForeignAssetClass.ACCOUNT, valuation="3000", asset_external_id="A1"),
        )
        forward = aggregate_foreign_assets_720(observations, period="2025")
        reverse = aggregate_foreign_assets_720(tuple(reversed(observations)), period="2025")
        assert forward.model_dump_json() == reverse.model_dump_json()

    def test_rollup_held_count_cannot_exceed_total(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="held_at_year_end_count"):
            ForeignAssetClassRollup(
                source_kind="ledger_transaction",
                asset_class=ForeignAssetClass.ACCOUNT,
                assets_count=2,
                held_at_year_end_count=99,
                total_valuation_eur=Decimal("10000"),
                countries=("AD",),
            )

    def test_rollup_rejects_invalid_public_country_tuple_values(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="uppercase ISO-3166"):
            ForeignAssetClassRollup(
                source_kind="ledger_transaction",
                asset_class=ForeignAssetClass.ACCOUNT,
                assets_count=1,
                held_at_year_end_count=1,
                total_valuation_eur=Decimal("10000"),
                countries=("ad", "1!", "ÑÑ"),
            )

    def test_aggregation_rejects_duplicate_class_rows(self) -> None:
        from pydantic import ValidationError

        row = ForeignAssetClassRollup(
            source_kind="ledger_transaction",
            asset_class=ForeignAssetClass.ACCOUNT,
            assets_count=1,
            held_at_year_end_count=1,
            total_valuation_eur=Decimal("1000"),
            countries=("AD",),
        )
        with pytest.raises(ValidationError, match="cohort may appear at most once"):
            ForeignAssetsAggregation(
                modelo="720",
                period="2025",
                rollups=(row, row),
                total_assets=2,
                total_valuation_eur=Decimal("2000"),
            )
