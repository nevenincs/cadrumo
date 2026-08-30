"""The Modelo 347 declaration floor merges a counterparty's cohorts before testing.

``declarable_counterparty_nifs_347`` accumulates ``total_invoice_total`` per
``counterparty_nif`` across ALL rollups (each rollup is
one ``(source_kind, counterparty_nif, operation_kind)`` cohort) and tests the MERGED
total against the AEAT ``M347_THRESHOLD_EUR`` (3.005,06 EUR) - not per cohort.
Existing coverage proves per-cohort rollup grouping and the single-cohort
threshold boundary, but not the cross-cohort merge case this module pins - a
single NIF whose two operation-kind cohorts are EACH below the floor yet sum
ABOVE it.

The AEAT rule (Orden EHA/3012/2008 art. 1) declares
a counterparty when operations with them "en su conjunto" exceed 3.005,06 EUR, so
the combined per-NIF total - not any single clave - is what the floor gates.

Real values, no mocks. The threshold is the registry-grounded
``M347_THRESHOLD_EUR``; the oracle is the arithmetic of the seeded per-cohort totals
(2.000 + 1.500 = 3.500 > 3.005,06; each cohort alone < 3.005,06), independent of the
function under test.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.period import Period
from ....core.external_constants import M347_THRESHOLD_EUR
from ....core.aggregation import BindingSourceKind
from .._counterpart import (
    CounterpartObservation,
    OperationKind347,
    aggregate_counterpart_347,
    declarable_counterparty_nifs_347,
    declarable_for_347,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_P_2025_ANNUAL = Period.from_year_and_code(2025, "0A")

# Same counterparty NIF, two operation-kind cohorts, each BELOW the floor.
_MERGED_NIF = "X1111111X"
_DELIVERY_TOTAL = Decimal("2000.00")  # clave A
_ACQUISITION_TOTAL = Decimal("1500.00")  # clave B
# Control counterparty: a single cohort below the floor (must NOT be declarable).
_SINGLE_COHORT_NIF = "Y2222222Y"
_SINGLE_COHORT_TOTAL = Decimal("2500.00")


def _obs(
    *,
    nif: str,
    op_kind: str,
    invoice_total: Decimal,
    source_id: str,
) -> CounterpartObservation:
    return CounterpartObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=source_id,
        counterparty_nif=nif,
        counterparty_name="",
        counterparty_country="ES",
        operation_kind=op_kind,
        operation_period="0A",
        taxable_base=invoice_total,
        invoice_total=invoice_total,
        accrued_on="2025-03-15",
    )


def test_same_nif_two_cohorts_each_below_floor_merge_above_is_declarable() -> None:
    """A NIF with two sub-floor operation-kind cohorts crosses the 347 floor on the MERGED total.

    Each cohort (entregas 2.000, adquisiciones 1.500) is below 3.005,06; their merged
    total 3.500 exceeds it, so the counterparty is declarable. A per-cohort (per-row)
    threshold test - the pre-fix behaviour - would wrongly exclude it.
    """
    # Oracle premises (independent of the function under test).
    assert _DELIVERY_TOTAL < M347_THRESHOLD_EUR
    assert _ACQUISITION_TOTAL < M347_THRESHOLD_EUR
    assert _DELIVERY_TOTAL + _ACQUISITION_TOTAL > M347_THRESHOLD_EUR

    observations = (
        _obs(nif=_MERGED_NIF, op_kind=OperationKind347.DELIVERY.value, invoice_total=_DELIVERY_TOTAL, source_id="tx-a"),
        _obs(
            nif=_MERGED_NIF,
            op_kind=OperationKind347.ACQUISITION.value,
            invoice_total=_ACQUISITION_TOTAL,
            source_id="tx-b",
        ),
        # Control: a different NIF with a single sub-floor cohort.
        _obs(
            nif=_SINGLE_COHORT_NIF,
            op_kind=OperationKind347.DELIVERY.value,
            invoice_total=_SINGLE_COHORT_TOTAL,
            source_id="tx-c",
        ),
    )
    aggregation = aggregate_counterpart_347(observations, period=_P_2025_ANNUAL)

    # The merged NIF produced two distinct cohorts, each below the floor (so it is
    # the MERGE, not a single cohort, that crosses).
    merged_rollups = [r for r in aggregation.rollups if r.counterparty_nif == _MERGED_NIF]
    assert len(merged_rollups) == 2, f"expected two cohorts for {_MERGED_NIF}; got {merged_rollups!r}"
    assert all(r.total_invoice_total < M347_THRESHOLD_EUR for r in merged_rollups), (
        "test premise: each cohort alone must be below the 347 floor so only the merge crosses"
    )

    # The fix: the per-NIF merged total crosses the floor -> declarable.
    assert declarable_for_347(aggregation, counterparty_nif=_MERGED_NIF), (
        f"{_MERGED_NIF} cohorts merge to {_DELIVERY_TOTAL + _ACQUISITION_TOTAL} > {M347_THRESHOLD_EUR}; "
        "must be declarable (per-cohort gating would wrongly exclude it)"
    )

    # Control: the single sub-floor cohort is NOT declarable.
    assert not declarable_for_347(aggregation, counterparty_nif=_SINGLE_COHORT_NIF), (
        f"{_SINGLE_COHORT_NIF} single cohort {_SINGLE_COHORT_TOTAL} < {M347_THRESHOLD_EUR}; must not be declarable"
    )

    # The declarable set is exactly the merged NIF.
    assert declarable_counterparty_nifs_347(aggregation) == frozenset({_MERGED_NIF})
