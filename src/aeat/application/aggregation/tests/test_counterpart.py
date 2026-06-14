"""Tests for the 347/349 counterpart aggregator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import Period
from ....core.aggregation import AggregationSourceKind
from ....core.external_constants import M347_THRESHOLD_EUR
from .._counterpart import (
    CounterpartAggregation,
    CounterpartObservation,
    CounterpartSourceKind,
    OperationKind347,
    OperationKind349,
    aggregate_counterpart_347,
    aggregate_counterpart_349,
    declarable_for_347,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_2025_Q1 = Period.from_year_and_code(2025, "1T")
_P_2025_ANNUAL = Period.from_year_and_code(2025, "0A")


def _obs(
    *,
    nif: str,
    op_kind: str,
    base: str,
    invoice_total: str | None = None,
    name: str = "",
    country: str = "ES",
    source_kind: CounterpartSourceKind = AggregationSourceKind.LEDGER_TRANSACTION,
    source_id: str = "tx-001",
    period: str = "2025",
    accrued: str = "2025-03-15",
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
    )


class TestObservationContract:
    def test_observation_rejects_bare_invoice_source_kind(self) -> None:
        from pydantic import ValidationError

        payload = {
            "source_kind": "invoice",
            "source_object_id": "tx-001",
            "counterparty_nif": "X1",
            "counterparty_name": "",
            "counterparty_country": "ES",
            "operation_kind": OperationKind347.DELIVERY.value,
            "operation_period": "2025",
            "taxable_base": "100",
            "invoice_total": "100",
            "accrued_on": "2025-03-15",
        }
        with pytest.raises(ValidationError, match="unsupported source_kind"):
            CounterpartObservation.model_validate(payload)

    def test_observation_rejects_lowercase_country(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="uppercase ISO-3166"):
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="100", country="es")


class TestAggregate347:
    def test_347_filters_to_347_operation_kinds(self) -> None:
        observations = (
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="5000", source_id="t1"),
            _obs(nif="X1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="999", source_id="t2"),
        )
        result = aggregate_counterpart_347(observations, period=_P_2025_ANNUAL)
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
        result = aggregate_counterpart_347(observations, period=_P_2025_ANNUAL)
        assert result.total_counterparties == 2
        x1_delivery = next(
            r
            for r in result.rollups
            if r.counterparty_nif == "X1" and r.operation_kind == OperationKind347.DELIVERY.value
        )
        assert x1_delivery.observations_count == 2
        assert x1_delivery.total_taxable_base == Decimal("5000")


class TestThreshold347:
    def test_threshold_is_canonical_3005_06(self) -> None:
        assert Decimal("3005.06") == M347_THRESHOLD_EUR

    def test_declarable_when_above_threshold(self) -> None:
        observations = (
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="5000", invoice_total="6050", source_id="t1"),
        )
        result = aggregate_counterpart_347(observations, period=_P_2025_ANNUAL)
        assert declarable_for_347(result, counterparty_nif="X1") is True

    def test_not_declarable_when_at_or_below_threshold(self) -> None:
        observations = (
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="2500", invoice_total="3000", source_id="t1"),
        )
        result = aggregate_counterpart_347(observations, period=_P_2025_ANNUAL)
        assert declarable_for_347(result, counterparty_nif="X1") is False

    def test_threshold_excludes_exactly_at_floor(self) -> None:
        observations = (
            _obs(nif="X1", op_kind=OperationKind347.DELIVERY.value, base="0", invoice_total="3005.06", source_id="t1"),
        )
        result = aggregate_counterpart_347(observations, period=_P_2025_ANNUAL)
        assert declarable_for_347(result, counterparty_nif="X1") is False


class TestAggregate349:
    def test_349_filters_to_intracomunitarias_kinds(self) -> None:
        observations = (
            _obs(nif="DE1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="10000", country="DE", source_id="t1"),
            _obs(nif="DE1", op_kind=OperationKind347.DELIVERY.value, base="5000", country="DE", source_id="t2"),
        )
        result = aggregate_counterpart_349(observations, period=_P_2025_Q1)
        assert result.modelo == "349"
        assert len(result.rollups) == 1
        assert result.rollups[0].operation_kind == OperationKind349.INTRA_DELIVERY.value

    def test_349_aggregates_per_country(self) -> None:
        observations = (
            _obs(nif="DE1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="10000", country="DE", source_id="t1"),
            _obs(nif="FR1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="5000", country="FR", source_id="t2"),
        )
        result = aggregate_counterpart_349(observations, period=_P_2025_Q1)
        de1 = next(r for r in result.rollups if r.counterparty_nif == "DE1")
        fr1 = next(r for r in result.rollups if r.counterparty_nif == "FR1")
        assert de1.counterparty_country == "DE"
        assert fr1.counterparty_country == "FR"


class TestInvariants:
    def test_unregistered_modelo_raises_domain_error(self) -> None:
        from .._counterpart import _MODELO_KIND_CATALOGUE
        from .._errors import AggregationUnsupportedModeloError
        from .._grouping import filter_observations_for_modelo

        with pytest.raises(AggregationUnsupportedModeloError) as exc_info:
            filter_observations_for_modelo(
                (),
                modelo="720",
                catalogue=_MODELO_KIND_CATALOGUE,
                attribute_fn=lambda obs: obs.operation_kind,
                aggregator_label="counterpart aggregator",
            )
        exc = exc_info.value
        assert exc.translated_message == "aggregation.grouping.errors.unsupported_modelo"
        assert exc.context is not None
        assert exc.context["modelo"] == "720"

    def test_totals_must_match_rollups(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="!= sum of rollups"):
            CounterpartAggregation(
                modelo="347",
                period=_P_2025_ANNUAL,
                rollups=(),
                total_counterparties=0,
                total_taxable_base=Decimal("999"),
                total_invoice_total=Decimal("0"),
            )

    def test_combined_period_string_is_not_coerced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Period"):
            CounterpartAggregation(
                modelo="347",
                period="2025",  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # negative test: intentionally invalid input
                rollups=(),
                total_counterparties=0,
                total_taxable_base=Decimal("0"),
                total_invoice_total=Decimal("0"),
            )

    def test_period_dict_is_not_coerced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Period"):
            CounterpartAggregation(
                modelo="347",
                period={"filing_year": 2025, "code": "0A"},  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # negative test: intentionally invalid input
                rollups=(),
                total_counterparties=0,
                total_taxable_base=Decimal("0"),
                total_invoice_total=Decimal("0"),
            )

    def test_input_order_invariance(self) -> None:
        observations = (
            _obs(nif="Z1", op_kind=OperationKind347.RENTAL.value, base="500", source_id="t1"),
            _obs(nif="A1", op_kind=OperationKind347.DELIVERY.value, base="800", source_id="t2"),
        )
        forward = aggregate_counterpart_347(observations, period=_P_2025_ANNUAL)
        reverse = aggregate_counterpart_347(tuple(reversed(observations)), period=_P_2025_ANNUAL)
        assert forward.model_dump_json() == reverse.model_dump_json()
