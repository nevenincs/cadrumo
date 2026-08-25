"""Absence must not become a verdict, and a printed number must not become a registration.

Two failures this file exists to prevent, both of which produce a plausible
classification rather than an error, and both of which cost money in opposite
directions.

**Reading absence as "consumer"** would reclassify the entire factura
simplificada population — documents that legitimately print no recipient at all.

**Reading a printed IVA identifier as "IVA-registered"** would let an unverified
number satisfy the intra-community supply rule, which classifies the operation
EXEMPT under LIVA art. 25. That exemption requires an IVA number *verified* as
valid; a number printed on a page has been verified by nobody.
"""

from __future__ import annotations

import pytest

from ....core import ClassifierInputSource, CounterpartyTaxablePersonStatus
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.iva import CustomerTaxStatus
from ..classifier_inputs import ClassifierInputFact, collect_classifier_inputs
from ..evidence_draft import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SUPPLIER_CIF = "B12345674"
_CUSTOMER_NIF = "12345678Z"


def _profile(regime: IVARegime) -> TaxpayerProfile:
    """Build a real taxpayer profile carrying a declared IVA regime."""
    return TaxpayerProfile(tax_id=_SUPPLIER_CIF, iva_regime=regime)


def test_a_printed_counterparty_identifier_establishes_a_taxable_person() -> None:
    """Someone who prints an IVA identifier is acting as a taxable person."""
    inputs = collect_classifier_inputs(InvoiceDraft(customer_tax_id=_CUSTOMER_NIF))

    assert inputs.counterparty_taxable_person is CounterpartyTaxablePersonStatus.TAXABLE_PERSON


def test_the_established_status_is_anchored_to_the_printed_identifier() -> None:
    """Anchorable evidence, so an operator can be shown what it was read from."""
    inputs = collect_classifier_inputs(InvoiceDraft(customer_tax_id=_CUSTOMER_NIF))
    fact = next(f for f in inputs.facts if f.name == "counterparty_taxable_person")

    assert fact.source is ClassifierInputSource.DOCUMENT_EVIDENCE
    assert fact.anchor == _CUSTOMER_NIF


def test_an_absent_identifier_resolves_unknown() -> None:
    """The load-bearing case: a simplified ticket prints no recipient at all."""
    inputs = collect_classifier_inputs(InvoiceDraft())

    assert inputs.counterparty_taxable_person is CounterpartyTaxablePersonStatus.UNKNOWN


def test_absence_is_never_reported_as_a_consumer() -> None:
    """Stronger than checking the default: no input can produce a consumer verdict.

    Asserted over the taxonomy itself rather than over one fixture. A default
    that merely happens to be safe would still let some other branch conclude
    "consumer"; a taxonomy with no such member cannot, whatever the document
    said or failed to say.
    """
    assert "consumer" not in {member.value for member in CounterpartyTaxablePersonStatus}
    assert {member.value for member in CounterpartyTaxablePersonStatus} == {"taxable_person", "unknown"}

    for draft in (
        InvoiceDraft(),
        InvoiceDraft(customer_tax_id=_CUSTOMER_NIF),
        InvoiceDraft(supplier_tax_id=_SUPPLIER_CIF),
    ):
        assert collect_classifier_inputs(draft).counterparty_taxable_person in {
            CounterpartyTaxablePersonStatus.TAXABLE_PERSON,
            CounterpartyTaxablePersonStatus.UNKNOWN,
        }


def test_an_unknown_status_carries_no_anchor() -> None:
    """Nothing was read, so there is no printed form to point an operator at."""
    inputs = collect_classifier_inputs(InvoiceDraft())
    fact = next(f for f in inputs.facts if f.name == "counterparty_taxable_person")

    assert fact.anchor is None


def test_a_printed_identifier_is_not_promoted_to_iva_registered() -> None:
    """The expensive one. An unverified number must not reach the art. 25 exemption.

    `CustomerTaxStatus.B2B_IVA_REGISTERED` is the trigger for the
    intra-community supply rule, which classifies the operation exempt. This
    envelope must not be able to express that claim at all — not merely decline
    to make it today — because VIES is deferred and nothing here has verified
    anything.
    """
    inputs = collect_classifier_inputs(InvoiceDraft(customer_tax_id=_CUSTOMER_NIF))

    values = {fact.value for fact in inputs.facts}
    assert CustomerTaxStatus.B2B_IVA_REGISTERED.value not in values
    assert CustomerTaxStatus.B2B_IVA_REGISTERED.value not in {
        member.value for member in CounterpartyTaxablePersonStatus
    }


def test_a_declared_regime_is_taken_from_the_profile_authority() -> None:
    """The filer's censo regime is system-authoritative, not read off the page."""
    inputs = collect_classifier_inputs(
        InvoiceDraft(customer_tax_id=_CUSTOMER_NIF),
        profile=_profile(IVARegime.RECARGO_EQUIVALENCIA),
    )
    fact = next(f for f in inputs.facts if f.name == "filer_iva_regime")

    assert inputs.filer_iva_regime is IVARegime.RECARGO_EQUIVALENCIA
    assert fact.source is ClassifierInputSource.PROFILE_AUTHORITY
    assert fact.authority
    assert fact.anchor is None, "a profile fact has no printed form on this document"


def test_no_profile_records_no_regime_rather_than_a_default() -> None:
    """Guessing the filer's regime would change the tax on every document they file."""
    inputs = collect_classifier_inputs(InvoiceDraft(customer_tax_id=_CUSTOMER_NIF))

    assert inputs.filer_iva_regime is None
    assert all(fact.name != "filer_iva_regime" for fact in inputs.facts)


def test_a_profile_fact_may_not_claim_a_document_anchor() -> None:
    """An anchor on a profile fact claims the document printed what it did not."""
    with pytest.raises(ValueError, match="must not carry a document anchor"):
        ClassifierInputFact(
            name="filer_iva_regime",
            value="recargo_equivalencia",
            source=ClassifierInputSource.PROFILE_AUTHORITY,
            anchor="Régimen de recargo de equivalencia",
            authority="taxpayer profile",
        )


def test_a_profile_fact_must_name_its_authority() -> None:
    """A system fact vouched for by nobody is not authoritative, just unsourced."""
    with pytest.raises(ValueError, match="must name the authority"):
        ClassifierInputFact(
            name="filer_iva_regime",
            value="general",
            source=ClassifierInputSource.PROFILE_AUTHORITY,
        )


def test_document_evidence_may_not_claim_an_authority() -> None:
    """The other direction: it would hide that a value was read rather than vouched for."""
    with pytest.raises(ValueError, match="vouched for by its anchor"):
        ClassifierInputFact(
            name="counterparty_taxable_person",
            value="taxable_person",
            source=ClassifierInputSource.DOCUMENT_EVIDENCE,
            anchor=_CUSTOMER_NIF,
            authority="taxpayer profile",
        )


def test_every_collected_fact_states_where_it_came_from() -> None:
    """The envelope's whole purpose: an audit reads the inputs, not a re-run."""
    inputs = collect_classifier_inputs(
        InvoiceDraft(customer_tax_id=_CUSTOMER_NIF),
        profile=_profile(IVARegime.GENERAL),
    )

    assert len(inputs.facts) == 2
    assert {fact.source for fact in inputs.facts} == {
        ClassifierInputSource.DOCUMENT_EVIDENCE,
        ClassifierInputSource.PROFILE_AUTHORITY,
    }
