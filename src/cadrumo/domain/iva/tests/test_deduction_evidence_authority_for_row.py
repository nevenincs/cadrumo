"""Held-back deduction rows name the authority required by the governed catalogue."""

from __future__ import annotations

import pytest

from ....core.iva_deduction_fact import IvaDeductionFactKind
from ..deduction_facts import deduction_evidence_authority_for_row
from ..schema import IvaCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]


@pytest.mark.parametrize(
    ("kind", "authority"),
    [
        ("domestic_current", "invoice_evidence"),
        ("domestic_investment", "invoice_evidence"),
        ("import_current", "customs_declaration"),
        ("import_investment", "customs_declaration"),
        ("intra_eu_current", "intra_eu_self_assessment"),
        ("intra_eu_investment", "intra_eu_self_assessment"),
        ("reagp_compensation", "reagp_receipt"),
        ("rectification", "rectification_evidence"),
        ("investment_goods_regularisation", "bienes_inversion_register"),
    ],
)
def test_a_declared_kind_keeps_its_required_authority_even_when_the_category_disagrees(
    kind: str, authority: str
) -> None:
    found = deduction_evidence_authority_for_row(
        kind=IvaDeductionFactKind.from_registry(kind), category=IvaCategory("domestic_general")
    )
    assert found is not None
    assert found.value == authority


@pytest.mark.parametrize(
    ("category", "authority"),
    [
        ("domestic_general", "invoice_evidence"),
        ("intra_community_acquisition_reverse_charge", "intra_eu_self_assessment"),
        ("intra_community_service_acquisition_reverse_charge", "intra_eu_self_assessment"),
        ("import_third_country", "customs_declaration"),
        ("reagp_compensation", "reagp_receipt"),
    ],
)
def test_an_undeclared_kind_is_resolved_only_by_a_unanimous_registry_category_family(
    category: str, authority: str
) -> None:
    found = deduction_evidence_authority_for_row(kind=None, category=IvaCategory(category))
    assert found is not None
    assert found.value == authority


@pytest.mark.parametrize("category", [None, "domestic_exempt", "domestic_not_subject", "export"])
def test_a_category_without_a_deduction_family_does_not_guess_a_supporting_document(category: str | None) -> None:
    assert (
        deduction_evidence_authority_for_row(kind=None, category=None if category is None else IvaCategory(category))
        is None
    )
