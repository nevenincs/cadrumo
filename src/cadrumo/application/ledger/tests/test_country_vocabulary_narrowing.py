"""An unassigned country code must reach the operator, and must not refuse the draft.

The domain gate proves the resolver refuses. This file proves the refusal reaches
the place it has to reach, because a narrowed authority whose consumers had
already cached the old answer would pass that gate and still zero-rate the
invoice. The measured defect ran end to end: an issued goods invoice whose
customer country code was ``XX`` assembled cleanly and classified as
``export_third_country_zero_rated`` -- an exempt operation, from a string that
names no country, with no refusal and no advisory anywhere on the path.

**And it proves the report is ADVISORY.** The two country conditions were first
placed on the deterministic-findings channel, every member of which blocks the
confirm by construction. The bundled vocabulary carries a bounded subset of the
world's jurisdictions, so on a live population that refuses the draft of every
correct invoice naming a country we simply do not carry yet -- alert fatigue on
exactly the operators whose documents are fine. Nothing is lost by advising
instead, and this file measures that too: the classification assembly still
refuses, which is the refusal that actually prevented the silent zero-rating.

Five properties, and the middle ones are the reason the others are not enough:

* the unassigned code no longer assembles, so the classifier stays unreachable
  and the operator meets a named missing input instead of a category;
* a genuine catalogued third country still assembles AND still classifies as the
  export, so the narrowing did not buy safety by refusing real exports;
* the stated code is NAMED back to the operator, distinguishably, so a typo and
  a gap in our own vocabulary do not arrive wearing the same sentence;
* neither condition blocks the confirm, and the blocking axis carries no member
  for either, so restoring the block takes a change to that axis;
* an unreadable postal code on the same draft STILL blocks, which is the positive
  control -- without it, a broken gate would pass the property above vacuously.

Real registry data, real assembly, real rule table: nothing here is stubbed, and
the classification assertions are the shipped classifier's own output.

**The advisory fixtures set the STATED field, because that is the one a document
can populate.** The resolved ``*_country_code`` beside it is contracted alpha-2
and is filled only where the bundled vocabulary placed the token, so it is empty
for exactly the codes this file is about -- and a fixture setting it by hand
proves the selector while describing a draft no reading path produces. The
reaching-a-real-document half is measured against corpus bytes in
``test_structured_country_degradation``; these cases stay at the advisory's own
boundary.

See Also:
    :func:`~domain.iva.territorial_scope_for_country`
        The authority the narrowing was stated at.
    :func:`~application.ledger.country_vocabulary_advisory.country_vocabulary_advisory`
        The non-blocking channel the operator-facing half is reported on.
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
    StatedCountryCodeStatus,
    SupplyNature,
)
from ....tests.country_vocabulary_specimens import an_uncatalogued_alpha2
from ..classification_assembly import (
    DeclaredFact,
    DeclaredFacts,
    assemble_classification_criteria,
    classify_from_assembled_criteria,
)
from ..classifier_inputs import collect_classifier_inputs
from ..confirmation_gate import BLOCKING_REASON_BY_DISCREPANCY_KIND, confirmation_blockers
from ..country_vocabulary_advisory import country_vocabulary_advisory
from ..deterministic_findings import deterministic_findings
from ..evidence_draft import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DATE = date(2026, 4, 2)
_ASSERTED = ClassifierInputSource.OPERATOR_ASSERTION

#: The user-assigned codes measured settling a party outside the EU at HEAD.
UNASSIGNED_PROBES = ("XX", "ZZ", "QQ")

#: An address line in the postal slot: the one still-blocking sibling condition.
_UNREADABLE_POSTAL = "Calle Mayor 3, 28013 Madrid"


def _as_read(draft: InvoiceDraft) -> InvoiceDraft:
    """Return the draft carrying its findings, exactly as a reading path hands it on.

    The gate reads ``draft.discrepancies``; it does not run the checks itself. A
    bare draft therefore raises no blocker for any reason at all, so asserting
    "the country condition does not block" against one would measure nothing.
    This is the same ``model_copy`` the structured reader performs.
    """
    return draft.model_copy(update={"discrepancies": deterministic_findings(draft)})


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

    This is also the refusal that carries the safety, and it is why the operator
    report beside it does not need to. Softening the report to an advisory leaves
    this assertion untouched.
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
    """A real jurisdiction we do not carry refuses, and says whose fault it is.

    The specimen is derived from the vocabulary, so this follows the boundary
    instead of pinning it: a named country reds this case the day it is admitted,
    which reports a fixture change as a behaviour change.
    """
    specimen = an_uncatalogued_alpha2()
    missing = next(m for m in _issued_goods_to(specimen).missing if m.field == "customer_residency")

    assert repr(specimen) in missing.reason
    assert "country vocabulary" in missing.reason


def test_a_genuine_third_country_still_classifies_as_the_export() -> None:
    """The opposite direction, and the control on every refusal above.

    Without this, a narrowing that refused every country whatsoever would pass
    the entire file -- and refusing a legitimate export is the over-payment
    direction nothing else in this codebase watches.
    """
    assembly = _issued_goods_to("US")

    assert assembly.assembled
    classification = classify_from_assembled_criteria(assembly)
    assert classification is not None
    assert classification.category is IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED


@pytest.mark.parametrize("code", UNASSIGNED_PROBES)
def test_an_unassigned_code_raises_the_typo_advisory(code: str) -> None:
    """The operator's typo signal, on the non-blocking channel."""
    advisory = country_vocabulary_advisory(InvoiceDraft(customer_stated_country_code=code))

    assert advisory is not None
    warning = next(party for party in advisory.parties if party.field == "customer_stated_country_code")
    assert warning.status is StatedCountryCodeStatus.UNASSIGNED
    assert warning.stated_code == code
    assert repr(code) in warning.detail


def test_an_assigned_uncatalogued_code_raises_the_catalogue_gap_advisory() -> None:
    """The two kinds must be distinguishable, or the operator hunts a typo we caused."""
    specimen = an_uncatalogued_alpha2()
    advisory = country_vocabulary_advisory(InvoiceDraft(customer_stated_country_code=specimen))

    assert advisory is not None
    warning = next(party for party in advisory.parties if party.field == "customer_stated_country_code")
    assert warning.status is StatedCountryCodeStatus.UNCATALOGUED
    assert repr(specimen) in warning.detail
    assert "vocabulary" in warning.detail
    assert advisory.by_status(StatedCountryCodeStatus.UNASSIGNED) == ()


def test_the_check_runs_on_the_issuing_side_too() -> None:
    """Both parties, because establishment is asked of each independently."""
    advisory = country_vocabulary_advisory(InvoiceDraft(supplier_stated_country_code="XX"))

    assert advisory is not None
    assert advisory.fields == ("supplier_stated_country_code",)
    assert advisory.parties[0].role == "issuing"


@pytest.mark.parametrize("code", ["US", "DE", "ES", "XI"])
def test_a_catalogued_code_raises_no_country_advisory(code: str) -> None:
    """The negative control. A check that fired on everything would be noise."""
    assert country_vocabulary_advisory(InvoiceDraft(customer_stated_country_code=code)) is None


@pytest.mark.parametrize("stated", [None, "", "  ", "Calle Mayor 3, 28013 Madrid"])
def test_nothing_that_is_not_a_code_raises_a_country_advisory(stated: str | None) -> None:
    """An absent field is an honest absence, and an address line is not a bad code."""
    assert country_vocabulary_advisory(InvoiceDraft(customer_stated_country_code=stated)) is None


def test_a_resolved_printed_name_suppresses_the_advisory() -> None:
    """A party the name rung settled needs no report about the code nothing consumed.

    The whole population this could false-fire on: a document whose address block
    printed "Alemania" while the structured country-code slot carried a
    placeholder. The territory is established, so the placeholder cost nothing.
    """
    advisory = country_vocabulary_advisory(
        InvoiceDraft(customer_country="Alemania", customer_stated_country_code="XX"),
    )

    assert advisory is None


@pytest.mark.parametrize("code", [*UNASSIGNED_PROBES, an_uncatalogued_alpha2()])
def test_a_country_code_outside_the_vocabulary_does_not_block_the_confirm(code: str) -> None:
    """The deliverable. An advised draft is still confirmable.

    Asserted on both channels at once, because either alone is escapable: a
    finding could be raised and left unmapped (the gate refuses to import, but a
    reader checking only blockers would not know why), and a blocker could be
    raised from something other than a finding.
    """
    draft = _as_read(InvoiceDraft(customer_stated_country_code=code))

    assert country_vocabulary_advisory(draft) is not None
    assert draft.discrepancies == ()
    assert confirmation_blockers(draft) == ()


@pytest.mark.parametrize("code", [*UNASSIGNED_PROBES, an_uncatalogued_alpha2()])
def test_an_unreadable_postal_code_on_the_same_draft_still_blocks(code: str) -> None:
    """The positive control on the property above.

    Without it, a confirmation gate that had stopped raising blockers at all
    would pass the non-blocking assertion vacuously -- the exact shape of a green
    run that measures the harness rather than the code. One draft carries both
    conditions, so the same call that returns no country blocker returns the
    postal one.
    """
    draft = _as_read(InvoiceDraft(customer_stated_country_code=code, customer_postal_code=_UNREADABLE_POSTAL))

    blockers = confirmation_blockers(draft)

    assert [blocker.field for blocker in blockers] == ["customer_postal_code"]
    assert [finding.kind for finding in draft.discrepancies] == [DraftDiscrepancyKind.POSTAL_CODE_UNREADABLE]
    assert country_vocabulary_advisory(draft) is not None


def test_the_blocking_axis_carries_no_country_condition() -> None:
    """Structural, so restoring the block cannot happen by editing the advisory.

    The confirmation gate maps every member of the blocking axis and refuses to
    import while one is unmapped, so the axis IS the blocking set. A country
    member reappearing there is the regression this names, and it would be
    invisible to every behavioural case above if the check that raised it were
    still on the advisory channel.
    """
    country_members = [kind for kind in DraftDiscrepancyKind if "country" in kind.value]

    assert country_members == []
    assert set(BLOCKING_REASON_BY_DISCREPANCY_KIND) == set(DraftDiscrepancyKind)
