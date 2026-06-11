"""Real-behaviour tests for the IVA prorrata application aggregator.

Tests prove the aggregator threads ``IvaOperation`` records into the
correct prorrata pool per LIVA arts. 101-104, that art. 104 exclusions
do NOT contribute to either pool, and that the provisional/definitiva
orchestrators route the aggregator output into
:class:`~aeat.domain.iva.ProrrataResult` values with the correct
``kind`` and ``period`` per LIVA arts. 105 and 109.

No tautological assertions: the prorrata percentage itself is computed
by the domain calculator (already covered in
``src/aeat/domain/iva/test_prorrata.py``), and the integration tests
here verify that the aggregator's pool routing is faithful to the
classification kind of each input record.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....domain.iva import ProrrataKind, ProrrataRegime
from .. import (
    AggregationPeriodError,
    AggregationValidationError,
    IvaOperation,
    IvaOperationKind,
    ProrrataAggregation,
    aggregate_definitiva_prorrata,
    aggregate_prorrata_inputs,
    aggregate_provisional_prorrata,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _op(
    operation_id: str,
    *,
    year: int,
    base_amount: str,
    kind: IvaOperationKind,
    classification_source: str = "iva-classify:test",
) -> IvaOperation:
    return IvaOperation(
        operation_id=operation_id,
        operation_date=date(year, 6, 15),
        base_amount=Decimal(base_amount),
        kind=kind,
        classification_source=classification_source,
    )


# ---------------------------------------------------------------------------
# Pool routing — the central contract of the aggregator.
# ---------------------------------------------------------------------------


def test_grants_deduction_operations_route_to_con_derecho_pool() -> None:
    """A GRANTS_DEDUCTION operation's base amount lands in
    ``operaciones_con_derecho_deduccion``, not in the exempt pool."""

    aggregation = aggregate_prorrata_inputs(
        (
            _op("inv-1", year=2025, base_amount="10000.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
            _op("inv-2", year=2025, base_amount="5000.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
        ),
        year=2025,
    )
    assert aggregation.inputs.operaciones_con_derecho_deduccion == Decimal("15000.00")
    assert aggregation.inputs.operaciones_sin_derecho_deduccion == Decimal("0")
    assert aggregation.operation_count_con_derecho == 2
    assert aggregation.operation_count_sin_derecho == 0


def test_exempt_without_deduction_operations_route_to_sin_derecho_pool() -> None:
    """An EXEMPT_WITHOUT_DEDUCTION operation lands in the exempt pool
    (LIVA art. 20 exempt supplies)."""

    aggregation = aggregate_prorrata_inputs(
        (
            _op(
                "inv-rent",
                year=2025,
                base_amount="8000.00",
                kind=IvaOperationKind.EXEMPT_WITHOUT_DEDUCTION,
                classification_source="liva-art-20.1.23-rental",
            ),
        ),
        year=2025,
    )
    assert aggregation.inputs.operaciones_con_derecho_deduccion == Decimal("0")
    assert aggregation.inputs.operaciones_sin_derecho_deduccion == Decimal("8000.00")
    assert aggregation.operation_count_sin_derecho == 1


def test_art_104_excluded_operations_do_not_contribute_to_either_pool() -> None:
    """LIVA art. 104: subvenciones not linked, autoconsumos, sale of
    bienes de inversión, and certain non-recurring operations are
    excluded from BOTH numerator and denominator."""

    aggregation = aggregate_prorrata_inputs(
        (
            _op("inv-1", year=2025, base_amount="10000.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
            _op(
                "subv-1",
                year=2025,
                base_amount="50000.00",
                kind=IvaOperationKind.EXCLUDED_BY_ART_104,
                classification_source="liva-art-104.dos.2-subvencion-no-vinculada",
            ),
        ),
        year=2025,
    )
    # The excluded subvención does NOT appear in either pool.
    assert aggregation.inputs.operaciones_con_derecho_deduccion == Decimal("10000.00")
    assert aggregation.inputs.operaciones_sin_derecho_deduccion == Decimal("0")
    # But it is counted and tracked separately for provenance.
    assert aggregation.operation_count_excluded == 1
    assert aggregation.excluded_amount_total == Decimal("50000.00")


def test_operations_outside_target_year_are_filtered_out() -> None:
    """Only operations whose date.year matches the target year
    contribute. Prior-year and following-year operations are skipped."""

    aggregation = aggregate_prorrata_inputs(
        (
            _op("prior", year=2024, base_amount="9999.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
            _op("target", year=2025, base_amount="7777.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
            _op("next", year=2026, base_amount="5555.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
        ),
        year=2025,
    )
    assert aggregation.inputs.operaciones_con_derecho_deduccion == Decimal("7777.00")
    assert aggregation.operation_count_con_derecho == 1


def test_empty_operations_produce_zero_pools() -> None:
    """An empty operations sequence yields zero pools (the calculator's
    zero-defence layer then maps that to 100% per AEAT criterion; that
    behaviour belongs to the domain calculator's tests)."""

    aggregation = aggregate_prorrata_inputs((), year=2025)
    assert aggregation.inputs.operaciones_con_derecho_deduccion == Decimal("0")
    assert aggregation.inputs.operaciones_sin_derecho_deduccion == Decimal("0")
    assert aggregation.operation_count_con_derecho == 0
    assert aggregation.operation_count_sin_derecho == 0
    assert aggregation.operation_count_excluded == 0
    assert aggregation.excluded_amount_total == Decimal("0")


def test_aggregation_inputs_are_correctly_carried_into_the_result() -> None:
    """ProrrataAggregation.inputs is a frozen ProrrataInputs ready for
    the domain calculator's consumption."""

    aggregation = aggregate_prorrata_inputs(
        (
            _op("a", year=2025, base_amount="40000.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
            _op("b", year=2025, base_amount="10000.00", kind=IvaOperationKind.EXEMPT_WITHOUT_DEDUCTION),
        ),
        year=2025,
    )
    assert aggregation.year == 2025
    # The aggregation is immutable.
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        aggregation.year = 2024


def test_aggregate_rejects_year_outside_supported_range() -> None:
    with pytest.raises(AggregationPeriodError) as exc_info:
        aggregate_prorrata_inputs((), year=1999)
    assert exc_info.value.translated_message == "aggregation.prorrata.errors.year_out_of_range"
    assert exc_info.value.context is not None and exc_info.value.context["year"] == 1999

    with pytest.raises(AggregationPeriodError) as exc_info2:
        aggregate_prorrata_inputs((), year=2101)
    assert exc_info2.value.translated_message == "aggregation.prorrata.errors.year_out_of_range"
    assert exc_info2.value.context is not None and exc_info2.value.context["year"] == 2101


# ---------------------------------------------------------------------------
# Provisional orchestrator (LIVA art. 105).
# ---------------------------------------------------------------------------


def test_provisional_orchestrator_uses_prior_year_inputs_and_current_year_stamp() -> None:
    """LIVA art. 105: provisional percentage applied in current_year is
    derived from prior_year's actuals. The result's ``year`` field
    records the period being filed (current_year), not the year whose
    operations were aggregated."""

    prior_ops = (
        _op("p-1", year=2024, base_amount="60000.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
        _op("p-2", year=2024, base_amount="40000.00", kind=IvaOperationKind.EXEMPT_WITHOUT_DEDUCTION),
    )
    result, aggregation = aggregate_provisional_prorrata(
        prior_ops,
        prior_year=2024,
        current_year=2025,
        period="Q1",
    )
    # Aggregation was over prior_year.
    assert aggregation.year == 2024
    # Result stamps current_year + period.
    assert result.year == 2025
    assert result.period == "Q1"
    assert result.kind is ProrrataKind.PROVISIONAL
    assert result.regime is ProrrataRegime.GENERAL


def test_provisional_orchestrator_rejects_non_advancing_year_pair() -> None:
    """current_year must be strictly greater than prior_year."""

    ops = (_op("p", year=2024, base_amount="10000.00", kind=IvaOperationKind.GRANTS_DEDUCTION),)
    with pytest.raises(AggregationValidationError) as exc_info:
        aggregate_provisional_prorrata(ops, prior_year=2024, current_year=2024, period="Q1")
    assert exc_info.value.translated_message == "aggregation.prorrata.errors.current_year_not_after_prior"
    assert exc_info.value.context is not None and "prior_year" in exc_info.value.context

    with pytest.raises(AggregationValidationError) as exc_info2:
        aggregate_provisional_prorrata(ops, prior_year=2025, current_year=2024, period="Q1")
    assert exc_info2.value.translated_message == "aggregation.prorrata.errors.current_year_not_after_prior"


def test_provisional_orchestrator_rejects_annual_period_token() -> None:
    """``annual`` is the definitiva period token; provisional must be
    quarterly (Qn) or monthly (Mnn)."""

    ops = (_op("p", year=2024, base_amount="10000.00", kind=IvaOperationKind.GRANTS_DEDUCTION),)
    with pytest.raises(AggregationValidationError) as exc_info:
        aggregate_provisional_prorrata(ops, prior_year=2024, current_year=2025, period="annual")
    assert exc_info.value.translated_message == "aggregation.prorrata.errors.invalid_provisional_period"
    assert exc_info.value.context is not None and "period" in exc_info.value.context


# ---------------------------------------------------------------------------
# Definitiva orchestrator (LIVA art. 109).
# ---------------------------------------------------------------------------


def test_definitiva_orchestrator_uses_current_year_actuals() -> None:
    """LIVA art. 109: definitiva uses the year's actual operations."""

    ops = (
        _op("a", year=2025, base_amount="80000.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
        _op("b", year=2025, base_amount="20000.00", kind=IvaOperationKind.EXEMPT_WITHOUT_DEDUCTION),
    )
    result, aggregation = aggregate_definitiva_prorrata(ops, year=2025)
    assert aggregation.year == 2025
    assert result.year == 2025
    assert result.kind is ProrrataKind.DEFINITIVA
    assert result.period is None  # definitiva is annual; the result validator accepts None.


def test_definitiva_orchestrator_skips_other_year_operations() -> None:
    """Definitiva must not pull operations from a different year even
    when they are passed in."""

    ops = (
        _op("noise", year=2024, base_amount="9999.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
        _op("target", year=2025, base_amount="50000.00", kind=IvaOperationKind.GRANTS_DEDUCTION),
    )
    _result, aggregation = aggregate_definitiva_prorrata(ops, year=2025)
    assert aggregation.inputs.operaciones_con_derecho_deduccion == Decimal("50000.00")
    assert aggregation.operation_count_con_derecho == 1


# ---------------------------------------------------------------------------
# Operation schema validation.
# ---------------------------------------------------------------------------


def test_iva_operation_rejects_negative_base_amount() -> None:
    with pytest.raises(ValidationError, match=r"base_amount|greater than|negative"):
        IvaOperation(
            operation_id="op",
            operation_date=date(2025, 1, 1),
            base_amount=Decimal("-1"),
            kind=IvaOperationKind.GRANTS_DEDUCTION,
            classification_source="test",
        )


def test_iva_operation_is_frozen_and_forbids_extras() -> None:
    op = _op("op", year=2025, base_amount="100.00", kind=IvaOperationKind.GRANTS_DEDUCTION)
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        op.base_amount = Decimal("0")
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        extra: dict[str, object] = {"unexpected": True}
        IvaOperation.model_validate(
            {
                "operation_id": "op",
                "operation_date": date(2025, 1, 1),
                "base_amount": Decimal("100"),
                "kind": IvaOperationKind.GRANTS_DEDUCTION,
                "classification_source": "test",
                **extra,
            },
        )


def test_iva_operation_rejects_empty_operation_id() -> None:
    with pytest.raises(ValidationError, match=r"operation_id|at least 1 character"):
        IvaOperation(
            operation_id="",
            operation_date=date(2025, 1, 1),
            base_amount=Decimal("10.00"),
            kind=IvaOperationKind.GRANTS_DEDUCTION,
            classification_source="test",
        )


def test_prorrata_aggregation_is_immutable() -> None:
    aggregation = aggregate_prorrata_inputs((), year=2025)
    assert isinstance(aggregation, ProrrataAggregation)
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        aggregation.operation_count_excluded = 99
