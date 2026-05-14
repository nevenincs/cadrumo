"""Tests for the 347/349 counterpart aggregator."""

from __future__ import annotations

from decimal import Decimal

import pytest

import aeat.application.aggregation as aggregation_api
from aeat.application.aggregation import (
    THRESHOLD_347_EUR,
    AggregationUnsupportedModeloError,
    CounterpartAggregation,
    CounterpartObservation,
    CounterpartRollup,
    OperationKind347,
    OperationKind349,
    aggregate_counterpart_347,
    aggregate_counterpart_349,
    declarable_counterparty_nifs_347,
    declarable_for_347,
)
from aeat.core.errors import get_registered_error_code

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _obs(
    *,
    nif: str,
    op_kind: str,
    base: str,
    invoice_total: str | None = None,
    name: str = "",
    country: str = "ES",
    source_kind: str = "ledger_transaction",
    source_id: str = "tx-001",
    period: str = "2025",
    accrued: str = "2025-03-15",
    groi_verified: bool = False,
    nif_iva_verified: bool = False,
) -> CounterpartObservation:
    return CounterpartObservation(
        source_kind=source_kind,
        source_object_id=source_id,
        counterparty_nif=nif,
        counterparty_name=name,
        counterparty_country=country,
        operation_kind=op_kind,
        operation_period=period,
        taxable_base=Decimal(base),
        invoice_total=Decimal(invoice_total) if invoice_total else Decimal(base),
        accrued_on=accrued,
        groi_verified=groi_verified,
        nif_iva_verified=nif_iva_verified,
    )


class TestObservationContract:
    def test_observation_rejects_bare_invoice_source_kind(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="unsupported source_kind"):
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="100", source_kind="invoice")

    def test_observation_rejects_unknown_source_kind(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="collectible_invoice"):
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="100", source_kind="business_operation")

    @pytest.mark.parametrize(
        "source_kind",
        [
            "ledger_transaction",
            "purchase_invoice_evidence",
            "payable_invoice",
            "collectible_invoice",
        ],
    )
    def test_observation_accepts_all_canonical_source_kinds(self, source_kind: str) -> None:
        observation = _obs(
            nif="X1",
            op_kind=OperationKind347.DELIVERY.value,
            base="100",
            source_kind=source_kind,
        )
        assert observation.source_kind == source_kind

    def test_observation_rejects_lowercase_country(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="uppercase ISO-3166"):
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="100", country="es")

    def test_observation_rejects_non_alpha_country(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="uppercase ISO-3166"):
            _obs(nif="X1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="100", country="1!")

    def test_observation_rejects_non_ascii_country_letters(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="uppercase ISO-3166"):
            _obs(nif="X1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="100", country="ÑÑ")

    def test_rollup_rejects_noncanonical_source_kind(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="unsupported source_kind"):
            CounterpartRollup(
                source_kind="invoice",
                counterparty_nif="X1",
                counterparty_country="ES",
                operation_kind=OperationKind347.DELIVERY.value,
                observations_count=1,
                total_taxable_base=Decimal("100"),
                total_invoice_total=Decimal("121"),
            )

    def test_counterpart_api_is_publicly_exported(self) -> None:
        assert "CounterpartRollup" in aggregation_api.__all__
        assert aggregation_api.CounterpartRollup is CounterpartRollup
        assert "declarable_counterparty_nifs_347" in aggregation_api.__all__


class TestAggregate347:
    def test_347_filters_to_347_operation_kinds(self) -> None:
        observations = (
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="5000", source_id="t1"),
            _obs(nif="X1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="999", source_id="t2"),
        )
        result = aggregate_counterpart_347(observations, period="2025")
        assert result.modelo == "347"
        assert len(result.rollups) == 1
        assert result.rollups[0].operation_kind == OperationKind347.DELIVERY.value

    def test_347_groups_by_nif_and_operation_kind(self) -> None:
        observations = (
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="2000", source_id="t1"),
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="3000", source_id="t2"),
            _obs(nif="X1", op_kind=OperationKind347.ACQUISITION.value, base="500", source_id="t3"),
            _obs(nif="X2", op_kind=OperationKind347.DELIVERY.value, base="1000", source_id="t4"),
        )
        result = aggregate_counterpart_347(observations, period="2025")
        assert result.total_counterparties == 2
        x1_delivery = next(
            r
            for r in result.rollups
            if r.counterparty_nif == "X1" and r.operation_kind == OperationKind347.DELIVERY.value
        )
        assert x1_delivery.observations_count == 2
        assert x1_delivery.total_taxable_base == Decimal("5000")

    def test_347_keeps_source_kind_cohorts_separate(self) -> None:
        observations = (
            _obs(
                nif="X1",
                op_kind=OperationKind347.DELIVERY.value,
                base="2000",
                source_kind="ledger_transaction",
                source_id="t1",
            ),
            _obs(
                nif="X1",
                op_kind=OperationKind347.DELIVERY.value,
                base="3000",
                source_kind="payable_invoice",
                source_id="p1",
            ),
            _obs(
                nif="X1",
                op_kind=OperationKind347.DELIVERY.value,
                base="4000",
                source_kind="collectible_invoice",
                source_id="c1",
            ),
        )
        result = aggregate_counterpart_347(observations, period="2025")
        assert result.total_counterparties == 1
        assert [rollup.source_kind for rollup in result.rollups] == [
            "collectible_invoice",
            "ledger_transaction",
            "payable_invoice",
        ]
        assert [rollup.total_taxable_base for rollup in result.rollups] == [
            Decimal("4000"),
            Decimal("2000"),
            Decimal("3000"),
        ]


class TestThreshold347:
    def test_threshold_is_canonical_3005_06(self) -> None:
        assert Decimal("3005.06") == THRESHOLD_347_EUR

    def test_declarable_when_above_threshold(self) -> None:
        observations = (
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="5000", invoice_total="6050", source_id="t1"),
        )
        result = aggregate_counterpart_347(observations, period="2025")
        assert declarable_for_347(result, counterparty_nif="X1") is True

    def test_not_declarable_when_at_or_below_threshold(self) -> None:
        observations = (
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="2500", invoice_total="3000", source_id="t1"),
        )
        result = aggregate_counterpart_347(observations, period="2025")
        assert declarable_for_347(result, counterparty_nif="X1") is False

    def test_threshold_excludes_exactly_at_floor(self) -> None:
        observations = (
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="0", invoice_total="3005.06", source_id="t1"),
        )
        result = aggregate_counterpart_347(observations, period="2025")
        assert declarable_for_347(result, counterparty_nif="X1") is False

    def test_threshold_sums_all_source_kind_and_operation_cohorts_per_counterparty(self) -> None:
        observations = (
            _obs(
                nif="X1",
                op_kind=OperationKind347.DELIVERY.value,
                base="1500",
                invoice_total="1500",
                source_kind="ledger_transaction",
                source_id="t1",
            ),
            _obs(
                nif="X1",
                op_kind=OperationKind347.ACQUISITION.value,
                base="1505.07",
                invoice_total="1505.07",
                source_kind="payable_invoice",
                source_id="p1",
            ),
            _obs(
                nif="X2",
                op_kind=OperationKind347.DELIVERY.value,
                base="3005.06",
                invoice_total="3005.06",
                source_kind="collectible_invoice",
                source_id="c1",
            ),
        )
        result = aggregate_counterpart_347(observations, period="2025")
        assert all(row.total_invoice_total <= THRESHOLD_347_EUR for row in result.rollups)
        assert declarable_counterparty_nifs_347(result) == frozenset({"X1"})
        assert declarable_for_347(result, counterparty_nif="X1") is True
        assert declarable_for_347(result, counterparty_nif="X2") is False


class TestAggregate349:
    def test_349_filters_to_intracomunitarias_kinds(self) -> None:
        observations = (
            _obs(nif="DE1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="10000", country="DE", source_id="t1"),
            _obs(nif="DE1", op_kind=OperationKind347.DELIVERY.value, base="5000", country="DE", source_id="t2"),
        )
        result = aggregate_counterpart_349(observations, period="2025-Q1")
        assert result.modelo == "349"
        assert len(result.rollups) == 1
        assert result.rollups[0].operation_kind == OperationKind349.INTRA_DELIVERY.value

    def test_349_aggregates_per_country(self) -> None:
        observations = (
            _obs(nif="DE1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="10000", country="DE", source_id="t1"),
            _obs(nif="FR1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="5000", country="FR", source_id="t2"),
        )
        result = aggregate_counterpart_349(observations, period="2025-Q1")
        de1 = next(r for r in result.rollups if r.counterparty_nif == "DE1")
        fr1 = next(r for r in result.rollups if r.counterparty_nif == "FR1")
        assert de1.counterparty_country == "DE"
        assert fr1.counterparty_country == "FR"

    def test_349_non_spanish_counterparty_requires_nif_iva_readiness(self) -> None:
        observations = (
            _obs(
                nif="DE1",
                op_kind=OperationKind349.INTRA_DELIVERY.value,
                base="10000",
                country="DE",
                source_id="t1",
                nif_iva_verified=False,
            ),
        )
        result = aggregate_counterpart_349(observations, period="2025-Q1")
        rollup = result.rollups[0]
        assert rollup.requires_nif_iva_check is True
        assert rollup.requires_groi_check is False
        assert rollup.nif_iva_ready is False
        assert rollup.declarable_readiness_satisfied is False

    def test_349_non_spanish_counterparty_ready_after_nif_iva_verification(self) -> None:
        observations = (
            _obs(
                nif="FR1",
                op_kind=OperationKind349.INTRA_SERVICE_OUT.value,
                base="10000",
                country="FR",
                source_id="t1",
                nif_iva_verified=True,
            ),
        )
        result = aggregate_counterpart_349(observations, period="2025-Q1")
        rollup = result.rollups[0]
        assert rollup.requires_nif_iva_check is True
        assert rollup.nif_iva_ready is True
        assert rollup.declarable_readiness_satisfied is True

    def test_349_spanish_counterparty_requires_groi_readiness(self) -> None:
        observations = (
            _obs(
                nif="A28015865",
                op_kind=OperationKind349.INTRA_DELIVERY.value,
                base="10000",
                country="ES",
                source_id="t1",
                groi_verified=False,
            ),
        )
        result = aggregate_counterpart_349(observations, period="2025-Q1")
        rollup = result.rollups[0]
        assert rollup.requires_groi_check is True
        assert rollup.requires_nif_iva_check is False
        assert rollup.groi_ready is False
        assert rollup.declarable_readiness_satisfied is False

    def test_349_spanish_counterparty_ready_after_groi_verification(self) -> None:
        observations = (
            _obs(
                nif="A28015865",
                op_kind=OperationKind349.INTRA_DELIVERY.value,
                base="10000",
                country="ES",
                source_id="t1",
                groi_verified=True,
            ),
        )
        result = aggregate_counterpart_349(observations, period="2025-Q1")
        rollup = result.rollups[0]
        assert rollup.requires_groi_check is True
        assert rollup.groi_ready is True
        assert rollup.declarable_readiness_satisfied is True

    def test_349_rejects_conflicting_country_for_same_counterparty_cohort(self) -> None:
        observations = (
            _obs(
                nif="X1",
                op_kind=OperationKind349.INTRA_DELIVERY.value,
                base="10000",
                country="ES",
                source_id="t1",
                groi_verified=True,
            ),
            _obs(
                nif="X1",
                op_kind=OperationKind349.INTRA_DELIVERY.value,
                base="5000",
                country="DE",
                source_id="t2",
                nif_iva_verified=True,
            ),
        )
        with pytest.raises(ValueError, match="conflicting counterparty_country"):
            aggregate_counterpart_349(observations, period="2025-Q1")


class TestInvariants:
    def test_unknown_modelo_uses_registered_aggregation_error(self) -> None:
        from aeat.application.aggregation._counterpart import _filter_observations_for_modelo

        with pytest.raises(AggregationUnsupportedModeloError, match="unsupported_modelo") as exc_info:
            _filter_observations_for_modelo((), modelo="720")
        assert exc_info.value.suggestion == "use one of 347, 349"
        assert get_registered_error_code(exc_info.value).code == "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO"

    def test_totals_must_match_rollups(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="!= sum of rollups"):
            CounterpartAggregation(
                modelo="347",
                period="2025",
                rollups=(),
                total_counterparties=0,
                total_taxable_base=Decimal("999"),
                total_invoice_total=Decimal("0"),
            )

    def test_input_order_invariance(self) -> None:
        observations = (
            _obs(nif="Z1", op_kind=OperationKind347.RENTAL.value, base="500", source_id="t1"),
            _obs(nif="A1", op_kind=OperationKind347.DELIVERY.value, base="800", source_id="t2"),
        )
        forward = aggregate_counterpart_347(observations, period="2025")
        reverse = aggregate_counterpart_347(tuple(reversed(observations)), period="2025")
        assert forward.model_dump_json() == reverse.model_dump_json()
