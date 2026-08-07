"""The classifier must stay unreachable on incomplete evidence, and reachable on complete evidence.

Both halves are load-bearing and they pull against each other. A producer that
answers whenever asked would replace a visible gap with a number on a filing; a
producer nothing can satisfy would be a gate that can never pass, which is worth
no more than one that never fails. So this file proves the refusals AND proves
the successful path they are refusals from.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.iva import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaCategory,
    IvaRateKind,
    IvaTerritorialScope,
    SupplyNature,
    TransactionKind,
)
from .._classification_assembly import (
    assemble_classification_criteria,
    classify_from_assembled_criteria,
)
from .._classifier_inputs import collect_classifier_inputs
from .._evidence_draft import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CUSTOMER_NIF = "12345678Z"
_DATE = date(2026, 4, 2)


def _inputs(*, printed_identifier: str | None = _CUSTOMER_NIF):
    return collect_classifier_inputs(InvoiceDraft(customer_tax_id=printed_identifier))


def _complete(**overrides: object):
    """An assembly whose every input is established, by assertion where evidence cannot."""
    kwargs: dict[str, object] = {
        "transaction_date": _DATE,
        "direction": InvoiceKind.ISSUED,
        "inputs": _inputs(),
        "supply_nature": SupplyNature.GOODS,
        # The customer's country code carries BOTH the EU scope and the Member
        # State; the issuer's Spanish territory has no country-code answer and
        # is asserted, which is the only sanctioned way to supply it.
        "customer_country_code": "FR",
        "asserted_customer_tax_status": CustomerTaxStatus.B2B_IVA_REGISTERED,
        "asserted_issuer_scope": IvaTerritorialScope.ES_MAINLAND,
    }
    kwargs.update(overrides)
    return assemble_classification_criteria(**kwargs)  # type: ignore[arg-type]


def test_a_printed_identifier_alone_does_not_assemble_the_criteria() -> None:
    """The expensive refusal. A taxable person is not a verified registration."""
    assembly = assemble_classification_criteria(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="ES",
        customer_country_code="DE",
    )

    assert not assembly.assembled
    gap = next(m for m in assembly.missing if m.field == "customer_tax_status")
    assert "not a valid registration" in gap.reason
    assert "VIES" in gap.settled_by


def test_the_registered_status_is_never_derived_from_the_envelope() -> None:
    """A structural guard, cheap to carry and loud the moment someone bridges it.

    The envelope's own taxonomy must not gain, and must not be mapped onto, the
    value that triggers the art. 25 exemption. Asserted over the emitted facts
    rather than over one call, so a future producer adding the bridge reds here.
    """
    from ....core import CounterpartyTaxablePersonStatus

    emitted = {fact.value for fact in _inputs().facts}
    assert CustomerTaxStatus.B2B_IVA_REGISTERED.value not in emitted
    assert CustomerTaxStatus.B2B_IVA_REGISTERED.value not in {
        member.value for member in CounterpartyTaxablePersonStatus
    }


def test_a_spanish_country_code_does_not_settle_the_territory() -> None:
    """Spain holds three IVA territories a country code cannot tell apart.

    The refusal must name that rather than defaulting to the mainland, which is
    the restrictive-provision-as-default shape: it would silently capture the
    Canaries, Ceuta and Melilla population the rule does not govern.
    """
    assembly = assemble_classification_criteria(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="ES",
        customer_country_code="ES",
        asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    )

    assert not assembly.assembled
    fields = {m.field for m in assembly.missing}
    assert fields == {"issuer_residency", "customer_residency"}
    assert all("three IVA territories" in m.reason for m in assembly.missing)


def test_a_foreign_country_code_does_settle_the_territory() -> None:
    """Positive control for the refusal above: the resolver is genuinely consulted."""
    assembly = assemble_classification_criteria(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="DE",
        customer_country_code="FR",
        asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    )

    assert assembly.assembled, [m.field for m in assembly.missing]
    assert assembly.criteria is not None
    assert assembly.criteria.issuer_residency is IvaTerritorialScope.EU_MEMBER


def test_an_absent_supply_nature_refuses_rather_than_defaulting() -> None:
    """Goods and services fork the place-of-supply rules; guessing picks a branch."""
    assembly = _complete(supply_nature=None)

    assert not assembly.assembled
    assert {m.field for m in assembly.missing} == {"kind"}


def test_an_absent_date_refuses() -> None:
    """The rate schedule is dated, so an undated operation cannot be rated."""
    assembly = _complete(transaction_date=None)

    assert not assembly.assembled
    assert {m.field for m in assembly.missing} == {"transaction_date"}


def test_every_missing_input_is_reported_at_once() -> None:
    """An operator resolving four gaps should learn four, not one per attempt."""
    assembly = assemble_classification_criteria(
        transaction_date=None,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(printed_identifier=None),
        supply_nature=None,
    )

    assert {m.field for m in assembly.missing} == {
        "customer_tax_status",
        "issuer_residency",
        "customer_residency",
        "kind",
        "transaction_date",
    }


def test_every_refusal_names_something_the_operator_can_do() -> None:
    """A refusal an operator cannot act on is barely better than a silent drop."""
    assembly = assemble_classification_criteria(
        transaction_date=None,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(printed_identifier=None),
        supply_nature=None,
    )

    assert assembly.missing
    assert all(m.settled_by.strip() for m in assembly.missing)


def test_complete_evidence_assembles_and_reaches_the_rule_table() -> None:
    """The positive control for the whole file: the table is genuinely reachable.

    Without this, every refusal above would pass equally against a producer that
    could never assemble anything — which is exactly the state this Step exists
    to end, since the criteria record was constructed nowhere in production.
    """
    assembly = _complete()

    assert assembly.assembled
    verdict = classify_from_assembled_criteria(assembly)

    assert verdict is not None
    assert verdict.category is IvaCategory.INTRA_COMMUNITY_SUPPLY, verdict.category


def test_an_unassembled_criteria_set_never_reaches_the_table() -> None:
    """The refusal must stop the classification, not merely annotate it."""
    assembly = _complete(supply_nature=None)

    assert classify_from_assembled_criteria(assembly) is None


def test_a_printed_nature_maps_only_to_the_general_service_kind() -> None:
    """The specialised kinds carry legal consequences a goods/services reading does not.

    Land-related services, passenger transport and the reverse-charge sub-kinds
    each change the answer, and none of them is established by a document saying
    it supplies services.
    """
    services = _complete(supply_nature=SupplyNature.SERVICES)

    assert services.criteria is not None
    assert services.criteria.kind is TransactionKind.SERVICES_GENERAL


def test_an_operator_assertion_settles_what_the_evidence_cannot() -> None:
    """The sanctioned path until VIES exists: the operator's claim, made knowingly."""
    without = assemble_classification_criteria(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="DE",
        customer_country_code="FR",
    )
    with_assertion = assemble_classification_criteria(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="DE",
        customer_country_code="FR",
        asserted_customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
    )

    assert not without.assembled
    assert with_assertion.assembled
    assert with_assertion.criteria is not None
    assert with_assertion.criteria.customer_tax_status is CustomerTaxStatus.B2C_CONSUMER


def test_the_domestic_rate_tier_axis_is_carried_through() -> None:
    """ES-to-ES domestic operations need the tier, and the criteria model enforces it."""
    assembly = _complete(
        customer_country_code=None,
        asserted_issuer_scope=IvaTerritorialScope.ES_MAINLAND,
        asserted_customer_scope=IvaTerritorialScope.ES_MAINLAND,
        rate_tier=IvaRateKind.GENERAL,
    )

    assert assembly.assembled, [m.field for m in assembly.missing]
    assert assembly.criteria is not None
    assert assembly.criteria.rate_tier is IvaRateKind.GENERAL
