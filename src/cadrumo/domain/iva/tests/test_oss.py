"""Tests for the OSS / IOSS regime substrate."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.iva.classification import CustomerTaxStatus, IvaTerritorialScope, TransactionKind
from cadrumo.domain.iva.schema import require_eu_member_state

from ..classification import (
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    classify_iva,
)
from ..oss import OssIossRegime
from ..schema import IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_oss_ioss_regime_enum_covers_all_three_esquemas() -> None:
    assert {r for r in OssIossRegime} == {
        OssIossRegime("external_scheme"),
        OssIossRegime("union_scheme"),
        OssIossRegime("import_scheme"),
    }


def test_oss_ioss_regime_string_values_match_registry_selector_keys() -> None:
    assert OssIossRegime("external_scheme").value == "external_scheme"
    assert OssIossRegime("union_scheme").value == "union_scheme"
    assert OssIossRegime("import_scheme").value == "import_scheme"


def test_classifier_routes_oss_union_goods_distance_sale_to_r17() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope._from_registry("es_mainland"),
        customer_residency=IvaTerritorialScope._from_registry("eu_member"),
        customer_identification_state=require_eu_member_state("DE"),
        customer_tax_status=CustomerTaxStatus._from_registry("b2c_consumer"),
        kind=TransactionKind("oss_union_goods_distance_sale"),
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R17_oss_union_goods_distance_sale"
    assert result.category == IvaCategory("domestic_not_subject")


def test_classifier_routes_oss_union_goods_interface_facilitated_to_r18() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope._from_registry("es_mainland"),
        customer_residency=IvaTerritorialScope._from_registry("eu_member"),
        customer_identification_state=require_eu_member_state("FR"),
        customer_tax_status=CustomerTaxStatus._from_registry("b2c_consumer"),
        kind=TransactionKind("oss_union_goods_interface_facilitated"),
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R18_oss_union_goods_interface_facilitated"
    assert result.category == IvaCategory("domestic_not_subject")


def test_classifier_routes_oss_union_services_to_r19() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope._from_registry("es_mainland"),
        customer_residency=IvaTerritorialScope._from_registry("eu_member"),
        customer_identification_state=require_eu_member_state("IT"),
        customer_tax_status=CustomerTaxStatus._from_registry("b2c_consumer"),
        kind=TransactionKind("oss_union_services"),
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R19_oss_union_services"
    assert result.category == IvaCategory("domestic_not_subject")


def test_classifier_routes_external_scheme_services_to_r16() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope._from_registry("third_country"),
        customer_residency=IvaTerritorialScope._from_registry("eu_member"),
        customer_identification_state=require_eu_member_state("ES"),
        customer_tax_status=CustomerTaxStatus._from_registry("b2c_consumer"),
        kind=TransactionKind("external_scheme_services"),
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R16_external_scheme_services"
    assert result.category == IvaCategory("operacion_no_sujeta")


def test_classifier_routes_ioss_low_value_distance_sale_to_r23() -> None:
    criteria = IvaInvoiceClassificationCriteria(
        transaction_date=date(2025, 6, 15),
        issuer_residency=IvaTerritorialScope._from_registry("es_mainland"),
        customer_residency=IvaTerritorialScope._from_registry("eu_member"),
        customer_identification_state=require_eu_member_state("DE"),
        customer_tax_status=CustomerTaxStatus._from_registry("b2c_consumer"),
        kind=TransactionKind("ioss_distance_sale_low_value"),
        direction=InvoiceKind.ISSUED,
    )
    result = classify_iva(criteria)
    assert result.matched_rule_id == "R23_ioss_distance_sale_low_value"
    assert result.category == IvaCategory("operacion_no_sujeta")


def test_classifier_rejects_retired_digital_b2c_oss_alias() -> None:
    with pytest.raises(ValueError, match="services_digital_b2c_oss"):
        IvaInvoiceClassificationCriteria.model_validate(
            {
                "transaction_date": date(2025, 6, 15),
                "issuer_residency": IvaTerritorialScope._from_registry("es_mainland"),
                "customer_residency": IvaTerritorialScope._from_registry("eu_member"),
                "customer_identification_state": require_eu_member_state("DE"),
                "customer_tax_status": CustomerTaxStatus._from_registry("b2c_consumer"),
                "kind": "services_digital_b2c_oss",
                "direction": InvoiceKind.ISSUED,
            },
        )
