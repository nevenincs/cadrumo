"""Which held-back rows rest on an intra-EU self-assessment is fact 0085's answer.

Verification names the authority a held-back row's deduction rests on, and the
ledger stamps a row's evidence under that authority. The generic authority query
answers it: a declared kind by its authority, an undeclared one by its category.

The last test is the teeth. It derives the answer for every declared kind from a
different fact-0085 declaration, the required evidence authority, and asserts
the two agree, so moving a kind between families without moving its authority
cannot pass unnoticed.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ...calculations.registry.iva_deduction_catalogue import (
    iva_deduction_fact_kinds,
    resolve_iva_deduction_catalogue,
)
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..deduction_facts import deduction_evidence_authority_for_row, supplier_invoice_deduction_authority
from ..schema import IvaCategory

_ON_DATE = date(filing_year_envelope().horizon, 6, 15)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_INTRA_EU_CATEGORIES = (
    "intra_community_acquisition_reverse_charge",
    "intra_community_service_acquisition_reverse_charge",
)


@pytest.mark.parametrize("kind", ["intra_eu_current", "intra_eu_investment"])
def test_a_declared_intra_eu_kind_rests_on_the_self_assessment(kind: str) -> None:
    assert deduction_evidence_authority_for_row(
        kind=IvaDeductionFactKind.from_registry(kind),
        category=IvaCategory("domestic_general"),
        effective_date=_ON_DATE,
    ) == IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")


@pytest.mark.parametrize("kind", ["domestic_current", "domestic_investment", "import_current", "rectification"])
def test_a_declared_kind_of_another_family_does_not(kind: str) -> None:
    """The declared kind wins over the category: a rectification on an intra-EU row is not the family's."""
    assert deduction_evidence_authority_for_row(
        kind=IvaDeductionFactKind.from_registry(kind),
        category=IvaCategory(_INTRA_EU_CATEGORIES[0]),
        effective_date=_ON_DATE,
    ) != IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")


@pytest.mark.parametrize("category", _INTRA_EU_CATEGORIES)
def test_an_undeclared_kind_on_an_intra_eu_category_rests_on_the_self_assessment(category: str) -> None:
    assert deduction_evidence_authority_for_row(
        kind=None, category=IvaCategory(category), effective_date=_ON_DATE
    ) == IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")


@pytest.mark.parametrize("category", ["domestic_general", "import_third_country", "domestic_reverse_charge", None])
def test_an_undeclared_kind_on_any_other_category_does_not(category: str | None) -> None:
    assert deduction_evidence_authority_for_row(
        kind=None,
        category=None if category is None else IvaCategory(category),
        effective_date=_ON_DATE,
    ) != IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")


def test_the_family_answer_matches_the_required_evidence_authority() -> None:
    """Every kind the self-assessment establishes is in the family, and no other kind is."""
    self_assessment = IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")
    kinds = iva_deduction_fact_kinds()
    assert kinds

    for kind in kinds:
        assert (
            deduction_evidence_authority_for_row(kind=kind, category=None, effective_date=_ON_DATE) == self_assessment
        ) == (kind in resolve_iva_deduction_catalogue().projection("kind.intra_eu")), kind


@pytest.mark.parametrize("kind", ["intra_eu_current", "intra_eu_investment"])
def test_the_supplier_invoice_justifies_an_intra_eu_deduction_under_the_self_assessment(kind: str) -> None:
    """LIVA art. 97.Uno.2.º and 4.º: the supplier's invoice, the cuota consigned in the buyer's own return."""
    assert supplier_invoice_deduction_authority(
        IvaDeductionFactKind.from_registry(kind), effective_date=_ON_DATE
    ) == IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")


@pytest.mark.parametrize("kind", ["domestic_current", "domestic_investment"])
def test_the_supplier_invoice_justifies_a_domestic_deduction_as_invoice_evidence(kind: str) -> None:
    """LIVA art. 97.Uno.1.º."""
    assert supplier_invoice_deduction_authority(
        IvaDeductionFactKind.from_registry(kind), effective_date=_ON_DATE
    ) == IvaDeductionEvidenceAuthority.from_registry("invoice_evidence")


@pytest.mark.parametrize(
    "kind",
    ["import_current", "import_investment", "reagp_compensation", "rectification", "investment_goods_regularisation"],
)
def test_the_supplier_invoice_justifies_no_deduction_another_document_establishes(kind: str) -> None:
    """The customs liquidation (3.º), the REAGP receipt (5.º), the rectifying document and the register."""
    assert (
        supplier_invoice_deduction_authority(IvaDeductionFactKind.from_registry(kind), effective_date=_ON_DATE) is None
    )


def test_the_supplier_invoice_answer_is_the_kind_s_required_authority_or_nothing() -> None:
    """Whatever the invoice justifies, it justifies under the authority fact 0085 requires of the kind."""
    catalogue = resolve_iva_deduction_catalogue()
    justified = [
        kind
        for kind in catalogue.kinds
        if supplier_invoice_deduction_authority(kind, effective_date=_ON_DATE) is not None
    ]

    assert justified
    for kind in justified:
        assert supplier_invoice_deduction_authority(kind, effective_date=_ON_DATE) == catalogue.required_authority(
            kind
        ), kind
