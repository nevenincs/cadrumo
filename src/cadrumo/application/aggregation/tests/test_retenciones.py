"""Tests for the Modelo 111 retenciones aggregator."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import BindingSourceKind, Period
from .._retenciones import (
    RETENCIONES_MODELO_SCHEME_CATALOGUE,
    RetencionesAggregation,
    RetencionObservation,
    RetencionScheme,
    aggregate_retenciones_111,
    aggregate_retenciones_115,
    aggregate_retenciones_123,
    aggregate_retenciones_180,
    aggregate_retenciones_190,
    aggregate_retenciones_193,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_2025_Q1 = Period.from_year_and_code(2025, "1T")
_P_2025_ANNUAL = Period.from_year_and_code(2025, "0A")


def _obs(
    *,
    nif: str,
    scheme: RetencionScheme,
    base: str,
    retencion: str,
    name: str = "",
    source_kind: BindingSourceKind = BindingSourceKind.LEDGER_TRANSACTION,
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

        with pytest.raises(ValidationError, match="source_kind"):
            RetencionObservation.model_validate(
                {
                    "source_kind": "invoice",
                    "source_object_id": "x",
                    "perceptor_nif": "A1",
                    "scheme": RetencionScheme.WORK_INCOME,
                    "taxable_base": Decimal("0"),
                    "retencion_amount": Decimal("0"),
                    "accrued_on": "2025-01-01",
                },
            )

    def test_observation_rejects_non_retenciones_source_kind_member(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="unsupported"):
            RetencionObservation(
                source_kind=BindingSourceKind.RETENCIONES_AGGREGATION,
                source_object_id="x",
                perceptor_nif="A1",
                scheme=RetencionScheme.WORK_INCOME,
                taxable_base=Decimal("0"),
                retencion_amount=Decimal("0"),
                accrued_on="2025-01-01",
            )

    def test_observation_accepts_canonical_source_kinds(self) -> None:
        expected = {
            BindingSourceKind.LEDGER_TRANSACTION,
            BindingSourceKind.PURCHASE_INVOICE_EVIDENCE,
            BindingSourceKind.PAYABLE_INVOICE,
            BindingSourceKind.COLLECTIBLE_INVOICE,
        }
        observed: set[BindingSourceKind] = set()
        for kind in expected:
            obs = _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="0", retencion="0", source_kind=kind)
            observed.add(obs.source_kind)
            from_string = _obs(
                nif="A1",
                scheme=RetencionScheme.WORK_INCOME,
                base="0",
                retencion="0",
                source_kind=kind,
            )
            assert from_string.source_kind is kind
        assert observed == expected


class TestAggregate111:
    def test_empty_observations_produces_zero_totals(self) -> None:
        result = aggregate_retenciones_111((), period=_P_2025_Q1)
        assert result.modelo == "111"
        assert result.period == _P_2025_Q1
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
        result = aggregate_retenciones_111((obs,), period=_P_2025_Q1)
        assert len(result.rollups) == 1
        row = result.rollups[0]
        assert row.source_kind is BindingSourceKind.LEDGER_TRANSACTION
        assert row.perceptor_nif == "B12345678"
        assert row.perceptor_name == "Acme S.L."
        assert row.scheme is RetencionScheme.ECONOMIC_ACTIVITY
        assert row.observations_count == 1
        assert row.total_taxable_base == Decimal("1000.00")
        assert row.total_retencion == Decimal("150.00")
        assert result.total_perceptors == 1

    def test_multiple_observations_same_perceptor_and_scheme_sum(self) -> None:
        obs_a = _obs(
            nif="B1",
            scheme=RetencionScheme.WORK_INCOME,
            base="500.00",
            retencion="75.00",
            source_id="tx-1",
        )
        obs_b = _obs(
            nif="B1",
            scheme=RetencionScheme.WORK_INCOME,
            base="700.00",
            retencion="105.00",
            source_id="tx-2",
        )
        result = aggregate_retenciones_111((obs_a, obs_b), period=_P_2025_Q1)
        assert len(result.rollups) == 1
        assert result.rollups[0].observations_count == 2
        assert result.rollups[0].total_taxable_base == Decimal("1200.00")
        assert result.rollups[0].total_retencion == Decimal("180.00")

    def test_same_perceptor_different_schemes_yield_separate_rollups(self) -> None:
        obs_work = _obs(
            nif="B1",
            scheme=RetencionScheme.WORK_INCOME,
            base="500.00",
            retencion="75.00",
            source_id="tx-1",
        )
        obs_econ = _obs(
            nif="B1",
            scheme=RetencionScheme.ECONOMIC_ACTIVITY,
            base="700.00",
            retencion="105.00",
            source_id="tx-2",
        )
        result = aggregate_retenciones_111((obs_work, obs_econ), period=_P_2025_Q1)
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
        result = aggregate_retenciones_111(observations, period=_P_2025_Q1)
        assert result.total_perceptors == 3
        assert result.total_taxable_base == Decimal("600")
        assert result.total_retencion == Decimal("90")

    def test_rollups_sort_deterministically_by_perceptor_then_scheme(self) -> None:
        observations = (
            _obs(nif="Z1", scheme=RetencionScheme.WORK_INCOME, base="100", retencion="15", source_id="t1"),
            _obs(nif="A1", scheme=RetencionScheme.ECONOMIC_ACTIVITY, base="200", retencion="30", source_id="t2"),
            _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="300", retencion="45", source_id="t3"),
        )
        result = aggregate_retenciones_111(observations, period=_P_2025_Q1)
        keys = [(row.perceptor_nif, row.scheme.value) for row in result.rollups]
        assert keys == sorted(keys)

    def test_aggregation_is_input_order_invariant(self) -> None:
        observations = (
            _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="100", retencion="15", source_id="t1"),
            _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="200", retencion="30", source_id="t2"),
        )
        forward = aggregate_retenciones_111(observations, period=_P_2025_Q1)
        reverse = aggregate_retenciones_111(tuple(reversed(observations)), period=_P_2025_Q1)
        assert forward.model_dump_json() == reverse.model_dump_json()

    def test_unregistered_modelo_raises_domain_error(self) -> None:
        from .._grouping import filter_observations_for_modelo
        from ..errors import AggregationUnsupportedModeloError

        with pytest.raises(AggregationUnsupportedModeloError):
            filter_observations_for_modelo(
                (),
                modelo="347",
                catalogue=RETENCIONES_MODELO_SCHEME_CATALOGUE,
                attribute_fn=lambda obs: obs.scheme,
                aggregator_label="retenciones aggregator",
            )


class TestAggregate123:
    def test_123_aggregates_capital_income_schemes(self) -> None:
        observations = (
            _obs(nif="B1", scheme=RetencionScheme.CAPITAL_INTEREST, base="500", retencion="95", source_id="c1"),
            _obs(nif="B1", scheme=RetencionScheme.CAPITAL_DIVIDEND, base="1000", retencion="190", source_id="c2"),
            _obs(nif="B1", scheme=RetencionScheme.WORK_INCOME, base="999", retencion="150", source_id="c3"),
        )
        result = aggregate_retenciones_123(observations, period=_P_2025_Q1)
        assert result.modelo == "123"
        # WORK_INCOME observation is filtered out (not in 123 catalogue)
        assert len(result.rollups) == 2
        schemes = {row.scheme for row in result.rollups}
        assert schemes == {RetencionScheme.CAPITAL_INTEREST, RetencionScheme.CAPITAL_DIVIDEND}

    def test_123_other_scheme_included(self) -> None:
        observations = (
            _obs(nif="B1", scheme=RetencionScheme.CAPITAL_OTHER, base="300", retencion="57", source_id="c1"),
        )
        result = aggregate_retenciones_123(observations, period=_P_2025_Q1)
        assert len(result.rollups) == 1
        assert result.rollups[0].scheme is RetencionScheme.CAPITAL_OTHER


class TestAggregate180190193:
    def test_180_widens_115_observations_to_annual_period(self) -> None:
        observations = (
            _obs(nif="L1", scheme=RetencionScheme.URBAN_RENTAL, base="2000", retencion="380", source_id="r1"),
            _obs(nif="L1", scheme=RetencionScheme.URBAN_RENTAL, base="2000", retencion="380", source_id="r2"),
        )
        result = aggregate_retenciones_180(observations, period=_P_2025_ANNUAL)
        assert result.modelo == "180"
        assert result.period == _P_2025_ANNUAL
        assert result.total_taxable_base == Decimal("4000")
        assert result.total_retencion == Decimal("760")

    def test_190_widens_111_observations_to_annual_period(self) -> None:
        observations = (
            _obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="1000", retencion="150", source_id="t1"),
            _obs(nif="A2", scheme=RetencionScheme.PROFESSIONAL, base="500", retencion="75", source_id="t2"),
        )
        result = aggregate_retenciones_190(observations, period=_P_2025_ANNUAL)
        assert result.modelo == "190"
        assert result.total_perceptors == 2

    def test_193_widens_123_observations_to_annual_period(self) -> None:
        observations = (
            _obs(nif="B1", scheme=RetencionScheme.CAPITAL_DIVIDEND, base="800", retencion="152", source_id="c1"),
            _obs(nif="B2", scheme=RetencionScheme.CAPITAL_INTEREST, base="200", retencion="38", source_id="c2"),
        )
        result = aggregate_retenciones_193(observations, period=_P_2025_ANNUAL)
        assert result.modelo == "193"
        assert result.total_perceptors == 2
        assert result.total_retencion == Decimal("190")


class TestAggregate115:
    def test_115_filters_to_urban_rental_only(self) -> None:
        observations = (
            _obs(nif="L1", scheme=RetencionScheme.URBAN_RENTAL, base="800", retencion="152", source_id="r1"),
            _obs(nif="L1", scheme=RetencionScheme.WORK_INCOME, base="100", retencion="15", source_id="r2"),
        )
        result = aggregate_retenciones_115(observations, period=_P_2025_Q1)
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
        result = aggregate_retenciones_115(observations, period=_P_2025_Q1)
        assert result.total_perceptors == 2
        l1 = next(row for row in result.rollups if row.perceptor_nif == "L1")
        assert l1.observations_count == 2
        assert l1.total_taxable_base == Decimal("1000")
        assert l1.total_retencion == Decimal("190")

    def test_115_empty_input_returns_zero_totals(self) -> None:
        result = aggregate_retenciones_115((), period=_P_2025_Q1)
        assert result.modelo == "115"
        assert result.rollups == ()
        assert result.total_perceptors == 0


class TestAggregationInvariants:
    def test_totals_must_match_rollups(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="!= sum of rollups"):
            RetencionesAggregation(
                modelo="111",
                period=_P_2025_Q1,
                rollups=(),
                total_perceptors=0,
                total_taxable_base=Decimal("999"),
                total_retencion=Decimal("0"),
            )

    def test_combined_period_string_is_not_coerced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Period"):
            RetencionesAggregation.model_validate(
                {
                    "modelo": "111",
                    "period": "2025Q1",
                    "rollups": (),
                    "total_perceptors": 0,
                    "total_taxable_base": Decimal("0"),
                    "total_retencion": Decimal("0"),
                },
            )

    def test_period_dict_is_not_coerced(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="Period"):
            RetencionesAggregation.model_validate(
                {
                    "modelo": "111",
                    "period": {"filing_year": 2025, "code": "1T"},
                    "rollups": (),
                    "total_perceptors": 0,
                    "total_taxable_base": Decimal("0"),
                    "total_retencion": Decimal("0"),
                },
            )

    def test_perceptor_count_must_match_distinct_nifs(self) -> None:
        from pydantic import ValidationError

        row = aggregate_retenciones_111(
            (_obs(nif="A1", scheme=RetencionScheme.WORK_INCOME, base="100", retencion="15", source_id="t1"),),
            period=_P_2025_Q1,
        ).rollups[0]
        with pytest.raises(ValidationError, match="distinct perceptor"):
            RetencionesAggregation(
                modelo="111",
                period=_P_2025_Q1,
                rollups=(row,),
                total_perceptors=99,
                total_taxable_base=row.total_taxable_base,
                total_retencion=row.total_retencion,
            )


ValidationError = __import__("pydantic").ValidationError


class TestAccruedDateAuthority:
    """``accrued_on`` is admitted by the canonical date authority, not a length bound."""

    @pytest.mark.parametrize("impossible", ["2026-99-99", "2026-02-30", "2025-13-01"])
    def test_impossible_accrued_dates_are_refused(self, impossible: str) -> None:
        """An impossible calendar date never reaches a rollup or the encrypted store.

        ``accrued_on`` was bounded by string length alone, so a ten-character
        non-date was summed and counted exactly like a real accrual, and the
        per-perceptor store persisted it as declared evidence.
        """
        with pytest.raises(ValidationError):
            _obs(
                nif="11111111H",
                scheme=RetencionScheme.ECONOMIC_ACTIVITY,
                base="100",
                retencion="15",
                accrued=impossible,
            )

    @pytest.mark.parametrize("malformed", ["20260301", "2026-3-1", "01-03-2026"])
    def test_non_extended_iso_accrued_dates_are_refused(self, malformed: str) -> None:
        """Only the extended ``YYYY-MM-DD`` wire form is admitted."""
        with pytest.raises(ValidationError):
            _obs(
                nif="11111111H", scheme=RetencionScheme.ECONOMIC_ACTIVITY, base="100", retencion="15", accrued=malformed
            )

    def test_valid_accrued_date_is_admitted_and_aggregates(self) -> None:
        """The positive control: a real accrual date is admitted and rolls up."""
        observation = _obs(
            nif="11111111H",
            scheme=RetencionScheme.ECONOMIC_ACTIVITY,
            base="100",
            retencion="15",
            accrued="2026-03-01",
        )
        assert observation.accrued_on == "2026-03-01"
        aggregation = aggregate_retenciones_111((observation,), period=Period.from_year_and_code(2026, "1T"))
        assert aggregation.total_perceptors == 1
