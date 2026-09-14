"""Unit tests for :func:`cadrumo.domain.iva.classify_iva`.

Walks the closed-table rules plus the R99 fallthrough, verifies the cross-field
``rate_tier`` requirements on
:class:`cadrumo.domain.iva.IvaInvoiceClassificationCriteria`, and checks that rate
resolution honours the transaction date.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.iva.classification import CustomerTaxStatus, IvaTerritorialScope, TransactionKind
from cadrumo.domain.iva.schema import IvaRateKind, require_eu_member_state

from ..classification import (
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    classify_iva,
)
from ..schema import IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _criteria(**overrides: object) -> IvaInvoiceClassificationCriteria:
    """Build a baseline ES-to-ES B2B goods ISSUED criteria with ``overrides`` applied."""
    base: dict[str, object] = {
        "transaction_date": date(2025, 6, 15),
        "issuer_residency": IvaTerritorialScope._from_registry("es_mainland"),
        "customer_residency": IvaTerritorialScope._from_registry("es_mainland"),
        "customer_tax_status": CustomerTaxStatus._from_registry("b2b_iva_registered"),
        "kind": TransactionKind("goods"),
        "direction": InvoiceKind.ISSUED,
        "rate_tier": IvaRateKind("general"),
    }
    base.update(overrides)
    return IvaInvoiceClassificationCriteria.model_validate(base)


_CLASSIFICATION_CASES = (
    (
        "r01-construction-reverse-charge",
        {"kind": TransactionKind("construction_reverse_charge")},
        IvaCategory("domestic_reverse_charge"),
        "R01_construction_reverse_charge",
        True,
        None,
    ),
    (
        "r02-waste-reverse-charge",
        {"kind": TransactionKind("waste_reverse_charge")},
        IvaCategory("domestic_reverse_charge"),
        "R02_waste_reverse_charge",
        None,
        None,
    ),
    (
        "r03-electronics-reverse-charge",
        {
            "kind": TransactionKind("electronics_reverse_charge"),
            "customer_tax_status": CustomerTaxStatus._from_registry("b2b_iva_registered"),
        },
        IvaCategory("domestic_reverse_charge"),
        "R03_electronics_reverse_charge",
        None,
        None,
    ),
    (
        "r04-immovable-b2c-exempt",
        {
            "kind": TransactionKind("immovable_property"),
            "customer_tax_status": CustomerTaxStatus._from_registry("b2c_consumer"),
        },
        IvaCategory("domestic_exempt"),
        "R04_immovable_property_exempt",
        None,
        None,
    ),
    (
        "r05-domestic-general-21",
        {"rate_tier": IvaRateKind("general")},
        IvaCategory("domestic_general"),
        "R05_domestic_at_rate_tier",
        None,
        Decimal("21"),
    ),
    (
        "r05-domestic-reduced-10",
        {"rate_tier": IvaRateKind("reduced")},
        IvaCategory("domestic_reduced"),
        None,
        None,
        Decimal("10"),
    ),
    (
        "r05-domestic-super-reduced-4",
        {"rate_tier": IvaRateKind("super_reduced")},
        IvaCategory("domestic_super_reduced"),
        None,
        None,
        Decimal("4"),
    ),
    (
        "r10-intra-community-supply-goods",
        {
            "customer_residency": IvaTerritorialScope._from_registry("eu_member"),
            "customer_identification_state": require_eu_member_state("DE"),
            "kind": TransactionKind("goods"),
            "direction": InvoiceKind.ISSUED,
        },
        IvaCategory("intra_community_supply"),
        "R10_intra_community_supply",
        None,
        None,
    ),
    (
        "r11-intra-community-acquisition-goods",
        {
            "issuer_residency": IvaTerritorialScope._from_registry("eu_member"),
            "issuer_identification_state": require_eu_member_state("DE"),
            "customer_residency": IvaTerritorialScope._from_registry("es_mainland"),
            "kind": TransactionKind("goods"),
            "direction": InvoiceKind.RECEIVED,
        },
        IvaCategory("intra_community_acquisition_reverse_charge"),
        None,
        True,
        None,
    ),
    (
        "r12-services-b2b-eu-outbound",
        {
            "customer_residency": IvaTerritorialScope._from_registry("eu_member"),
            "customer_identification_state": require_eu_member_state("FR"),
            "kind": TransactionKind("services_general"),
            "direction": InvoiceKind.ISSUED,
        },
        IvaCategory("domestic_not_subject"),
        "R12_services_b2b_eu_outbound",
        None,
        None,
    ),
    (
        "r13-services-b2b-eu-inbound",
        {
            "issuer_residency": IvaTerritorialScope._from_registry("eu_member"),
            "issuer_identification_state": require_eu_member_state("FR"),
            "customer_residency": IvaTerritorialScope._from_registry("es_mainland"),
            "kind": TransactionKind("services_general"),
            "direction": InvoiceKind.RECEIVED,
        },
        IvaCategory("intra_community_service_acquisition_reverse_charge"),
        "R13_services_b2b_eu_inbound",
        None,
        None,
    ),
    (
        "r19-oss-union-services",
        {
            "customer_residency": IvaTerritorialScope._from_registry("eu_member"),
            "customer_identification_state": require_eu_member_state("IT"),
            "customer_tax_status": CustomerTaxStatus._from_registry("b2c_consumer"),
            "kind": TransactionKind("oss_union_services"),
            "direction": InvoiceKind.ISSUED,
        },
        IvaCategory("domestic_not_subject"),
        "R19_oss_union_services",
        None,
        None,
    ),
    (
        "r20-export-goods",
        {
            "customer_residency": IvaTerritorialScope._from_registry("third_country"),
            "kind": TransactionKind("goods"),
            "direction": InvoiceKind.ISSUED,
        },
        IvaCategory("export_third_country_zero_rated"),
        "R20_export_goods",
        None,
        None,
    ),
    (
        "r21-import-goods",
        {
            "issuer_residency": IvaTerritorialScope._from_registry("third_country"),
            "customer_residency": IvaTerritorialScope._from_registry("es_mainland"),
            "kind": TransactionKind("goods"),
            "direction": InvoiceKind.RECEIVED,
        },
        IvaCategory("import_third_country"),
        None,
        None,
        None,
    ),
    (
        "r22-services-outbound-b2b",
        {
            "customer_residency": IvaTerritorialScope._from_registry("third_country"),
            "customer_tax_status": CustomerTaxStatus._from_registry("b2b_iva_registered"),
            "kind": TransactionKind("services_general"),
            "direction": InvoiceKind.ISSUED,
        },
        IvaCategory("operacion_no_sujeta"),
        "R22_services_outbound_b2b",
        None,
        None,
    ),
    (
        # The other limb of art. 69: 69.Uno.2.º places a B2C service at the
        # SUPPLIER, so a mainland issuer's is realizada in the TAI and taxed at
        # the Spanish rate rather than falling outside it.
        "r24-services-outbound-b2c",
        {
            "customer_residency": IvaTerritorialScope._from_registry("third_country"),
            "customer_tax_status": CustomerTaxStatus._from_registry("b2c_consumer"),
            "kind": TransactionKind("services_general"),
            "direction": InvoiceKind.ISSUED,
            "rate_tier": IvaRateKind("general"),
        },
        IvaCategory("domestic_general"),
        "R24_services_outbound_b2c_at_rate_tier",
        None,
        Decimal("21"),
    ),
    (
        "r30-canarias-issuer",
        {"issuer_residency": IvaTerritorialScope._from_registry("es_canarias")},
        IvaCategory("domestic_not_subject"),
        "R30_canarias_ceuta_melilla",
        None,
        None,
    ),
    (
        "r99-fallthrough",
        {
            "issuer_residency": IvaTerritorialScope._from_registry("eu_member"),
            "issuer_identification_state": require_eu_member_state("DE"),
            "customer_residency": IvaTerritorialScope._from_registry("eu_member"),
            "customer_identification_state": require_eu_member_state("FR"),
            "kind": TransactionKind("goods"),
            "direction": InvoiceKind.ISSUED,
        },
        IvaCategory("unknown"),
        "R99_fallthrough",
        None,
        None,
    ),
)


def test_classification_rule_cases() -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        for (
            case_id,
            overrides,
            expected_category,
            expected_rule_id,
            expected_reverse_charge,
            expected_rate_pct,
        ) in _CLASSIFICATION_CASES:
            result = classify_iva(_criteria(**overrides), operation=_authority_operation_for_test)
            assert result.category == expected_category, case_id
            if expected_rule_id is not None:
                assert result.matched_rule_id == expected_rule_id, case_id
            if expected_reverse_charge is not None:
                assert result.requires_reverse_charge is expected_reverse_charge, case_id
            if expected_rate_pct is not None:
                assert result.rate is not None, case_id
                assert result.rate.pct == expected_rate_pct, case_id


def test_r03_electronics_b2c_does_not_trigger_reverse_charge() -> None:
    """Electronics RC requires B2B; a B2C consumer falls through to R05."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        result = classify_iva(
            _criteria(
                kind=TransactionKind("electronics_reverse_charge"),
                customer_tax_status=CustomerTaxStatus._from_registry("b2c_consumer"),
            ),
            operation=_authority_operation_for_test,
        )
        assert result.matched_rule_id != "R03_electronics_reverse_charge"


def test_classify_iva_is_deterministic() -> None:
    """Same criteria ⇒ same rule + same category across N invocations."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        criteria = _criteria()
        first = classify_iva(criteria, operation=_authority_operation_for_test)
        for _ in range(20):
            repeat = classify_iva(criteria, operation=_authority_operation_for_test)
            assert repeat.matched_rule_id == first.matched_rule_id
            assert repeat.category == first.category


def test_eu_member_residency_does_not_require_an_identification_state() -> None:
    """An establishment abroad is not a claim about where the party is registered.

    This construction used to raise, and the requirement was the conflation:
    "established in another Member State" was read as "name the State that
    registered it", which is the same inference that made a German prefix
    establish a German place. Which branches genuinely need the identifying
    State is declared by the branches, and the producer demands it there.
    """
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope._from_registry("eu_member"),
        customer_residency=IvaTerritorialScope._from_registry("es_mainland"),
        customer_tax_status=CustomerTaxStatus._from_registry("b2b_iva_registered"),
        kind=TransactionKind("goods"),
        direction=InvoiceKind.RECEIVED,
        issuer_identification_state=None,
    )
    assert criteria.issuer_identification_state is None
    assert criteria.issuer_residency == IvaTerritorialScope._from_registry("eu_member")


def test_es_to_es_domestic_criteria_require_rate_tier() -> None:
    """ES-to-ES domestic GOODS / SERVICES criteria without rate_tier raise."""
    with pytest.raises(ValueError, match="rate_tier is required"):
        IvaInvoiceClassificationCriteria(
            transaction_date=date(2025, 6, 15),
            issuer_residency=IvaTerritorialScope._from_registry("es_mainland"),
            customer_residency=IvaTerritorialScope._from_registry("es_mainland"),
            customer_tax_status=CustomerTaxStatus._from_registry("b2b_iva_registered"),
            kind=TransactionKind("goods"),
            direction=InvoiceKind.ISSUED,
            rate_tier=None,
        )


def test_es_to_es_reverse_charge_kind_does_not_require_rate_tier() -> None:
    """RC-kind transactions route through R01-R03, not R05 — rate_tier optional."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        # Should NOT raise: construction RC routes to DOMESTIC_REVERSE_CHARGE.
        criteria = IvaInvoiceClassificationCriteria(
            transaction_date=date(2025, 6, 15),
            issuer_residency=IvaTerritorialScope._from_registry("es_mainland"),
            customer_residency=IvaTerritorialScope._from_registry("es_mainland"),
            customer_tax_status=CustomerTaxStatus._from_registry("b2b_iva_registered"),
            kind=TransactionKind("construction_reverse_charge"),
            direction=InvoiceKind.ISSUED,
            rate_tier=None,
        )
        result = classify_iva(criteria, operation=_authority_operation_for_test)
        assert result.matched_rule_id == "R01_construction_reverse_charge"


def test_es_to_es_immovable_property_does_not_require_rate_tier() -> None:
    """Immovable property routes to DOMESTIC_EXEMPT (R04) — rate_tier not needed."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        criteria = IvaInvoiceClassificationCriteria(
            transaction_date=date(2025, 6, 15),
            issuer_residency=IvaTerritorialScope._from_registry("es_mainland"),
            customer_residency=IvaTerritorialScope._from_registry("es_mainland"),
            customer_tax_status=CustomerTaxStatus._from_registry("b2c_consumer"),
            kind=TransactionKind("immovable_property"),
            direction=InvoiceKind.ISSUED,
            rate_tier=None,
        )
        result = classify_iva(criteria, operation=_authority_operation_for_test)
        assert result.category == IvaCategory("domestic_exempt")


def test_cross_border_criteria_do_not_require_rate_tier() -> None:
    """Non-ES-to-ES criteria never require rate_tier (classifier resolves it from substrate)."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        # Should NOT raise: ES->DE intra-community supply doesn't need rate_tier.
        criteria = IvaInvoiceClassificationCriteria(
            transaction_date=date(2025, 6, 15),
            issuer_residency=IvaTerritorialScope._from_registry("es_mainland"),
            customer_residency=IvaTerritorialScope._from_registry("eu_member"),
            customer_identification_state=require_eu_member_state("DE"),
            customer_tax_status=CustomerTaxStatus._from_registry("b2b_iva_registered"),
            kind=TransactionKind("goods"),
            direction=InvoiceKind.ISSUED,
            rate_tier=None,
        )
        result = classify_iva(criteria, operation=_authority_operation_for_test)
        assert result.category == IvaCategory("intra_community_supply")


def test_classification_rate_resolution_uses_transaction_date() -> None:
    """Two dates in different windows resolve DIFFERENT records.

    Asserts the property rather than one record's bounds. The previous version
    pinned ``effective_from == 2024-01-01``, which was a bulk-refresh boundary
    the table mistook for legal effect; when that was corrected to the statutory
    2012-09-01 the test failed for a reason that had nothing to do with
    classification. Comparing two windows tests what this function actually does
    -- pick by transaction date -- and survives any later correction to either
    window's edges.
    """
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        earlier = classify_iva(
            _criteria(transaction_date=date(2024, 6, 15), rate_tier=IvaRateKind("general")),
            operation=_authority_operation_for_test,
        )
        later = classify_iva(
            _criteria(transaction_date=date(2025, 6, 15), rate_tier=IvaRateKind("general")),
            operation=_authority_operation_for_test,
        )

        assert earlier.rate is not None
        assert later.rate is not None
        assert earlier.rate.effective_from != later.rate.effective_from
        assert earlier.rate.effective_until == date(2024, 12, 31)
        assert later.rate.effective_until is None
        # Same tier, same value, different record: the date is what discriminates.
        assert earlier.rate.pct == later.rate.pct


def test_classification_rate_resolution_returns_none_for_export() -> None:
    """Exports carry no domestic rate; rate is None."""
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        result = classify_iva(
            _criteria(
                customer_residency=IvaTerritorialScope._from_registry("third_country"),
                kind=TransactionKind("goods"),
                direction=InvoiceKind.ISSUED,
            ),
            operation=_authority_operation_for_test,
        )
        assert result.rate is None
