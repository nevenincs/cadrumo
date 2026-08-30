"""The two-layer rate partition, and the one subtraction both gates read.

A rate-specific official box may assert only a rate the evidence determines, so
a ledger row recording a cuota without recording the rate reaches the rate-blind
total layer and no box. The boxes then sum to less than the total by exactly the
unrated amount. These tests pin what the derivation recognises as that shape,
what it deliberately refuses to recognise, and that the shortfall it computes is
the real difference rather than an artefact of the fixture.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import validated_casilla_id
from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from .....domain.iva.flow import IvaFlowDirection
from .....domain.iva.schema import IvaCashAccountingTreatment, IvaCategory, IvaLedgerObservationRole, IvaRateKind
from ..rate_box_partition import derive_rate_box_partitions, rate_box_coverage_shortfalls
from ..schema import DataBindingDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from ..schema_surfaces import CasillaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LEGAL = ("ley-37-1992:art-91",)
_SOURCE = ("aeat-dr-390-2025",)

_TOTAL_CASILLA = validated_casilla_id("iva.anual.repercutido.super-reducido", surface="test.rate_box.total")
_BOX_4PCT = validated_casilla_id("02", surface="test.rate_box.box")
_BOX_2PCT = validated_casilla_id("668", surface="test.rate_box.box")


def _binding(
    binding_id: str,
    *,
    applied_rates: tuple[Decimal, ...] | None,
    fact: str = "iva_amount_sum",
    rate_kind: IvaRateKind = IvaRateKind.SUPER_REDUCED,
) -> DataBindingDefinition:
    selector: dict[str, object] = {
        "categories": (IvaCategory.DOMESTIC_SUPER_REDUCED,),
        "rate_kinds": (rate_kind,),
        "flow_direction": IvaFlowDirection.REPERCUTIDO,
        "fact": fact,
        "observation_roles": (IvaLedgerObservationRole.SETTLEMENT,),
        "cash_accounting_treatments": (
            IvaCashAccountingTreatment.NONE,
            IvaCashAccountingTreatment.TAXPAYER_REGIME,
            IvaCashAccountingTreatment.SUPPLIER_REGIME,
        ),
    }
    if applied_rates is not None:
        selector["applied_rates"] = applied_rates
    return DataBindingDefinition(
        id=binding_id,
        source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        selector=selector,
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
    )


def _casilla(casilla_id: str, *, number: str, binding: str, exports: bool) -> CasillaDefinition:
    return CasillaDefinition(
        id=casilla_id,
        number=number,
        localization_keys=(f"test.schema.casilla.{number}.label",),
        section=("iva", "anual"),
        input_kind="bound",
        binding=binding,
        export_refs=("modelo-390-page-02.field",) if exports else (),
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
    )


def _revision(
    *,
    bindings: tuple[DataBindingDefinition, ...],
    casillas: tuple[CasillaDefinition, ...],
) -> ModeloRevision:
    return ModeloRevision(
        id="2010-y-siguientes",
        localization_key="test.schema.revision.2010-y-siguientes.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=_LEGAL,
        source_refs=_SOURCE,
        bindings=bindings,
        casillas=casillas,
    )


def _split_revision(
    *,
    total_exports: bool = False,
    box_exports: bool = True,
    fact: str = "iva_amount_sum",
) -> ModeloRevision:
    """The shape the decision prescribes: one rate-blind total, two rate boxes."""
    return _revision(
        bindings=(
            _binding("m390-super-reducido-total", applied_rates=None, fact=fact),
            _binding("m390-super-reducido-4pct", applied_rates=(Decimal("0.04"),), fact=fact),
            _binding("m390-super-reducido-2pct", applied_rates=(Decimal("0.02"),), fact=fact),
        ),
        casillas=(
            _casilla(_TOTAL_CASILLA, number="9001", binding="m390-super-reducido-total", exports=total_exports),
            _casilla(_BOX_4PCT, number="02", binding="m390-super-reducido-4pct", exports=box_exports),
            _casilla(_BOX_2PCT, number="668", binding="m390-super-reducido-2pct", exports=box_exports),
        ),
    )


def test_the_two_layers_are_recognised_as_one_partition() -> None:
    """Bindings agreeing on every axis but ``applied_rates`` are one quantity."""
    partitions = derive_rate_box_partitions(_split_revision())

    assert len(partitions) == 1
    partition = partitions[0]
    assert partition.total_casilla_id == _TOTAL_CASILLA
    assert partition.box_casilla_ids == tuple(sorted((_BOX_4PCT, _BOX_2PCT)))
    assert partition.rate_kinds == (IvaRateKind.SUPER_REDUCED.value,)
    assert partition.fact == "iva_amount_sum"


def test_a_revision_with_no_rate_specific_binding_declares_no_partition() -> None:
    """The tier-only shape every quarterly revision uses is left alone.

    The negative control for every assertion above: without it, a derivation
    that returned a partition for any ledger-IVA binding at all would still pass
    the positive case.
    """
    revision = _revision(
        bindings=(_binding("m303-super-reducido", applied_rates=None),),
        casillas=(_casilla(_TOTAL_CASILLA, number="9001", binding="m303-super-reducido", exports=True),),
    )

    assert derive_rate_box_partitions(revision) == ()


def test_a_total_casilla_that_exports_is_not_a_total_layer() -> None:
    """The un-split shape is not read as a partition.

    A casilla that both totals and exports writes its own rate assertion to the
    record. Reading its rate-specific siblings as the box layer would measure a
    coverage gap the artefact does not have, and refuse an export on it.
    """
    assert derive_rate_box_partitions(_split_revision(total_exports=True)) == ()


def test_rate_specific_casillas_that_export_nothing_are_not_a_box_layer() -> None:
    """No official box asserts a rate, so no filed artefact can be wrong.

    A difference between these casillas and the total is internal bookkeeping.
    Refusing an export on it would block a filing over a discrepancy that never
    reaches the record.
    """
    assert derive_rate_box_partitions(_split_revision(box_exports=False)) == ()


def test_layers_over_different_facts_are_different_partitions() -> None:
    """Base and cuota are separate quantities and never share a partition."""
    cuota = _split_revision()
    base = _revision(
        bindings=(
            _binding("m390-sr-base-total", applied_rates=None, fact="base_amount_sum"),
            _binding("m390-sr-base-4pct", applied_rates=(Decimal("0.04"),), fact="base_amount_sum"),
        ),
        casillas=(
            _casilla("iva.anual.base.super-reducido", number="9002", binding="m390-sr-base-total", exports=False),
            _casilla("01", number="01", binding="m390-sr-base-4pct", exports=True),
        ),
    )
    merged = _revision(
        bindings=(*cuota.bindings, *base.bindings),
        casillas=(*cuota.casillas, *base.casillas),
    )

    partitions = derive_rate_box_partitions(merged)

    assert {partition.fact for partition in partitions} == {"iva_amount_sum", "base_amount_sum"}
    assert len(partitions) == 2


def test_a_partition_whose_boxes_reach_its_total_reports_no_shortfall() -> None:
    """Every row carried a rate, so the breakdown accounts for the whole.

    This is the direction a refusal that fires always would fail, and the reason
    the export gate is safe to ship: the healthy return must pass it.
    """
    partitions = derive_rate_box_partitions(_split_revision())

    shortfalls = rate_box_coverage_shortfalls(
        partitions,
        {_TOTAL_CASILLA: Decimal("350.00"), _BOX_4PCT: Decimal("250.00"), _BOX_2PCT: Decimal("100.00")},
    )

    assert shortfalls == ()


def test_the_shortfall_is_exactly_the_amount_no_box_accounts_for() -> None:
    """The unrated 42.50 stays in the total and reaches neither box."""
    partitions = derive_rate_box_partitions(_split_revision())

    shortfalls = rate_box_coverage_shortfalls(
        partitions,
        {_TOTAL_CASILLA: Decimal("392.50"), _BOX_4PCT: Decimal("250.00"), _BOX_2PCT: Decimal("100.00")},
    )

    assert len(shortfalls) == 1
    assert shortfalls[0].shortfall == Decimal("42.50")
    assert shortfalls[0].total == Decimal("392.50")
    assert shortfalls[0].boxes_total == Decimal("350.00")


def test_an_absent_box_casilla_reads_as_zero_not_as_absent() -> None:
    """The export renderer gives an unpopulated casilla the same reading.

    A box the calculation never populated contributes nothing to the record, so
    treating it as unknown (and skipping the partition) would let exactly the
    emptiest breakdown through.
    """
    partitions = derive_rate_box_partitions(_split_revision())

    shortfalls = rate_box_coverage_shortfalls(partitions, {_TOTAL_CASILLA: Decimal("350.00")})

    assert len(shortfalls) == 1
    assert shortfalls[0].shortfall == Decimal("350.00")


def test_boxes_exceeding_the_total_are_not_reported_as_a_shortfall() -> None:
    """A different defect, deliberately not claimed by this one.

    Overlapping rate boxes put one row in two, so the boxes exceed the total.
    Reporting that here would name the wrong condition and send the operator to
    a ledger repair that would not fix it.
    """
    partitions = derive_rate_box_partitions(_split_revision())

    shortfalls = rate_box_coverage_shortfalls(
        partitions,
        {_TOTAL_CASILLA: Decimal("350.00"), _BOX_4PCT: Decimal("250.00"), _BOX_2PCT: Decimal("150.00")},
    )

    assert shortfalls == ()
