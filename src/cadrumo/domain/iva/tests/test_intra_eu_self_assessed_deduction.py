"""Which held-back rows rest on an intra-EU self-assessment is fact 0085's answer.

Verification tells a filer that an intra-EU acquisition cannot pass the check,
because the self-assessment its deduction rests on is a document no ledger write
records. The generic authority query decides which rows get that refusal:
a declared kind answers by its authority, an undeclared one by its category.

The last test is the teeth. It derives the answer for every declared kind from a
different fact-0085 declaration, the required evidence authority, and asserts
the two agree, so moving a kind between families without moving its authority
cannot pass unnoticed.
"""

from __future__ import annotations

import pytest

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ...calculations.registry.iva_deduction_catalogue import (
    iva_deduction_fact_kinds,
    resolve_iva_deduction_catalogue,
)
from ..deduction_facts import deduction_evidence_authority_for_row
from ..schema import IvaCategory

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
    ) == IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")


@pytest.mark.parametrize("kind", ["domestic_current", "domestic_investment", "import_current", "rectification"])
def test_a_declared_kind_of_another_family_does_not(kind: str) -> None:
    """The declared kind wins over the category: a rectification on an intra-EU row is not the family's."""
    assert deduction_evidence_authority_for_row(
        kind=IvaDeductionFactKind.from_registry(kind),
        category=IvaCategory(_INTRA_EU_CATEGORIES[0]),
    ) != IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")


@pytest.mark.parametrize("category", _INTRA_EU_CATEGORIES)
def test_an_undeclared_kind_on_an_intra_eu_category_rests_on_the_self_assessment(category: str) -> None:
    assert deduction_evidence_authority_for_row(
        kind=None, category=IvaCategory(category)
    ) == IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")


@pytest.mark.parametrize("category", ["domestic_general", "import_third_country", "domestic_reverse_charge", None])
def test_an_undeclared_kind_on_any_other_category_does_not(category: str | None) -> None:
    assert deduction_evidence_authority_for_row(
        kind=None,
        category=None if category is None else IvaCategory(category),
    ) != IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")


def test_the_family_answer_matches_the_required_evidence_authority() -> None:
    """Every kind the self-assessment establishes is in the family, and no other kind is."""
    self_assessment = IvaDeductionEvidenceAuthority.from_registry("intra_eu_self_assessment")
    kinds = iva_deduction_fact_kinds()
    assert kinds

    for kind in kinds:
        assert (deduction_evidence_authority_for_row(kind=kind, category=None) == self_assessment) == (
            kind in resolve_iva_deduction_catalogue().projection("kind.intra_eu")
        ), kind
