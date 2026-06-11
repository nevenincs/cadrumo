"""Unit tests for :func:`aeat.domain.iva.classify_iva`.

Walks every closed-table rule (R01 through R30) plus the R99 fallthrough,
verifies the cross-field ``rate_tier`` requirements on
:class:`aeat.domain.iva.IvaInvoiceClassificationCriteria`, and checks that rate
resolution honours the transaction date.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .. import (
    CustomerTaxStatus,
    EUMemberState,
    InvoiceKind,
    IvaCategory,
    IvaInvoiceClassificationCriteria,
    IvaRateKind,
    IvaTerritorialScope,
    TransactionKind,
    classify_iva,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _criteria(**overrides: object) -> IvaInvoiceClassificationCriteria:
    """Build a baseline ES-to-ES B2B goods ISSUED criteria with ``overrides`` applied."""
    base: dict[str, object] = {
        "transaction_date": date(2025, 6, 15),
        "issuer_residency": IvaTerritorialScope.ES_MAINLAND,
        "customer_residency": IvaTerritorialScope.ES_MAINLAND,
        "customer_tax_status": CustomerTaxStatus.B2B_IVA_REGISTERED,
        "kind": TransactionKind.GOODS,
        "direction": InvoiceKind.ISSUED,
        "rate_tier": IvaRateKind.GENERAL,
    }
    base.update(overrides)
    return IvaInvoiceClassificationCriteria.model_validate(base)


def test_r01_construction_reverse_charge() -> None:
    result = classify_iva(_criteria(kind=TransactionKind.CONSTRUCTION_REVERSE_CHARGE))
    assert result.category is IvaCategory.DOMESTIC_REVERSE_CHARGE
    assert result.requires_reverse_charge is True
    assert result.matched_rule_id == "R01_construction_reverse_charge"


def test_r02_waste_reverse_charge() -> None:
    result = classify_iva(_criteria(kind=TransactionKind.WASTE_REVERSE_CHARGE))
    assert result.category is IvaCategory.DOMESTIC_REVERSE_CHARGE
    assert result.matched_rule_id == "R02_waste_reverse_charge"


def test_r03_electronics_reverse_charge() -> None:
    result = classify_iva(
        _criteria(
            kind=TransactionKind.ELECTRONICS_REVERSE_CHARGE,
            customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
        ),
    )
    assert result.category is IvaCategory.DOMESTIC_REVERSE_CHARGE
    assert result.matched_rule_id == "R03_electronics_reverse_charge"


def test_r03_electronics_b2c_does_not_trigger_reverse_charge() -> None:
    """Electronics RC requires B2B; a B2C consumer falls through to R05."""
    result = classify_iva(
        _criteria(
            kind=TransactionKind.ELECTRONICS_REVERSE_CHARGE,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        ),
    )
    assert result.matched_rule_id != "R03_electronics_reverse_charge"


def test_r04_immovable_b2c_exempt() -> None:
    result = classify_iva(
        _criteria(
            kind=TransactionKind.IMMOVABLE_PROPERTY,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        ),
    )
    assert result.category is IvaCategory.DOMESTIC_EXEMPT
    assert result.matched_rule_id == "R04_immovable_property_exempt"


def test_r05_domestic_general_21() -> None:
    result = classify_iva(_criteria(rate_tier=IvaRateKind.GENERAL))
    assert result.category is IvaCategory.DOMESTIC_GENERAL_21
    assert result.matched_rule_id == "R05_domestic_at_rate_tier"
    assert result.rate is not None
    assert result.rate.pct == Decimal("21")


def test_r05_domestic_reduced_10() -> None:
    result = classify_iva(_criteria(rate_tier=IvaRateKind.REDUCED))
    assert result.category is IvaCategory.DOMESTIC_REDUCED_10
    assert result.rate is not None
    assert result.rate.pct == Decimal("10")


def test_r05_domestic_super_reduced_4() -> None:
    result = classify_iva(_criteria(rate_tier=IvaRateKind.SUPER_REDUCED))
    assert result.category is IvaCategory.DOMESTIC_SUPER_REDUCED_4
    assert result.rate is not None
    assert result.rate.pct == Decimal("4")


def test_r10_intra_community_supply_goods() -> None:
    result = classify_iva(
        _criteria(
            customer_residency=IvaTerritorialScope.EU_MEMBER,
            customer_member_state=EUMemberState.DE,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.ISSUED,
        ),
    )
    assert result.category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert result.matched_rule_id == "R10_intra_community_supply"


def test_r11_intra_community_acquisition_goods() -> None:
    result = classify_iva(
        _criteria(
            issuer_residency=IvaTerritorialScope.EU_MEMBER,
            issuer_member_state=EUMemberState.DE,
            customer_residency=IvaTerritorialScope.ES_MAINLAND,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.RECEIVED,
        ),
    )
    assert result.category is IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
    assert result.requires_reverse_charge is True


def test_r12_services_b2b_eu_outbound_is_not_subject_in_es() -> None:
    result = classify_iva(
        _criteria(
            customer_residency=IvaTerritorialScope.EU_MEMBER,
            customer_member_state=EUMemberState.FR,
            kind=TransactionKind.SERVICES_GENERAL,
            direction=InvoiceKind.ISSUED,
        ),
    )
    assert result.category is IvaCategory.DOMESTIC_NOT_SUBJECT
    assert result.matched_rule_id == "R12_services_b2b_eu_outbound"


def test_r13_services_b2b_eu_inbound_reverse_charge() -> None:
    result = classify_iva(
        _criteria(
            issuer_residency=IvaTerritorialScope.EU_MEMBER,
            issuer_member_state=EUMemberState.FR,
            customer_residency=IvaTerritorialScope.ES_MAINLAND,
            kind=TransactionKind.SERVICES_GENERAL,
            direction=InvoiceKind.RECEIVED,
        ),
    )
    assert result.category is IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE
    assert result.matched_rule_id == "R13_services_b2b_eu_inbound"


def test_r14_digital_b2c_oss() -> None:
    result = classify_iva(
        _criteria(
            customer_residency=IvaTerritorialScope.EU_MEMBER,
            customer_member_state=EUMemberState.IT,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
            kind=TransactionKind.SERVICES_DIGITAL_B2C_OSS,
            direction=InvoiceKind.ISSUED,
        ),
    )
    assert result.category is IvaCategory.DOMESTIC_NOT_SUBJECT
    assert result.matched_rule_id == "R14_digital_b2c_oss"


def test_r20_export_goods() -> None:
    result = classify_iva(
        _criteria(
            customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.ISSUED,
        ),
    )
    assert result.category is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED
    assert result.matched_rule_id == "R20_export_goods"


def test_r21_import_goods() -> None:
    result = classify_iva(
        _criteria(
            issuer_residency=IvaTerritorialScope.THIRD_COUNTRY,
            customer_residency=IvaTerritorialScope.ES_MAINLAND,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.RECEIVED,
        ),
    )
    assert result.category is IvaCategory.IMPORT_THIRD_COUNTRY


def test_r22_services_outbound_third_country() -> None:
    result = classify_iva(
        _criteria(
            customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
            kind=TransactionKind.SERVICES_GENERAL,
            direction=InvoiceKind.ISSUED,
        ),
    )
    assert result.category is IvaCategory.OPERACION_NO_SUJETA
    assert result.matched_rule_id == "R22_services_outbound_third_country"


def test_r30_canarias_issuer_short_circuits_to_not_subject() -> None:
    result = classify_iva(_criteria(issuer_residency=IvaTerritorialScope.ES_CANARIAS))
    assert result.category is IvaCategory.DOMESTIC_NOT_SUBJECT
    assert result.matched_rule_id == "R30_canarias_ceuta_melilla"


def test_r99_fallthrough_returns_unknown() -> None:
    """A non-matching THIRD_COUNTRY-to-EU pair has no rule ⇒ UNKNOWN."""
    result = classify_iva(
        _criteria(
            issuer_residency=IvaTerritorialScope.EU_MEMBER,
            issuer_member_state=EUMemberState.DE,
            customer_residency=IvaTerritorialScope.EU_MEMBER,
            customer_member_state=EUMemberState.FR,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.ISSUED,
        ),
    )
    assert result.category is IvaCategory.UNKNOWN
    assert result.matched_rule_id == "R99_fallthrough"


def test_classify_iva_is_deterministic() -> None:
    """Same criteria ⇒ same rule + same category across N invocations."""
    criteria = _criteria()
    first = classify_iva(criteria)
    for _ in range(20):
        repeat = classify_iva(criteria)
        assert repeat.matched_rule_id == first.matched_rule_id
        assert repeat.category is first.category


def test_eu_member_residency_requires_member_state() -> None:
    """Constructing a criteria with EU_MEMBER but no state is a ValidationError."""
    with pytest.raises(ValueError, match=r"member_state|EU_MEMBER|residency"):
        IvaInvoiceClassificationCriteria(
            transaction_date=date(2025, 6, 15),
            issuer_residency=IvaTerritorialScope.EU_MEMBER,
            customer_residency=IvaTerritorialScope.ES_MAINLAND,
            customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.RECEIVED,
            issuer_member_state=None,
        )


def test_es_to_es_domestic_criteria_require_rate_tier() -> None:
    """ES-to-ES domestic GOODS / SERVICES criteria without rate_tier raise."""
    with pytest.raises(ValueError, match="rate_tier is required"):
        IvaInvoiceClassificationCriteria(
            transaction_date=date(2025, 6, 15),
            issuer_residency=IvaTerritorialScope.ES_MAINLAND,
            customer_residency=IvaTerritorialScope.ES_MAINLAND,
            customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.ISSUED,
            rate_tier=None,
        )


def test_es_to_es_reverse_charge_kind_does_not_require_rate_tier() -> None:
    """RC-kind transactions route through R01-R03, not R05 — rate_tier optional."""
    # Should NOT raise: construction RC routes to DOMESTIC_REVERSE_CHARGE.
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
        kind=TransactionKind.CONSTRUCTION_REVERSE_CHARGE,
        direction=InvoiceKind.ISSUED,
        rate_tier=None,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R01_construction_reverse_charge"


def test_es_to_es_immovable_property_does_not_require_rate_tier() -> None:
    """Immovable property routes to DOMESTIC_EXEMPT (R04) — rate_tier not needed."""
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        kind=TransactionKind.IMMOVABLE_PROPERTY,
        direction=InvoiceKind.ISSUED,
        rate_tier=None,
    )
    result = classify_iva(criteria)
    assert result.category is IvaCategory.DOMESTIC_EXEMPT


def test_cross_border_criteria_do_not_require_rate_tier() -> None:
    """Non-ES-to-ES criteria never require rate_tier (classifier resolves it from substrate)."""
    # Should NOT raise: ES->DE intra-community supply doesn't need rate_tier.
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.EU_MEMBER,
        customer_member_state=EUMemberState.DE,
        customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
        kind=TransactionKind.GOODS,
        direction=InvoiceKind.ISSUED,
        rate_tier=None,
    )
    result = classify_iva(criteria)
    assert result.category is IvaCategory.INTRA_COMMUNITY_SUPPLY


def test_classification_rate_resolution_uses_transaction_date() -> None:
    """The 2024 baseline lookup returns the 2024 rate record."""
    result = classify_iva(
        _criteria(
            transaction_date=date(2024, 6, 15),
            rate_tier=IvaRateKind.GENERAL,
        ),
    )
    assert result.rate is not None
    assert result.rate.effective_from == date(2024, 1, 1)
    assert result.rate.effective_until == date(2024, 12, 31)


def test_classification_rate_resolution_returns_none_for_export() -> None:
    """Exports carry no domestic rate; rate is None."""
    result = classify_iva(
        _criteria(
            customer_residency=IvaTerritorialScope.THIRD_COUNTRY,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.ISSUED,
        ),
    )
    assert result.rate is None
