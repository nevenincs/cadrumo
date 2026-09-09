"""Tests for the OSS / IOSS regime substrate."""

from __future__ import annotations

from datetime import date

import pytest

from ..classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    TransactionKind,
    classify_iva,
)
from ..oss import OssIossRegime
from ..schema import EUMemberState, IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_oss_ioss_regime_enum_covers_all_three_esquemas() -> None:
    assert {r for r in OssIossRegime} == {
        OssIossRegime.EXTERNAL_SCHEME,
        OssIossRegime.UNION_SCHEME,
        OssIossRegime.IMPORT_SCHEME,
    }


def test_oss_ioss_regime_string_values_match_registry_selector_keys() -> None:
    assert OssIossRegime.EXTERNAL_SCHEME.value == "external_scheme"
    assert OssIossRegime.UNION_SCHEME.value == "union_scheme"
    assert OssIossRegime.IMPORT_SCHEME.value == "import_scheme"


def test_classifier_routes_oss_union_goods_distance_sale_to_r17() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.EU_MEMBER,
        customer_identification_state=EUMemberState.DE,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R17_oss_union_goods_distance_sale"
    assert result.category is IvaCategory.DOMESTIC_NOT_SUBJECT


def test_classifier_routes_oss_union_goods_interface_facilitated_to_r18() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.EU_MEMBER,
        customer_identification_state=EUMemberState.FR,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        kind=TransactionKind.OSS_UNION_GOODS_INTERFACE_FACILITATED,
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R18_oss_union_goods_interface_facilitated"
    assert result.category is IvaCategory.DOMESTIC_NOT_SUBJECT


def test_classifier_routes_oss_union_services_to_r19() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.EU_MEMBER,
        customer_identification_state=EUMemberState.IT,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        kind=TransactionKind.OSS_UNION_SERVICES,
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R19_oss_union_services"
    assert result.category is IvaCategory.DOMESTIC_NOT_SUBJECT


def test_classifier_routes_external_scheme_services_to_r16() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope.THIRD_COUNTRY,
        customer_residency=IvaTerritorialScope.EU_MEMBER,
        customer_identification_state=EUMemberState.ES,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        kind=TransactionKind.EXTERNAL_SCHEME_SERVICES,
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R16_external_scheme_services"
    assert result.category is IvaCategory.OPERACION_NO_SUJETA


def test_classifier_routes_ioss_low_value_distance_sale_to_r23() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.EU_MEMBER,
        customer_identification_state=EUMemberState.DE,
        customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
        kind=TransactionKind.IOSS_DISTANCE_SALE_LOW_VALUE,
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R23_ioss_distance_sale_low_value"
    assert result.category is IvaCategory.OPERACION_NO_SUJETA


def test_classifier_rejects_retired_digital_b2c_oss_alias() -> None:
    with pytest.raises(ValueError, match="services_digital_b2c_oss"):
        IvaInvoiceClassificationCriteria.model_validate(
            {
                "transaction_date": date(2025, 6, 15),
                "issuer_residency": IvaTerritorialScope.ES_MAINLAND,
                "customer_residency": IvaTerritorialScope.EU_MEMBER,
                "customer_identification_state": EUMemberState.DE,
                "customer_tax_status": CustomerTaxStatus.B2C_CONSUMER,
                "kind": "services_digital_b2c_oss",
                "direction": InvoiceKind.ISSUED,
            },
        )
