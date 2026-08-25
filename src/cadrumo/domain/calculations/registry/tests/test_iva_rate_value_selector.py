"""A rate-specific binding rejects a same-tier line charged at another rate.

Modelo 390 carries one box per rate per window where Modelo 303 carries one per
tier, because a tier's rate can change inside a filing year -- the anti-inflation
food measures stepped the super-reducido tier 4 % to 2 % to 0 % across successive
extensions. A 2 % box that admitted a 4 % line would declare both under one
figure the form asks to be reported separately.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.ledger_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
)
from cadrumo.domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodSelector

from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from .....domain.iva import (
    IvaCashAccountingTreatment,
    IvaCategory,
    IvaFlowDirection,
    IvaLedgerObservationRole,
    IvaRateKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _binding(binding_id: str, *, applied_rates: tuple[Decimal, ...] | None) -> DataBindingDefinition:
    selector: dict[str, object] = {
        "categories": (IvaCategory.DOMESTIC_SUPER_REDUCED,),
        "rate_kinds": (IvaRateKind.SUPER_REDUCED,),
        "flow_direction": IvaFlowDirection.REPERCUTIDO,
        "fact": "base_amount_sum",
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
        legal_refs=("ley-37-1992:art-91",),
        source_refs=("aeat-dr-390-2025",),
    )


def _revision(*bindings: DataBindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="2010-y-siguientes",
        localization_key="test.schema.revision.2010-y-siguientes.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=("ley-37-1992:art-91",),
        source_refs=("aeat-dr-390-2025",),
        bindings=bindings,
    )


def _row(ledger_id: str, *, applied_rate: Decimal | None, base: str) -> IvaLedgerObservation:
    """A super-reducido sale at ``applied_rate``.

    Both rows share the tier, which is the whole point: the tier cannot separate
    them and only the value can.
    """
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=date(2024, 11, 15),
        category=IvaCategory.DOMESTIC_SUPER_REDUCED,
        rate_kind=IvaRateKind.SUPER_REDUCED,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=Decimal(base),
        iva_amount=Decimal("0.00"),
        applied_rate=applied_rate,
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def test_a_rate_specific_binding_takes_only_its_own_rate() -> None:
    """The 2 % box must not absorb the 4 % line that shares its tier."""
    revision = _revision(
        _binding("m390-super-reducido-2pct", applied_rates=(Decimal("0.02"),)),
        _binding("m390-super-reducido-4pct", applied_rates=(Decimal("0.04"),)),
    )
    rows = (
        _row("row-2pct", applied_rate=Decimal("0.02"), base="100.00"),
        _row("row-4pct", applied_rate=Decimal("0.04"), base="250.00"),
    )

    resolved = resolve_ledger_iva_aggregation_binding_values(revision, rows)

    assert resolved["m390-super-reducido-2pct"] == Decimal("100.00")
    assert resolved["m390-super-reducido-4pct"] == Decimal("250.00")


def test_without_the_axis_one_tier_binding_takes_both() -> None:
    """The quarterly shape is unchanged, which is what makes the axis additive.

    A binding that names no rates keeps matching every rate its tier admits, so
    Modelo 303's one-box-per-tier bindings behave exactly as before.
    """
    revision = _revision(_binding("m303-super-reducido", applied_rates=None))
    rows = (
        _row("row-2pct", applied_rate=Decimal("0.02"), base="100.00"),
        _row("row-4pct", applied_rate=Decimal("0.04"), base="250.00"),
    )

    resolved = resolve_ledger_iva_aggregation_binding_values(revision, rows)

    assert resolved["m303-super-reducido"] == Decimal("350.00")


def test_a_rate_less_row_reaches_no_rate_specific_binding() -> None:
    """An unmeasured line must not land in a box that asserts a rate.

    ``applied_rate is None`` means the rate is genuinely unknown -- an
    invoice-sourced line carries a rate slot, not a number -- and the annual
    return is where a per-rate assertion is read. It still reaches the
    tier-only binding, so the value is declared, just not as a rate claim.
    """
    revision = _revision(
        _binding("m390-super-reducido-4pct", applied_rates=(Decimal("0.04"),)),
        _binding("m303-super-reducido", applied_rates=None),
    )
    rows = (_row("row-unknown-rate", applied_rate=None, base="500.00"),)

    resolved = resolve_ledger_iva_aggregation_binding_values(revision, rows)

    assert resolved["m390-super-reducido-4pct"] == Decimal("0")
    assert resolved["m303-super-reducido"] == Decimal("500.00")
