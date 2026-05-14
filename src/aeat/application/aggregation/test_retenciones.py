"""Tests for the Modelo 111 retenciones aggregator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from aeat.application.aggregation._retenciones import (
    RetencionesAggregation,
    RetencionObservation,
    RetencionScheme,
    aggregate_retenciones_111,
    aggregate_retenciones_115,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _obs(
    *,
    nif: str,
    scheme: RetencionScheme,
    base: str,
    retencion: str,
    name: str = "",
    source_kind: str = "ledger_transaction",
    source_id: str = "tx-001",
    accrued: str = "2025-03-15",
) -> RetencionObservation:
    return RetencionObservation(
        source_kind=source_kind,
        source_object_id=source_id,
        perceptor_nif=nif,
        perceptor_name=name,
        scheme=scheme,
        taxable_base=Decimal(base),
        retencion_amount=Decimal(retencion),
        accrued_on=accrued,
    )


class TestObservationContract:
    def test_observation_rejects_bare_invoice_source_kind(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="bare 'invoice'"):
            RetencionObservation(
                source_kind="invoice",
                source_object_id="x",
                perceptor_nif="A1",
                scheme=RetencionScheme.WORK_INCOME,
                taxable_base=Decimal("0"),
                retencion_amount=Decimal("0"),
                accrued_on="2025-01-01",
            )

    def test_observation_accepts_canonical_source_kinds(self) -> None:
        for kind in ("ledger_transaction", "purchase_invoice_evidence", "payable_invoice", "collectible_invoice"):
            obs = _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="0", retencion="0", source_kind=kind)
            assert obs.source_kind == kind


class TestAggregate111:
    def test_empty_observations_produces_zero_totals(self) -> None:
        result = aggregate_retenciones_111((), period="2025-Q1")
        assert result.modelo == "111"
        assert result.period == "2025-Q1"
        assert result.rollups == ()
        assert result.total_perceptors == 0
        assert result.total_taxable_base == Decimal("0")
        assert result.total_retencion == Decimal("0")

    def test_single_observation_creates_one_rollup(self) -> None:
        obs = _obs(
            nif="B12345678",
            name="Acme S.L.",
            scheme=RetencionScheme.ECONOMIC_ACTIVITY,
            base="1000.00",
            retencion="150.00",
        )
        result = aggregate_retenciones_111((obs,), period="2025-Q1")
        assert len(result.rollups) == 1
        row = result.rollups[0]
        assert row.perceptor_nif == "B12345678"
        assert row.perceptor_name == "Acme S.L."
        assert row.scheme is RetencionScheme.ECONOMIC_ACTIVITY
        assert row.observations_count == 1
        assert row.total_taxable_base == Decimal("1000.00")
        assert row.total_retencion == Decimal("150.00")
        assert result.total_perceptors == 1

    def test_multiple_observations_same_perceptor_and_scheme_sum(self) -> None:
        obs_a = _obs(
            nif="B1", scheme=RetencionScheme.WORK_INCOME, base="500.00", retencion="75.00",
            source_id="tx-1",
        )
        obs_b = _obs(
            nif="B1", scheme=RetencionScheme.WORK_INCOME, base="700.00", retencion="105.00",
            source_id="tx-2",
        )
        result = aggregate_retenciones_111((obs_a, obs_b), period="2025-Q1")
        assert len(result.rollups) == 1
        assert result.rollups[0].observations_count == 2
        assert result.rollups[0].total_taxable_base == Decimal("1200.00")
        assert result.rollups[0].total_retencion == Decimal("180.00")

    def test_same_perceptor_different_schemes_yield_separate_rollups(self) -> None:
        obs_work = _obs(
            nif="B1", scheme=RetencionScheme.WORK_INCOME, base="500.00", retencion="75.00",
            source_id="tx-1",
        )
        obs_econ = _obs(
            nif="B1", scheme=RetencionScheme.ECONOMIC_ACTIVITY, base="700.00", retencion="105.00",
            source_id="tx-2",
        )
        result = aggregate_retenciones_111((obs_work, obs_econ), period="2025-Q1")
        assert len(result.rollups) == 2
        schemes = {row.scheme for row in result.rollups}
        assert schemes == {RetencionScheme.WORK_INCOME, RetencionScheme.ECONOMIC_ACTIVITY}
        # Same perceptor counted once
        assert result.total_perceptors == 1

    def test_distinct_perceptors_count_separately(self) -> None:
        observations = (
            _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="100", retencion="15", source_id="t1"),
            _obs(nif="A2", scheme=RetencionScheme.WORK_INCOME, base="200", retencion="30", source_id="t2"),
            _obs(nif="A3", scheme=RetencionScheme.WORK_INCOME, base="300", retencion="45", source_id="t3"),
        )
        result = aggregate_retenciones_111(observations, period="2025-Q1")
        assert result.total_perceptors == 3
        assert result.total_taxable_base == Decimal("600")
        assert result.total_retencion == Decimal("90")

    def test_rollups_sort_deterministically_by_perceptor_then_scheme(self) -> None:
        observations = (
            _obs(nif="Z1", scheme=RetencionScheme.WORK_INCOME, base="100", retencion="15", source_id="t1"),
            _obs(nif="A1", scheme=RetencionScheme.ECONOMIC_ACTIVITY, base="200", retencion="30", source_id="t2"),
            _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="300", retencion="45", source_id="t3"),
        )
        result = aggregate_retenciones_111(observations, period="2025-Q1")
        keys = [(row.perceptor_nif, row.scheme.value) for row in result.rollups]
        assert keys == sorted(keys)

    def test_aggregation_is_input_order_invariant(self) -> None:
        observations = (
            _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="100", retencion="15", source_id="t1"),
            _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="200", retencion="30", source_id="t2"),
        )
        forward = aggregate_retenciones_111(observations, period="2025-Q1")
        reverse = aggregate_retenciones_111(tuple(reversed(observations)), period="2025-Q1")
        assert forward.model_dump_json() == reverse.model_dump_json()

    def test_unimplemented_modelo_raises(self) -> None:
        from aeat.application.aggregation._retenciones import _filter_observations_for_modelo

        with pytest.raises(NotImplementedError, match="modelo '123'"):
            _filter_observations_for_modelo((), modelo="123")


class TestAggregate115:
    def test_115_filters_to_urban_rental_only(self) -> None:
        observations = (
            _obs(nif="L1", scheme=RetencionScheme.URBAN_RENTAL, base="800", retencion="152", source_id="r1"),
            _obs(nif="L1", scheme=RetencionScheme.WORK_INCOME, base="100", retencion="15", source_id="r2"),
        )
        result = aggregate_retenciones_115(observations, period="2025-Q1")
        assert result.modelo == "115"
        assert len(result.rollups) == 1
        row = result.rollups[0]
        assert row.scheme is RetencionScheme.URBAN_RENTAL
        assert row.total_taxable_base == Decimal("800")
        assert row.total_retencion == Decimal("152")

    def test_115_sums_per_landlord_nif(self) -> None:
        observations = (
            _obs(nif="L1", scheme=RetencionScheme.URBAN_RENTAL, base="500", retencion="95", source_id="r1"),
            _obs(nif="L1", scheme=RetencionScheme.URBAN_RENTAL, base="500", retencion="95", source_id="r2"),
            _obs(nif="L2", scheme=RetencionScheme.URBAN_RENTAL, base="700", retencion="133", source_id="r3"),
        )
        result = aggregate_retenciones_115(observations, period="2025-Q1")
        assert result.total_perceptors == 2
        l1 = next(row for row in result.rollups if row.perceptor_nif == "L1")
        assert l1.observations_count == 2
        assert l1.total_taxable_base == Decimal("1000")
        assert l1.total_retencion == Decimal("190")

    def test_115_empty_input_returns_zero_totals(self) -> None:
        result = aggregate_retenciones_115((), period="2025-Q1")
        assert result.modelo == "115"
        assert result.rollups == ()
        assert result.total_perceptors == 0


class TestAggregationInvariants:
    def test_totals_must_match_rollups(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="does not match"):
            RetencionesAggregation(
                modelo="111",
                period="2025-Q1",
                rollups=(),
                total_perceptors=0,
                total_taxable_base=Decimal("999"),
                total_retencion=Decimal("0"),
            )

    def test_perceptor_count_must_match_distinct_nifs(self) -> None:
        from pydantic import ValidationError

        row = aggregate_retenciones_111(
            (
                _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="100", retencion="15", source_id="t1"),
            ),
            period="2025-Q1",
        ).rollups[0]
        with pytest.raises(ValidationError, match="distinct perceptor"):
            RetencionesAggregation(
                modelo="111",
                period="2025-Q1",
                rollups=(row,),
                total_perceptors=99,
                total_taxable_base=row.total_taxable_base,
                total_retencion=row.total_retencion,
            )
