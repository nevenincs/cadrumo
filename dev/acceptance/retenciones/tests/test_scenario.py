"""Independent checks for the RETENCIONES-01 fixture and oracle."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..scenario import (
    Direction,
    EvidenceState,
    build_installed_annual_cli_slices,
    build_installed_periodic_cli_slices,
    build_scenario,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_payment_date_owns_the_period_across_invoice_boundary() -> None:
    scenario = build_scenario()
    payment = next(row for row in scenario.payments if row.source_id == "professional-cross-quarter")

    assert payment.invoice_date.isoformat() == "2025-03-31"
    assert payment.paid_on.isoformat() == "2025-04-02"
    assert payment.period == "2T"


def test_own_sale_withholding_is_not_a_payer_liability() -> None:
    scenario = build_scenario()

    assert scenario.own_sale_withholding.direction is Direction.SUFFERED_ON_OWN_SALE
    assert scenario.own_sale_withholding not in scenario.payments
    assert sum(row.withheld for row in scenario.periodic_oracle if row.modelo == "111") == Decimal("465.00")


def test_periodic_oracle_keeps_distinct_modelos_and_zero_payment() -> None:
    scenario = build_scenario()
    observed = {(row.modelo, row.period): row for row in scenario.periodic_oracle}

    assert (observed[("111", "1T")].taxable_base, observed[("111", "1T")].withheld) == (
        Decimal("3000.00"),
        Decimal("390.00"),
    )
    assert (observed[("111", "2T")].taxable_base, observed[("111", "2T")].withheld) == (
        Decimal("500.00"),
        Decimal("75.00"),
    )
    assert (observed[("111", "4T")].taxable_base, observed[("111", "4T")].withheld) == (
        Decimal("500.00"),
        Decimal("0.00"),
    )
    assert (observed[("115", "1T")].taxable_base, observed[("115", "1T")].withheld) == (
        Decimal("3000.00"),
        Decimal("570.00"),
    )
    assert (observed[("123", "3T")].taxable_base, observed[("123", "3T")].withheld) == (
        Decimal("1000.00"),
        Decimal("190.00"),
    )


def test_annual_oracle_groups_people_keys_and_properties_substantively() -> None:
    scenario = build_scenario()
    observed = {row.modelo: row for row in scenario.annual_oracle}

    assert (observed["190"].recipient_count, observed["190"].detail_record_count) == (3, 3)
    assert (observed["190"].taxable_base, observed["190"].withheld) == (Decimal("4000.00"), Decimal("465.00"))
    assert (observed["180"].recipient_count, observed["180"].detail_record_count) == (1, 2)
    assert (observed["180"].taxable_base, observed["180"].withheld) == (Decimal("5000.00"), Decimal("950.00"))
    assert (observed["193"].recipient_count, observed["193"].detail_record_count) == (1, 1)


def test_missing_zero_no_activity_and_not_applicable_remain_distinct() -> None:
    scenario = build_scenario()

    states = {
        scenario.missing_state,
        scenario.no_activity_state,
        EvidenceState.ZERO_WITH_RELEVANT_PAYMENT,
        EvidenceState.NOT_APPLICABLE,
    }
    assert len(states) == 4


def test_nonresident_boundary_is_not_forced_into_resident_models() -> None:
    scenario = build_scenario()

    assert scenario.nonresident_boundary.modelo == "216"
    assert scenario.nonresident_boundary.annual_modelo == "296"
    assert scenario.nonresident_boundary not in scenario.payments


def test_scenario_refuses_unreviewed_year_reuse() -> None:
    with pytest.raises(ValueError, match="grounded only for 2025"):
        build_scenario(2026)


def test_installed_cli_slices_close_each_invoice_without_a_rate_engine() -> None:
    """The periodic public inputs are supplied evidence, not computed rates."""
    professional, rent = build_installed_periodic_cli_slices()

    assert professional.invoice_date.isoformat() == "2025-03-31"
    assert tuple(item.paid_on.isoformat() for item in professional.allocations) == ("2025-04-02", "2025-06-30")
    assert sum(item.allocated_withholding for item in professional.allocations) == Decimal("95.00")
    assert sum(item.allocated_settlement for item in professional.allocations) == professional.expected_settlement
    assert rent.property_reference == "1234567VK4713C0001XY"
    assert rent.annual_detail_capture_supported is True
    assert rent.modelo_180_property is not None
    assert professional.modelo_190_detail is not None


def test_installed_annual_cli_slices_keep_allocations_and_no_activity_history_distinct() -> None:
    """Annual rows consume the public payment evidence without inventing empty-quarter payments."""
    rent, professional = build_installed_annual_cli_slices()

    assert rent.modelo == "180"
    assert rent.expected_capture_allocation_count == 3
    assert tuple(
        (period.period, period.evidence_state, period.expected_observation_count) for period in rent.source_periods
    ) == (
        ("1T", EvidenceState.AVAILABLE, 1),
        ("2T", EvidenceState.AVAILABLE, 2),
        ("3T", EvidenceState.NO_RELEVANT_PAYMENT, 0),
        ("4T", EvidenceState.NO_RELEVANT_PAYMENT, 0),
    )
    assert len(rent.expected_type2_rows) == 2
    assert professional.modelo == "190"
    assert professional.expected_capture_allocation_count == 3
    assert professional.source_periods[0].evidence_state is EvidenceState.NO_RELEVANT_PAYMENT
    assert professional.source_periods[1].expected_casillas[1:] == (
        ("08", Decimal("600.00")),
        ("09", Decimal("110.00")),
        ("28", Decimal("110.00")),
        ("30", Decimal("110.00")),
    )


def test_installed_cli_slices_refuse_unreviewed_year_reuse() -> None:
    with pytest.raises(ValueError, match="grounded only for 2025"):
        build_installed_periodic_cli_slices(2026)


def test_installed_annual_cli_slices_refuse_unreviewed_year_reuse() -> None:
    with pytest.raises(ValueError, match="grounded only for 2025"):
        build_installed_annual_cli_slices(2026)
