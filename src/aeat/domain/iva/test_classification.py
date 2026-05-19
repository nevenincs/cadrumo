"""Unit tests for :func:`aeat.domain.vat.classify_vat`.

Walks every closed-table rule (R01 through R30) plus the R99 fallthrough,
verifies the cross-field ``rate_tier`` requirements on
:class:`aeat.domain.vat.VATClassificationCriteria`, and checks that rate
resolution honours the transaction date.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from . import (
    CustomerResidency,
    CustomerTaxStatus,
    EUMemberState,
    InvoiceDirection,
    IssuerResidency,
    TransactionKind,
    VATCategory,
    VATClassificationCriteria,
    VATRateKind,
    classify_vat,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _criteria(**overrides: object) -> VATClassificationCriteria:
    """Build a baseline ES-to-ES B2B goods ISSUED criteria with ``overrides`` applied."""
    base: dict[str, object] = {
        "transaction_date": date(2025, 6, 15),
        "issuer_residency": IssuerResidency.ES_MAINLAND,
        "customer_residency": CustomerResidency.ES_MAINLAND,
        "customer_tax_status": CustomerTaxStatus.B2B_VAT_REGISTERED,
        "kind": TransactionKind.GOODS,
        "direction": InvoiceDirection.ISSUED,
        "rate_tier": VATRateKind.GENERAL,
    }
    base.update(overrides)
    return VATClassificationCriteria.model_validate(base)


def test_r01_construction_reverse_charge() -> None:
    result = classify_vat(_criteria(kind=TransactionKind.CONSTRUCTION_REVERSE_CHARGE))
    assert result.category is VATCategory.DOMESTIC_REVERSE_CHARGE
    assert result.requires_reverse_charge is True
    assert result.matched_rule_id == "R01_construction_reverse_charge"


def test_r02_waste_reverse_charge() -> None:
    result = classify_vat(_criteria(kind=TransactionKind.WASTE_REVERSE_CHARGE))
    assert result.category is VATCategory.DOMESTIC_REVERSE_CHARGE
    assert result.matched_rule_id == "R02_waste_reverse_charge"


def test_r03_electronics_reverse_charge() -> None:
    result = classify_vat(
        _criteria(
            kind=TransactionKind.ELECTRONICS_REVERSE_CHARGE,
            customer_tax_status=CustomerTaxStatus.B2B_VAT_REGISTERED,
        )
    )
    assert result.category is VATCategory.DOMESTIC_REVERSE_CHARGE
    assert result.matched_rule_id == "R03_electronics_reverse_charge"


def test_r03_electronics_b2c_does_not_trigger_reverse_charge() -> None:
    """Electronics RC requires B2B; a B2C consumer falls through to R05."""
    result = classify_vat(
        _criteria(
            kind=TransactionKind.ELECTRONICS_REVERSE_CHARGE,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        )
    )
    assert result.matched_rule_id != "R03_electronics_reverse_charge"


def test_r04_immovable_b2c_exempt() -> None:
    result = classify_vat(
        _criteria(
            kind=TransactionKind.IMMOVABLE_PROPERTY,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        )
    )
    assert result.category is VATCategory.DOMESTIC_EXEMPT
    assert result.matched_rule_id == "R04_immovable_property_exempt"


def test_r05_domestic_general_21() -> None:
    result = classify_vat(_criteria(rate_tier=VATRateKind.GENERAL))
    assert result.category is VATCategory.DOMESTIC_GENERAL_21
    assert result.matched_rule_id == "R05_domestic_at_rate_tier"
    assert result.rate is not None
    assert result.rate.pct == Decimal("21")


def test_r05_domestic_reduced_10() -> None:
    result = classify_vat(_criteria(rate_tier=VATRateKind.REDUCED))
    assert result.category is VATCategory.DOMESTIC_REDUCED_10
    assert result.rate is not None
    assert result.rate.pct == Decimal("10")


def test_r05_domestic_super_reduced_4() -> None:
    result = classify_vat(_criteria(rate_tier=VATRateKind.SUPER_REDUCED))
    assert result.category is VATCategory.DOMESTIC_SUPER_REDUCED_4
    assert result.rate is not None
    assert result.rate.pct == Decimal("4")


def test_r10_intra_community_supply_goods() -> None:
    result = classify_vat(
        _criteria(
            customer_residency=CustomerResidency.EU_MEMBER,
            customer_member_state=EUMemberState.DE,
            kind=TransactionKind.GOODS,
            direction=InvoiceDirection.ISSUED,
        )
    )
    assert result.category is VATCategory.INTRA_COMMUNITY_SUPPLY
    assert result.matched_rule_id == "R10_intra_community_supply"


def test_r11_intra_community_acquisition_goods() -> None:
    result = classify_vat(
        _criteria(
            issuer_residency=IssuerResidency.EU_MEMBER,
            issuer_member_state=EUMemberState.DE,
            customer_residency=CustomerResidency.ES_MAINLAND,
            kind=TransactionKind.GOODS,
            direction=InvoiceDirection.RECEIVED,
        )
    )
    assert result.category is VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
    assert result.requires_reverse_charge is True


def test_r12_services_b2b_eu_outbound_is_not_subject_in_es() -> None:
    result = classify_vat(
        _criteria(
            customer_residency=CustomerResidency.EU_MEMBER,
            customer_member_state=EUMemberState.FR,
            kind=TransactionKind.SERVICES_GENERAL,
            direction=InvoiceDirection.ISSUED,
        )
    )
    assert result.category is VATCategory.DOMESTIC_NOT_SUBJECT
    assert result.matched_rule_id == "R12_services_b2b_eu_outbound"


def test_r13_services_b2b_eu_inbound_reverse_charge() -> None:
    result = classify_vat(
        _criteria(
            issuer_residency=IssuerResidency.EU_MEMBER,
            issuer_member_state=EUMemberState.FR,
            customer_residency=CustomerResidency.ES_MAINLAND,
            kind=TransactionKind.SERVICES_GENERAL,
            direction=InvoiceDirection.RECEIVED,
        )
    )
    assert result.category is VATCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
    assert result.matched_rule_id == "R13_services_b2b_eu_inbound"


def test_r14_digital_b2c_oss() -> None:
    result = classify_vat(
        _criteria(
            customer_residency=CustomerResidency.EU_MEMBER,
            customer_member_state=EUMemberState.IT,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
            kind=TransactionKind.SERVICES_DIGITAL_B2C_OSS,
            direction=InvoiceDirection.ISSUED,
        )
    )
    assert result.category is VATCategory.DOMESTIC_NOT_SUBJECT
    assert result.matched_rule_id == "R14_digital_b2c_oss"


def test_r20_export_goods() -> None:
    result = classify_vat(
        _criteria(
            customer_residency=CustomerResidency.THIRD_COUNTRY,
            kind=TransactionKind.GOODS,
            direction=InvoiceDirection.ISSUED,
        )
    )
    assert result.category is VATCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED
    assert result.matched_rule_id == "R20_export_goods"


def test_r21_import_goods() -> None:
    result = classify_vat(
        _criteria(
            issuer_residency=IssuerResidency.THIRD_COUNTRY,
            customer_residency=CustomerResidency.ES_MAINLAND,
            kind=TransactionKind.GOODS,
            direction=InvoiceDirection.RECEIVED,
        )
    )
    assert result.category is VATCategory.IMPORT_THIRD_COUNTRY


def test_r22_services_outbound_third_country() -> None:
    result = classify_vat(
        _criteria(
            customer_residency=CustomerResidency.THIRD_COUNTRY,
            kind=TransactionKind.SERVICES_GENERAL,
            direction=InvoiceDirection.ISSUED,
        )
    )
    assert result.category is VATCategory.OPERACION_NO_SUJETA
    assert result.matched_rule_id == "R22_services_outbound_third_country"


def test_r30_canarias_issuer_short_circuits_to_not_subject() -> None:
    result = classify_vat(_criteria(issuer_residency=IssuerResidency.ES_CANARIAS))
    assert result.category is VATCategory.DOMESTIC_NOT_SUBJECT
    assert result.matched_rule_id == "R30_canarias_ceuta_melilla"


def test_r99_fallthrough_returns_unknown() -> None:
    """A non-matching THIRD_COUNTRY-to-EU pair has no rule ⇒ UNKNOWN."""
    result = classify_vat(
        _criteria(
            issuer_residency=IssuerResidency.EU_MEMBER,
            issuer_member_state=EUMemberState.DE,
            customer_residency=CustomerResidency.EU_MEMBER,
            customer_member_state=EUMemberState.FR,
            kind=TransactionKind.GOODS,
            direction=InvoiceDirection.ISSUED,
        )
    )
    assert result.category is VATCategory.UNKNOWN
    assert result.matched_rule_id == "R99_fallthrough"


def test_classify_vat_is_deterministic() -> None:
    """Same criteria ⇒ same rule + same category across N invocations."""
    criteria = _criteria()
    first = classify_vat(criteria)
    for _ in range(20):
        repeat = classify_vat(criteria)
        assert repeat.matched_rule_id == first.matched_rule_id
        assert repeat.category is first.category


def test_eu_member_residency_requires_member_state() -> None:
    """Constructing a criteria with EU_MEMBER but no state is a ValidationError."""
    with pytest.raises(ValueError, match=r"member_state|EU_MEMBER|residency"):
        VATClassificationCriteria(
            transaction_date=date(2025, 6, 15),
            issuer_residency=IssuerResidency.EU_MEMBER,
            customer_residency=CustomerResidency.ES_MAINLAND,
            customer_tax_status=CustomerTaxStatus.B2B_VAT_REGISTERED,
            kind=TransactionKind.GOODS,
            direction=InvoiceDirection.RECEIVED,
            issuer_member_state=None,
        )


def test_es_to_es_domestic_criteria_require_rate_tier() -> None:
    """ES-to-ES domestic GOODS / SERVICES criteria without rate_tier raise."""
    with pytest.raises(ValueError, match="rate_tier is required"):
        VATClassificationCriteria(
            transaction_date=date(2025, 6, 15),
            issuer_residency=IssuerResidency.ES_MAINLAND,
            customer_residency=CustomerResidency.ES_MAINLAND,
            customer_tax_status=CustomerTaxStatus.B2B_VAT_REGISTERED,
            kind=TransactionKind.GOODS,
            direction=InvoiceDirection.ISSUED,
            rate_tier=None,
        )


def test_es_to_es_reverse_charge_kind_does_not_require_rate_tier() -> None:
    """RC-kind transactions route through R01-R03, not R05 — rate_tier optional."""
    # Should NOT raise: construction RC routes to DOMESTIC_REVERSE_CHARGE.
    criteria = VATClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IssuerResidency.ES_MAINLAND,
        customer_residency=CustomerResidency.ES_MAINLAND,
        customer_tax_status=CustomerTaxStatus.B2B_VAT_REGISTERED,
        kind=TransactionKind.CONSTRUCTION_REVERSE_CHARGE,
        direction=InvoiceDirection.ISSUED,
        rate_tier=None,
    )
    result = classify_vat(criteria)
    assert result.matched_rule_id == "R01_construction_reverse_charge"


def test_es_to_es_immovable_property_does_not_require_rate_tier() -> None:
    """Immovable property routes to DOMESTIC_EXEMPT (R04) — rate_tier not needed."""
    criteria = VATClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IssuerResidency.ES_MAINLAND,
        customer_residency=CustomerResidency.ES_MAINLAND,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        kind=TransactionKind.IMMOVABLE_PROPERTY,
        direction=InvoiceDirection.ISSUED,
        rate_tier=None,
    )
    result = classify_vat(criteria)
    assert result.category is VATCategory.DOMESTIC_EXEMPT


def test_cross_border_criteria_do_not_require_rate_tier() -> None:
    """Non-ES-to-ES criteria never require rate_tier (classifier resolves it from substrate)."""
    # Should NOT raise: ES->DE intra-community supply doesn't need rate_tier.
    criteria = VATClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IssuerResidency.ES_MAINLAND,
        customer_residency=CustomerResidency.EU_MEMBER,
        customer_member_state=EUMemberState.DE,
        customer_tax_status=CustomerTaxStatus.B2B_VAT_REGISTERED,
        kind=TransactionKind.GOODS,
        direction=InvoiceDirection.ISSUED,
        rate_tier=None,
    )
    result = classify_vat(criteria)
    assert result.category is VATCategory.INTRA_COMMUNITY_SUPPLY


def test_classification_rate_resolution_uses_transaction_date() -> None:
    """The 2024 baseline lookup returns the 2024 rate record."""
    result = classify_vat(
        _criteria(
            transaction_date=date(2024, 6, 15),
            rate_tier=VATRateKind.GENERAL,
        )
    )
    assert result.rate is not None
    assert result.rate.effective_from == date(2024, 1, 1)
    assert result.rate.effective_until == date(2024, 12, 31)


def test_classification_rate_resolution_returns_none_for_export() -> None:
    """Exports carry no domestic rate; rate is None."""
    result = classify_vat(
        _criteria(
            customer_residency=CustomerResidency.THIRD_COUNTRY,
            kind=TransactionKind.GOODS,
            direction=InvoiceDirection.ISSUED,
        )
    )
    assert result.rate is None
