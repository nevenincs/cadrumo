"""Tests for the 347/349 counterpart aggregator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.period import Period
from ....core.external_constants import M347_THRESHOLD_EUR
from ....core.aggregation import BindingSourceKind
from .._counterpart import (
    COUNTERPART_MODELO_KIND_CATALOGUE,
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
    source_kind: CounterpartSourceKind = BindingSourceKind.LEDGER_TRANSACTION,
    source_id: str = "tx-001",
    period: str = "0A",
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
            "operation_period": "0A",
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

    def test_349_accepts_invoice_shaped_observation_sources(self) -> None:
        observations = (
            _obs(
                nif="DE1",
                op_kind=OperationKind349.INTRA_DELIVERY.value,
                base="1000.00",
                country="DE",
                source_kind=BindingSourceKind.COLLECTIBLE_INVOICE,
                source_id="sale-de",
            ),
            _obs(
                nif="IT1",
                op_kind=OperationKind349.INTRA_SERVICE_IN.value,
                base="3000.00",
                country="IT",
                source_kind=BindingSourceKind.PAYABLE_INVOICE,
                source_id="purchase-it",
            ),
        )

        result = aggregate_counterpart_349(observations, period=_P_2025_Q1)

        assert {rollup.source_kind for rollup in result.rollups} == {
            BindingSourceKind.COLLECTIBLE_INVOICE,
            BindingSourceKind.PAYABLE_INVOICE,
        }
        assert result.total_invoice_total == Decimal("4000.00")


class TestInvariants:
    def test_unregistered_modelo_raises_domain_error(self) -> None:
        from .._grouping import filter_observations_for_modelo
        from ..errors import AggregationUnsupportedModeloError

        with pytest.raises(AggregationUnsupportedModeloError) as exc_info:
            filter_observations_for_modelo(
                (),
                modelo="720",
                catalogue=COUNTERPART_MODELO_KIND_CATALOGUE,
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
            CounterpartAggregation.model_validate(
                {
                    "modelo": "347",
                    "period": "2025",
                    "rollups": (),
                    "total_counterparties": 0,
                    "total_taxable_base": Decimal("0"),
                    "total_invoice_total": Decimal("0"),
                },
            )

    def test_period_dict_is_not_coerced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Period"):
            CounterpartAggregation.model_validate(
                {
                    "modelo": "347",
                    "period": {"filing_year": 2025, "code": "0A"},
                    "rollups": (),
                    "total_counterparties": 0,
                    "total_taxable_base": Decimal("0"),
                    "total_invoice_total": Decimal("0"),
                },
            )

    def test_input_order_invariance(self) -> None:
        observations = (
            _obs(nif="Z1", op_kind=OperationKind347.RENTAL.value, base="500", source_id="t1"),
            _obs(nif="A1", op_kind=OperationKind347.DELIVERY.value, base="800", source_id="t2"),
        )
        forward = aggregate_counterpart_347(observations, period=_P_2025_ANNUAL)
        reverse = aggregate_counterpart_347(tuple(reversed(observations)), period=_P_2025_ANNUAL)
        assert forward.model_dump_json() == reverse.model_dump_json()


class TestObservationBoundaryAuthorities:
    """The operator boundary admits dates and periods through the shared authorities."""

    @pytest.mark.parametrize("impossible", ["2026-99-99", "2026-02-30", "2025-13-01"])
    def test_impossible_accrued_dates_are_refused(self, impossible: str) -> None:
        """An impossible calendar date never reaches a preview rollup.

        ``accrued_on`` was bounded by string length alone, so a ten-character
        non-date was admitted and produced a rollup exactly as a real date did —
        while the adjacent registry counterpart binding types the same concept
        as a real :class:`~datetime.date`.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _obs(nif="A1", op_kind=OperationKind347.DELIVERY.value, base="100", accrued=impossible)

    @pytest.mark.parametrize("malformed", ["20250315", "2025-3-15", "15-03-2025"])
    def test_non_extended_iso_accrued_dates_are_refused(self, malformed: str) -> None:
        """Only the extended ``YYYY-MM-DD`` wire form is admitted."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _obs(nif="A1", op_kind=OperationKind347.DELIVERY.value, base="100", accrued=malformed)

    @pytest.mark.parametrize(
        "unconstrained",
        [
            "2025",
            "bogus",
            "Q1",
            "ANUAL",
            "ALTA",
            "MODIFICACION",
            "BAJA",
            "COMUNICACION",
            "VARIACION",
            "EVENT-N",
        ],
    )
    def test_non_registry_operation_periods_are_refused(self, unconstrained: str) -> None:
        """``operation_period`` must be a FILING period token, not free text.

        The administrative censo tokens and the ``EVENT-N`` selector placeholder
        address a registry revision; an M347 counterpart operation period is a
        period the taxpayer operated in, so they are refused here even though the
        registry coordinate admits them.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _obs(nif="A1", op_kind=OperationKind347.DELIVERY.value, base="100", period=unconstrained)

    @pytest.mark.parametrize(
        "uncanonical",
        [
            "Entregas_Y_Prestaciones",
            "entregas y prestaciones",
            "entregas_y_prestacion",
            "A",
            "E",
            "delivery",
        ],
    )
    def test_uncanonical_operation_kinds_are_refused(self, uncanonical: str) -> None:
        """An ``operation_kind`` outside the 347/349 clave vocabulary is refused here.

        Admitted, such a token did not merely mis-group — it made the operation
        *vanish*. The aggregator routes each observation by testing this field
        against the requested modelo's clave set, so a token in neither set
        matches neither pass and is dropped, while the aggregation's totals
        still reconcile because they are summed from the surviving rollups.
        Before this refusal, the observation below aggregated to
        ``total_counterparties == 0`` and ``total_taxable_base == 0`` with no
        error and no notice, silently under-declaring a real above-threshold
        operation on an informativa a human files.
        """
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            _obs(nif="A1", op_kind=uncanonical, base="10000")

    def test_a_349_clave_still_routes_past_the_347_pass(self) -> None:
        """Cross-modelo filtering is correct and is deliberately left intact.

        The refusal above targets a token belonging to *neither* vocabulary. A
        canonical 349 clave handed to the 347 pass must still be skipped rather
        than refused, so the boundary check must not collapse the two cases.
        """
        observation = _obs(nif="A1", op_kind=OperationKind349.INTRA_DELIVERY.value, base="10000")

        aggregation = aggregate_counterpart_347((observation,), period=_P_2025_ANNUAL)
        assert aggregation.total_counterparties == 0

    def test_canonical_observation_is_admitted_and_aggregates(self) -> None:
        """The positive control: canonical values are admitted and produce a rollup.

        Without this, every refusal above would also hold for a validator that
        refused every value.
        """
        observation = _obs(
            nif="A1",
            op_kind=OperationKind347.DELIVERY.value,
            base="100",
            period="0A",
            accrued="2025-03-15",
        )
        assert observation.operation_period == "0A"
        assert observation.accrued_on == "2025-03-15"

        aggregation = aggregate_counterpart_347((observation,), period=_P_2025_ANNUAL)
        assert aggregation.total_counterparties == 1
