"""An unassigned country code must reach the review gate, never a zero-rated category.

The domain gate proves the resolver refuses. This file proves the refusal reaches
the place it has to reach, because a narrowed authority whose consumers had
already cached the old answer would pass that gate and still zero-rate the
invoice. The measured defect ran end to end: an issued goods invoice whose
customer country code was ``XX`` assembled cleanly and classified as
``export_third_country_zero_rated`` -- an exempt operation, from a string that
names no country, with no refusal and no advisory anywhere on the path.

Three properties, and the middle one is the reason the others are not enough:

* the unassigned code no longer assembles, so the classifier stays unreachable
  and the operator meets a named missing input instead of a category;
* a genuine catalogued third country still assembles AND still classifies as the
  export, so the narrowing did not buy safety by refusing real exports;
* the stated code is NAMED back to the operator, distinguishably, so a typo and
  a gap in our own vocabulary do not arrive wearing the same sentence.

Real registry data, real assembly, real rule table: nothing here is stubbed, and
the classification assertions are the shipped classifier's own output.

See Also:
    :func:`~domain.iva.territorial_scope_for_country`
        The authority the narrowing was stated at.
    :func:`~application.ledger.deterministic_findings`
        The list the operator-facing half of this is enrolled in.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core import ClassifierInputSource, DraftDiscrepancyKind
from ....domain.iva import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaCategory,
    IvaTerritorialScope,
    SupplyNature,
)
from .._classification_assembly import (
    DeclaredFact,
    DeclaredFacts,
    assemble_classification_criteria,
    classify_from_assembled_criteria,
)
from .._classifier_inputs import collect_classifier_inputs
from .._deterministic_findings import deterministic_findings
from .._evidence_draft import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DATE = date(2026, 4, 2)
_ASSERTED = ClassifierInputSource.OPERATOR_ASSERTION

#: The user-assigned codes measured settling a party outside the EU at HEAD.
UNASSIGNED_PROBES = ("XX", "ZZ", "QQ")


def _issued_goods_to(customer_country_code: str):
    """Assemble a Spanish issuer's goods invoice to a customer in one country.

    Everything except the customer's territory is asserted, so the ONLY question
    the assembly still has to answer from evidence is the one under test. A
    fixture that also left the supply nature or the issuer's territory open would
    refuse for reasons unrelated to the country axis and would pass whatever the
    axis did.
    """
    return assemble_classification_criteria(
        declared=DeclaredFacts(
            supply_nature=DeclaredFact(value=SupplyNature.GOODS, source=_ASSERTED),
            customer_tax_status=DeclaredFact(value=CustomerTaxStatus.B2C_CONSUMER, source=_ASSERTED),
            issuer_scope=DeclaredFact(value=IvaTerritorialScope.ES_MAINLAND, source=_ASSERTED),
            customer_scope=None,
            customer_identification_state=None,
        ),
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=collect_classifier_inputs(InvoiceDraft(customer_tax_id="12345678Z")),
        customer_country_code=customer_country_code,
    )


@pytest.mark.parametrize("code", UNASSIGNED_PROBES)
def test_an_unassigned_code_never_reaches_a_zero_rated_category(code: str) -> None:
    """The measured defect, asserted end to end on the side where it exempts.

    The classifier is unreachable rather than reachable-and-answering-otherwise,
    which is the stronger of the two shapes: a category assertion would still
    pass if some later path fed the same string in under a different name, while
    an unassembled criteria record cannot be classified at all.
    """
    assembly = _issued_goods_to(code)

    assert not assembly.assembled
    assert assembly.criteria is None
    assert {missing.field for missing in assembly.missing} == {"customer_residency"}


@pytest.mark.parametrize("code", UNASSIGNED_PROBES)
def test_the_refusal_names_the_string_the_document_stated(code: str) -> None:
    """A refusal an operator cannot act on is a dead end.

    The reason must quote the code and must say it names no country -- not that
    it is malformed, which would send the operator to re-read a field that reads
    perfectly.
    """
    missing = next(m for m in _issued_goods_to(code).missing if m.field == "customer_residency")

    assert repr(code) in missing.reason
    assert "reserved by ISO 3166-1" in missing.reason


def test_a_catalogued_code_the_vocabulary_omits_refuses_as_a_gap() -> None:
    """A real jurisdiction we do not carry refuses, and says whose fault it is."""
    missing = next(m for m in _issued_goods_to("TH").missing if m.field == "customer_residency")

    assert "'TH'" in missing.reason
    assert "country vocabulary" in missing.reason


def test_a_genuine_third_country_still_classifies_as_the_export() -> None:
    """The opposite direction, and the control on every refusal above.

    Without this, a narrowing that refused every country whatsoever would pass
    the entire file -- and refusing a legitimate export is the over-payment
    direction nothing else in this codebase watches.
    """
    assembly = _issued_goods_to("US")

    assert assembly.assembled
    assert classify_from_assembled_criteria(assembly).category is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED


@pytest.mark.parametrize("code", UNASSIGNED_PROBES)
def test_an_unassigned_code_raises_the_typo_finding(code: str) -> None:
    """The operator's typo signal, on the check list both readers run."""
    findings = deterministic_findings(InvoiceDraft(customer_country_code=code))

    finding = next(f for f in findings if f.field == "customer_country_code")
    assert finding.kind is DraftDiscrepancyKind.COUNTRY_CODE_UNASSIGNED
    assert repr(code) in finding.detail


def test_an_assigned_uncatalogued_code_raises_the_catalogue_gap_finding() -> None:
    """The two kinds must be distinguishable, or the operator hunts a typo we caused."""
    findings = deterministic_findings(InvoiceDraft(customer_country_code="TH"))

    finding = next(f for f in findings if f.field == "customer_country_code")
    assert finding.kind is DraftDiscrepancyKind.COUNTRY_CODE_UNCATALOGUED
    assert "'TH'" in finding.detail
    assert "vocabulary" in finding.detail


def test_the_check_runs_on_the_issuing_side_too() -> None:
    """Both parties, because establishment is asked of each independently."""
    findings = deterministic_findings(InvoiceDraft(supplier_country_code="XX"))

    assert [f.field for f in findings if f.kind is DraftDiscrepancyKind.COUNTRY_CODE_UNASSIGNED] == [
        "supplier_country_code",
    ]


@pytest.mark.parametrize("code", ["US", "DE", "ES", "XI"])
def test_a_catalogued_code_raises_no_country_finding(code: str) -> None:
    """The negative control. A check that fired on everything would be noise."""
    findings = deterministic_findings(InvoiceDraft(customer_country_code=code))

    assert not [f for f in findings if f.kind in _COUNTRY_KINDS]


@pytest.mark.parametrize("stated", [None, "", "  ", "Calle Mayor 3, 28013 Madrid"])
def test_nothing_that_is_not_a_code_raises_a_country_finding(stated: str | None) -> None:
    """An absent field is an honest absence, and an address line is not a bad code."""
    findings = deterministic_findings(InvoiceDraft(customer_country_code=stated))

    assert not [f for f in findings if f.kind in _COUNTRY_KINDS]


def test_a_resolved_printed_name_suppresses_the_finding() -> None:
    """A party the name rung settled needs no report about the code nothing consumed.

    The whole population this could false-fire on: a document whose address block
    printed "Alemania" while the structured country-code slot carried a
    placeholder. The territory is established, so the placeholder cost nothing.
    """
    findings = deterministic_findings(
        InvoiceDraft(customer_country="Alemania", customer_country_code="XX"),
    )

    assert not [f for f in findings if f.kind in _COUNTRY_KINDS]


_COUNTRY_KINDS = frozenset(
    {DraftDiscrepancyKind.COUNTRY_CODE_UNASSIGNED, DraftDiscrepancyKind.COUNTRY_CODE_UNCATALOGUED},
)
"""Both kinds this check can raise, so a negative control cannot miss one.

Derived from the members rather than written as a single kind, because a control
naming only the typo kind would pass while the catalogue-gap kind false-fired.
"""
