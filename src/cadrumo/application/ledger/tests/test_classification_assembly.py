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

from ....core import ClassifierInputSource
from ....domain.iva import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaCategory,
    IvaRateKind,
    IvaTerritorialScope,
    SupplyNature,
    TransactionKind,
    domestic_rate_tier_is_required,
)
from ..classification_assembly import (
    DeclaredFact,
    DeclaredFacts,
    assemble_classification_criteria,
    classify_from_assembled_criteria,
)
from ..classifier_inputs import collect_classifier_inputs
from ..evidence_draft import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CUSTOMER_NIF = "12345678Z"
#: A structurally valid French IVA number. A document whose customer is
#: IVA-identified in France prints one, and it is what establishes the
#: identification: the printed country code beside it says where the party
#: IS, which is a different fact and settles nothing here.
_FRENCH_IVA_NUMBER = "FR40303265045"
_DATE = date(2026, 4, 2)


def _inputs(*, printed_identifier: str | None = _CUSTOMER_NIF):
    return collect_classifier_inputs(InvoiceDraft(customer_tax_id=printed_identifier))


_ASSERTED = ClassifierInputSource.OPERATOR_ASSERTION


def _assemble_with_declared(
    *,
    supply_nature=None,
    asserted_customer_tax_status=None,
    asserted_issuer_scope=None,
    asserted_customer_scope=None,
    asserted_customer_identification_state=None,
    **kwargs,
):
    """Call the real assembly, building the declared-facts channel from flat facts.

    An adapter rather than a rewrite of every call site: these tests are about
    the assembly's REFUSAL logic, and restating four attributions at sixteen
    sites would bury that behind ceremony. Every fact it supplies is attributed
    as an operator assertion, which is what these cases mean -- they exercise
    the path where the document could not settle the value.

    The channel's own contract is gated separately in
    ``test_declared_facts_channel.py`` against the real signature, so nothing
    here is the only thing standing between the channel and a regression.
    """

    def wrap(value):
        return None if value is None else DeclaredFact(value=value, source=_ASSERTED)

    return assemble_classification_criteria(
        declared=DeclaredFacts(
            supply_nature=wrap(supply_nature),
            customer_tax_status=wrap(asserted_customer_tax_status),
            issuer_scope=wrap(asserted_issuer_scope),
            customer_scope=wrap(asserted_customer_scope),
            customer_identification_state=wrap(asserted_customer_identification_state),
        ),
        **kwargs,
    )


def _complete(**overrides: object):
    """An assembly whose every input is established, by assertion where evidence cannot."""
    kwargs: dict[str, object] = {
        "transaction_date": _DATE,
        "direction": InvoiceKind.ISSUED,
        "inputs": _inputs(),
        "supply_nature": SupplyNature.GOODS,
        # The country code establishes WHERE the customer is; the printed IVA
        # number establishes WHICH State identifies it. They are two facts and
        # neither supplies the other, so a case meaning a French taxable
        # customer carries both. The issuer's Spanish territory has no
        # country-code answer and is asserted, which is the only sanctioned way
        # to supply it.
        "customer_country_code": "FR",
        "customer_identifier": _FRENCH_IVA_NUMBER,
        "asserted_customer_tax_status": CustomerTaxStatus.B2B_IVA_REGISTERED,
        "asserted_issuer_scope": IvaTerritorialScope.ES_MAINLAND,
    }
    kwargs.update(overrides)
    return _assemble_with_declared(**kwargs)  # type: ignore[arg-type]


def test_a_printed_identifier_alone_does_not_assemble_the_criteria() -> None:
    """The expensive refusal. A taxable person is not a verified registration."""
    assembly = _assemble_with_declared(
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
    assembly = _assemble_with_declared(
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
    assembly = _assemble_with_declared(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="DE",
        customer_country_code="FR",
        # This pair reaches no rule, so the fallthrough declares both party
        # facts consumed and the counterparty's identification is demanded --
        # an unplaced operation is asked rather than certified indifferent. The
        # printed number settles it, leaving the country resolver as the only
        # thing this case is testing.
        customer_identifier=_FRENCH_IVA_NUMBER,
        asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    )

    assert assembly.assembled, [m.field for m in assembly.missing]
    assert assembly.criteria is not None
    assert assembly.criteria.issuer_residency is IvaTerritorialScope.EU_MEMBER


def test_an_absent_supply_nature_refuses_on_a_branch_that_forks() -> None:
    """Cross-border: goods and services take different place-of-supply rules."""
    assembly = _complete(supply_nature=None)

    assert not assembly.assembled
    assert {m.field for m in assembly.missing} == {"kind"}


def test_a_domestic_operation_is_never_asked_for_the_supply_nature() -> None:
    """The common path must not carry a gap the law does not fork on.

    A domestic operation between established parties at a registry rate resolves
    identically for goods and services, so demanding the distinction asked the
    operator a question with no answer that could change anything — on every
    domestic invoice.
    """
    assembly = _complete(
        supply_nature=None,
        customer_country_code=None,
        asserted_issuer_scope=IvaTerritorialScope.ES_MAINLAND,
        asserted_customer_scope=IvaTerritorialScope.ES_MAINLAND,
        rate_tier=IvaRateKind.GENERAL,
    )

    assert "kind" not in {m.field for m in assembly.missing}
    assert assembly.assembled, [m.field for m in assembly.missing]

    # And the placeholder it supplied must land on the same category an
    # explicitly-natured domestic operation does. Asserting only that it
    # assembled leaves the placeholder unguarded: a value that quietly selected
    # a reverse-charge branch would still assemble, and would still be wrong.
    with_nature = _complete(
        supply_nature=SupplyNature.SERVICES,
        customer_country_code=None,
        asserted_issuer_scope=IvaTerritorialScope.ES_MAINLAND,
        asserted_customer_scope=IvaTerritorialScope.ES_MAINLAND,
        rate_tier=IvaRateKind.GENERAL,
    )
    without = classify_from_assembled_criteria(assembly)
    stated = classify_from_assembled_criteria(with_nature)

    assert without is not None and stated is not None
    assert without.category is stated.category, (
        f"the nature-indifferent placeholder changed the outcome: {without.category} vs {stated.category}"
    )


def test_the_domestic_branch_is_genuinely_indifferent_to_the_nature() -> None:
    """Proves the placeholder kind is sound rather than asserting it.

    Skipping the demand is only honest if the answer truly cannot matter. So
    classify the same domestic operation under BOTH reachable kinds and require
    the identical category. If the branch ever starts forking on nature, this
    reds and the laziness above becomes a defect rather than a convenience.
    """
    verdicts = set()
    for nature in (SupplyNature.GOODS, SupplyNature.SERVICES):
        assembly = _complete(
            supply_nature=nature,
            customer_country_code=None,
            asserted_issuer_scope=IvaTerritorialScope.ES_MAINLAND,
            asserted_customer_scope=IvaTerritorialScope.ES_MAINLAND,
            rate_tier=IvaRateKind.GENERAL,
        )
        verdict = classify_from_assembled_criteria(assembly)
        assert verdict is not None
        verdicts.add(verdict.category)

    assert len(verdicts) == 1, f"the domestic branch forked on supply nature: {verdicts}"


def test_the_probe_agrees_with_the_domain_laziness_authority() -> None:
    """The two must never fork, and only a gate can keep that true.

    The assembly cannot call ``supply_nature_is_required`` — it keys on an
    established category and the assembly is what produces one — so it derives
    the same judgement by asking the table itself. That is not a second
    authority only while the two agree, and nothing in the type system says they
    do. So: for each branch, take the categories the probe reaches and require
    the domain function's verdict to match the probe's.

    A category moved into or out of the nature-indifferent set reds here rather
    than silently making the assembly demand the wrong thing.
    """
    from ....domain.iva import supply_nature_is_required

    for scopes, expect_forks in (
        ((IvaTerritorialScope.ES_MAINLAND, IvaTerritorialScope.ES_MAINLAND), False),
        ((IvaTerritorialScope.ES_MAINLAND, IvaTerritorialScope.EU_MEMBER), True),
    ):
        issuer, customer = scopes
        reached = set()
        for nature in (SupplyNature.GOODS, SupplyNature.SERVICES):
            assembly = _complete(
                supply_nature=nature,
                customer_country_code="FR" if customer is IvaTerritorialScope.EU_MEMBER else None,
                asserted_issuer_scope=issuer,
                asserted_customer_scope=customer,
                rate_tier=IvaRateKind.GENERAL,
            )
            verdict = classify_from_assembled_criteria(assembly)
            assert verdict is not None
            reached.add(verdict.category)

        probe_says_forks = len(reached) > 1
        assert probe_says_forks is expect_forks, f"{scopes} reached {reached}"
        # The domain authority must agree: a branch the probe calls indifferent
        # must reach only categories it also calls indifferent.
        if not probe_says_forks:
            assert not any(supply_nature_is_required(c) for c in reached), (
                f"the probe called {scopes} indifferent but the domain authority disagrees: {reached}"
            )
        else:
            assert any(supply_nature_is_required(c) for c in reached), (
                f"the probe called {scopes} forking but the domain authority sees no forking category: {reached}"
            )


def test_an_unresolved_scope_still_demands_the_nature() -> None:
    """Fails toward asking: an unplaced operation may yet land on a forking branch."""
    assembly = _complete(
        supply_nature=None,
        customer_country_code="ES",
        asserted_issuer_scope=None,
        asserted_customer_scope=None,
    )

    assert "kind" in {m.field for m in assembly.missing}


def test_an_absent_date_refuses() -> None:
    """The rate schedule is dated, so an undated operation cannot be rated."""
    assembly = _complete(transaction_date=None)

    assert not assembly.assembled
    assert {m.field for m in assembly.missing} == {"transaction_date"}


def test_every_missing_input_is_reported_at_once() -> None:
    """An operator resolving four gaps should learn four, not one per attempt."""
    assembly = _assemble_with_declared(
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
    assembly = _assemble_with_declared(
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
    could never assemble anything — which is exactly the failure mode this test
    guards against, since the criteria record was constructed nowhere in production.
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
    """The sanctioned path until VIES exists: the operator's claim, made knowingly.

    Written against the real signature rather than the adapter, because the
    subject here IS the attribution: the same value settles the assembly only
    when someone is recorded as having claimed it.
    """
    goods = DeclaredFact(value=SupplyNature.GOODS, source=ClassifierInputSource.OPERATOR_ASSERTION)
    without = assemble_classification_criteria(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        declared=DeclaredFacts(supply_nature=goods),
        issuer_country_code="DE",
        customer_country_code="FR",
        customer_identifier=_FRENCH_IVA_NUMBER,
    )
    with_assertion = assemble_classification_criteria(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        declared=DeclaredFacts(
            supply_nature=goods,
            customer_tax_status=DeclaredFact(
                value=CustomerTaxStatus.B2C_CONSUMER,
                source=ClassifierInputSource.OPERATOR_ASSERTION,
            ),
        ),
        issuer_country_code="DE",
        customer_country_code="FR",
        customer_identifier=_FRENCH_IVA_NUMBER,
    )

    assert not without.assembled
    assert with_assertion.assembled
    assert with_assertion.criteria is not None
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


def test_a_domestic_operation_with_no_tier_names_the_tier_and_not_another_axis() -> None:
    """The blocker must be the field reported, not whatever the failed probe implicated.

    Measured before the fix: this operation reported ``issuer_identification_state``
    as its missing input -- a fact the domestic branch provably does not consume,
    gated one package over -- while the tier that actually blocked it was never
    named. The cause is a chain rather than a wrong string: the criteria model
    RAISES without a domestic tier, the axis probe treats an unclassifiable
    criteria set as "this branch might need everything", and everything includes
    the identification.

    So the operator was sent to supply a NIF-IVA. Following that instruction
    could not have unblocked them, because supplying it changes nothing the
    domestic branch reads -- a refusal an operator cannot act on, which is the
    one thing every refusal here is contracted not to be.
    """
    assembly = _complete(
        customer_country_code=None,
        asserted_issuer_scope=IvaTerritorialScope.ES_MAINLAND,
        asserted_customer_scope=IvaTerritorialScope.ES_MAINLAND,
        rate_tier=None,
    )

    reported = [gap.field for gap in assembly.missing]
    assert "rate_tier" in reported, f"the tier is the blocker and must be named: {reported}"
    assert "issuer_identification_state" not in reported, (
        f"the domestic branch does not consume an identification; reporting one misdirects: {reported}"
    )
    assert not assembly.assembled


def test_supplying_the_tier_is_what_actually_unblocks_it() -> None:
    """The positive control the assertion above needs to mean anything.

    Without this, the case above would hold for a refusal that named the tier
    and then refused anyway on some further axis, which would be the same
    dead-end failure wearing a better label.
    """
    assembly = _complete(
        customer_country_code=None,
        asserted_issuer_scope=IvaTerritorialScope.ES_MAINLAND,
        asserted_customer_scope=IvaTerritorialScope.ES_MAINLAND,
        rate_tier=IvaRateKind.GENERAL,
    )

    assert assembly.assembled, [gap.field for gap in assembly.missing]


def test_a_cross_border_operation_is_never_asked_for_a_domestic_tier() -> None:
    """The laziness half: the demand is made only where the law forks on it.

    A demand raised unconditionally would put a Spanish rate-tier question on
    every intra-community invoice, which is the noise the per-branch demand
    exists to remove -- and is the exact defect a sibling row corrected on the
    supply-nature axis.
    """
    assembly = _complete(rate_tier=None)

    assert "rate_tier" not in [gap.field for gap in assembly.missing]


def test_a_domestic_reverse_charge_kind_is_never_asked_for_a_tier() -> None:
    """The exempt kinds, asked of the domain authority rather than restated here.

    Rules R01 through R03 route the dedicated reverse-charge kinds before the
    domestic rate rule runs, so their tier is a payload concern. This asserts
    the producer agrees with the predicate the criteria model enforces, in both
    directions, which is what stops the two drifting into a demand the model
    does not make or a silence where it does.
    """
    for kind in (
        TransactionKind.CONSTRUCTION_REVERSE_CHARGE,
        TransactionKind.WASTE_REVERSE_CHARGE,
        TransactionKind.ELECTRONICS_REVERSE_CHARGE,
        TransactionKind.IMMOVABLE_PROPERTY,
    ):
        assert not domestic_rate_tier_is_required(
            issuer_residency=IvaTerritorialScope.ES_MAINLAND,
            customer_residency=IvaTerritorialScope.ES_MAINLAND,
            kind=kind,
        ), kind
    assert domestic_rate_tier_is_required(
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.ES_MAINLAND,
        kind=TransactionKind.GOODS,
    )
    assert not domestic_rate_tier_is_required(
        issuer_residency=IvaTerritorialScope.ES_MAINLAND,
        customer_residency=IvaTerritorialScope.EU_MEMBER,
        kind=TransactionKind.GOODS,
    )


def test_a_spanish_postal_code_settles_the_territory_the_country_code_cannot() -> None:
    """The join that resolves the sub-national half of establishment.

    A country code names Spain and stops there, because the three Spanish IVA
    territories are treated differently by law. The postal code's first two
    digits are the province, so it is the deterministic evidence that separates
    them — and until it was joined, the resolver existed and nothing consulted
    it.
    """
    assembly = _assemble_with_declared(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="ES",
        issuer_postal_code="35001",
        customer_country_code="ES",
        customer_postal_code="28013",
        asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
        rate_tier=IvaRateKind.GENERAL,
    )

    assert assembly.assembled, [m.field for m in assembly.missing]
    assert assembly.criteria is not None
    assert assembly.criteria.issuer_residency is IvaTerritorialScope.ES_CANARIAS
    assert assembly.criteria.customer_residency is IvaTerritorialScope.ES_MAINLAND


def test_a_spanish_party_with_no_postal_code_refuses_rather_than_assuming_mainland() -> None:
    """The safety asymmetry carried through the join, and the whole point of the row.

    The peninsula is the majority population, so defaulting to it would be
    invisible in testing while silently placing Canarian and Ceutan parties
    inside a territory their operations are not subject to. The refusal must
    survive at the JOIN and not only inside the resolver: a caller is free to
    substitute its own default for the resolver's ``None``, which is exactly the
    failure this asserts against.
    """
    assembly = _assemble_with_declared(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="ES",
        issuer_postal_code=None,
        customer_country_code="ES",
        customer_postal_code="   ",
        asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    )

    assert not assembly.assembled
    assert {m.field for m in assembly.missing} == {"issuer_residency", "customer_residency"}
    assert all(m.settled_by.strip() for m in assembly.missing)


def test_a_postal_code_alone_never_establishes_a_spanish_territory() -> None:
    """A bare postal code is not evidence of Spain, and reading it as such is the trap.

    Five-digit postal codes are not unique to Spain, so consulting the Spanish
    resolver without country evidence would map a French or German code onto a
    Spanish province — the restrictive default one level below the country axis
    that already refuses it. The join is gated on the country evidence
    POSITIVELY naming Spain, never on the country resolver merely returning
    nothing.
    """
    assembly = _assemble_with_declared(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code=None,
        issuer_postal_code="35001",
        customer_country_code=None,
        customer_postal_code="28013",
        asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    )

    assert not assembly.assembled
    assert {m.field for m in assembly.missing} == {"issuer_residency", "customer_residency"}
    assert all("no country code" in m.reason for m in assembly.missing)


#: A checksum-valid Spanish company identifier, as an ordinary domestic invoice prints it.
#:
#: Real rather than a placeholder because the whole point of the fixture below is
#: that this identifier is genuinely, verifiably Spanish and still establishes
#: nothing about establishment. A malformed value would be refused for the wrong
#: reason and would prove nothing.
_DOMESTIC_B_CIF = "B84333723"


def test_a_bare_spanish_company_identifier_never_reaches_the_peninsula() -> None:
    """The ordinary domestic invoice: valid Spanish CIF, no country, no postal code.

    This is the document the whole read path is aimed at, and it must refuse
    rather than resolve. The identifier passes the AEAT checksum, so the tempting
    reading is that a Spanish CIF makes a Spanish party -- and it is false. The
    non-resident company leader, the K/L/M identifiers issued to Spaniards abroad
    and to non-residents, and the whole NIE series are all checksum-valid Spanish
    identifiers belonging to parties not established in Spain. Establishment for
    IVA is the sede de actividad, not tax registration.

    **It would have tested green**, which is why this is a gate rather than a
    comment: most Spanish identifiers do belong to resident parties, so the
    inference is right often enough to survive casual testing and wrong exactly
    where a wrong domestic placement drops a reverse charge.

    Asserts the absence of the mainland specifically, not merely that something
    was missing. A refusal for some unrelated reason would satisfy a bare
    "not assembled" check while the peninsula default sat live underneath it.
    """
    draft = InvoiceDraft(supplier_tax_id=_DOMESTIC_B_CIF, customer_tax_id=_DOMESTIC_B_CIF)
    assembly = _assemble_with_declared(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=collect_classifier_inputs(draft),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code=None,
        issuer_postal_code=None,
        customer_country_code=None,
        customer_postal_code=None,
        asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    )

    assert not assembly.assembled
    assert assembly.criteria is None
    assert {m.field for m in assembly.missing} == {"issuer_residency", "customer_residency"}
    assert all("no country code" in m.reason for m in assembly.missing)


def test_no_reachable_evidence_shape_ever_defaults_a_residency_to_the_peninsula() -> None:
    """Sweep the shapes a domestic document can present, and require none to default.

    One fixture proves one document. The peninsula default is dangerous because
    it is invisible, so the claim worth gating is over the whole space of
    evidence a domestic invoice can carry: identifier present or absent, postal
    code present or absent, and neither carrying country evidence. Every one must
    refuse.

    The postal-bearing rows are the sharp ones. A Spanish-looking code with no
    country evidence must NOT resolve, because the five-digit shape is shared
    with France, Germany and Italy and so establishes nothing on its own.
    """
    for tax_id in (None, _DOMESTIC_B_CIF):
        for postal in (None, "", "   ", "28013", "35001"):
            assembly = _assemble_with_declared(
                transaction_date=_DATE,
                direction=InvoiceKind.ISSUED,
                inputs=collect_classifier_inputs(InvoiceDraft(supplier_tax_id=tax_id)),
                supply_nature=SupplyNature.GOODS,
                issuer_country_code=None,
                issuer_postal_code=postal,
                customer_country_code="FR",
                asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
            )

            assert assembly.criteria is None, (tax_id, postal)
            assert "issuer_residency" in {m.field for m in assembly.missing}, (tax_id, postal)


@pytest.mark.parametrize(
    ("postal_code", "city"),
    [("75001", "Paris"), ("10115", "Berlin"), ("00170", "Rome"), ("51001", "Reims")],
)
def test_a_foreign_postal_code_never_resolves_to_a_spanish_territory(postal_code: str, city: str) -> None:
    """The five-digit shape discriminates NOTHING, so only the country gate does.

    Spain, France, Germany and Italy all use five-digit postal codes, and the
    Spanish resolver is named for its precondition rather than checking it:
    measured directly, ``75001`` yields the peninsula and ``51001`` yields Ceuta
    and Melilla. So a consumer that reaches the postal half without having
    established Spain places a Paris party on the peninsula and a Reims party in
    Ceuta -- on exactly the countries most likely to appear on an
    intra-community invoice, where a wrong domestic placement silently drops the
    reverse charge.

    The composition is the trap: the country half and the postal half are each
    fail-closed, and they compose fail-OPEN. The country resolver returns
    nothing for a Spanish code BY DESIGN and also for an absent or malformed
    one, so the obvious "country first, else postal" fallback treats a French
    party whose country was unreadable exactly like a Spanish one. Gating on the
    country evidence POSITIVELY naming Spain is what closes it, which is why
    telling those three outcomes apart is load-bearing rather than cosmetic.
    """
    assembly = _assemble_with_declared(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code=None,
        issuer_postal_code=postal_code,
        customer_country_code="FR",
        asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    )

    assert not assembly.assembled, f"a {city} postal code was accepted as Spanish establishment evidence"
    gap = next(m for m in assembly.missing if m.field == "issuer_residency")
    assert "no country code" in gap.reason


def test_a_malformed_country_code_is_not_reported_as_naming_spain() -> None:
    """The collapsed-outcome defect: three different situations wore one answer.

    The country resolver returns nothing for an absent code, a malformed one AND
    a Spanish one alike, so a refusal that branched on the code merely being
    present told the operator that a malformed code named Spain. It becomes
    load-bearing the moment anything gates the postal join on whether the
    country evidence named Spain, which is what this test does.

    ``ESP`` rather than ``XX``: a well-formed but unlisted alpha-2 code resolves
    to THIRD_COUNTRY and never reaches this branch, so it would prove nothing.
    """
    assembly = _assemble_with_declared(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="ESP",
        issuer_postal_code="28013",
        customer_country_code="FR",
        asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
    )

    assert not assembly.assembled
    gap = next(m for m in assembly.missing if m.field == "issuer_residency")
    assert "names Spain" not in gap.reason, gap.reason
    assert "ESP" in gap.reason


def test_each_refusal_distinguishes_why_the_country_evidence_failed() -> None:
    """Absent, malformed and Spanish must read as three different refusals.

    An operator fixes what the refusal names. One shared message for three
    causes sends them to correct a country code that was already correct, or to
    supply a postal code for a party whose country was never established.
    """
    reasons = {}
    for label, country, postal in (
        ("absent", None, "28013"),
        ("malformed", "ESP", "28013"),
        ("spanish", "ES", None),
    ):
        assembly = _assemble_with_declared(
            transaction_date=_DATE,
            direction=InvoiceKind.ISSUED,
            inputs=_inputs(),
            supply_nature=SupplyNature.GOODS,
            issuer_country_code=country,
            issuer_postal_code=postal,
            customer_country_code="FR",
            asserted_customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
        )
        reasons[label] = next(m for m in assembly.missing if m.field == "issuer_residency").reason

    assert len(set(reasons.values())) == 3, reasons
    assert "three IVA territories" in reasons["spanish"]


def _domestic(**overrides: object):
    """An ES-to-ES operation, which is the shape the customer-status demand blocked."""
    kwargs: dict[str, object] = {
        "customer_country_code": None,
        "asserted_issuer_scope": IvaTerritorialScope.ES_MAINLAND,
        "asserted_customer_scope": IvaTerritorialScope.ES_MAINLAND,
        "rate_tier": IvaRateKind.GENERAL,
    }
    kwargs.update(overrides)
    return _complete(**kwargs)


def test_an_ordinary_domestic_invoice_is_never_asked_for_the_customer_status() -> None:
    """The payoff. A demand with no consequence blocked the commonest document there is.

    The domestic rule reads the customer's status ONLY to route the three
    reverse-charge kinds and the exempt immovable supply, and a printed
    goods-or-services reading produces none of them. So every status reaches the
    same category and the question could not have mattered.
    """
    assembly = _domestic(asserted_customer_tax_status=None, supply_nature=None)

    assert "customer_tax_status" not in {m.field for m in assembly.missing}
    assert assembly.assembled, [m.field for m in assembly.missing]


def test_an_unestablished_status_is_stamped_as_unresolved_not_as_a_business() -> None:
    """The safety asymmetry, asserted on the VALUE and not merely on the verdict.

    Where the probe certifies indifference, a substantive placeholder would reach
    the same category — so a category-only assertion cannot see this, and did not:
    swapping the placeholder to ``B2B_IVA_REGISTERED`` left every other gate in
    this file green. The harm is not the verdict but the record. The criteria
    carry the status onward to whatever reads the field rather than the category,
    so a substantive placeholder writes a claim about the customer that nobody
    made, on the commonest document there is.
    """
    assembly = _domestic(asserted_customer_tax_status=None, supply_nature=None)

    assert assembly.criteria is not None
    assert assembly.criteria.customer_tax_status is CustomerTaxStatus.UNKNOWN, (
        f"an unestablished status was stamped as {assembly.criteria.customer_tax_status}"
    )


def test_the_undetermined_status_placeholder_never_changes_the_outcome() -> None:
    """Asserting it assembled leaves the placeholder unguarded.

    A value that quietly selected a reverse-charge or exempt branch would still
    assemble and would still be wrong, so the placeholder's verdict is compared
    against every substantive status the customer could actually have.
    """
    placeholder = classify_from_assembled_criteria(_domestic(asserted_customer_tax_status=None, supply_nature=None))

    assert placeholder is not None
    for status in CustomerTaxStatus:
        if status is CustomerTaxStatus.UNKNOWN:
            continue
        stated = classify_from_assembled_criteria(_domestic(asserted_customer_tax_status=status, supply_nature=None))
        assert stated is not None
        assert placeholder.category is stated.category, (
            f"the undetermined-status placeholder changed the outcome under {status}: "
            f"{placeholder.category} vs {stated.category}"
        )


def test_an_intra_community_operation_still_demands_the_customer_status() -> None:
    """The expensive refusal must survive the laziness, on a PLACED operation.

    The art. 25 exemption turns on the registered status, so skipping the demand
    here would zero-rate a taxable sale on evidence nobody verified. This is the
    positive control for the laziness above: without it, a producer that simply
    stopped asking would pass every domestic assertion in this file.
    """
    assembly = _complete(asserted_customer_tax_status=None)

    assert not assembly.assembled
    gap = next(m for m in assembly.missing if m.field == "customer_tax_status")
    assert "not a valid registration" in gap.reason
    assert "VIES" in gap.settled_by


def test_an_unplaced_operation_is_not_certified_indifferent() -> None:
    """Identical-because-unplaced must not read as identical-because-it-cannot-matter.

    A DE-to-FR pair matches no rule at all, so all five statuses agree on the
    fallthrough sentinel. That agreement says nothing whatever about the status
    mattering, and a probe reading it as indifference would assemble an operation
    the table never placed and stamp a sentinel category onto a filing.
    """
    assembly = _assemble_with_declared(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_inputs(),
        supply_nature=SupplyNature.GOODS,
        issuer_country_code="DE",
        customer_country_code="FR",
    )

    assert not assembly.assembled
    assert "customer_tax_status" in {m.field for m in assembly.missing}


def test_the_undetermined_status_can_only_ride_status_blind_rules() -> None:
    """The safety asymmetry, asserted structurally rather than left to the probe.

    ``UNKNOWN`` is supplied where nobody established a status, so it must never
    be what TRIGGERS a rule. Sweeping the table: wherever ``UNKNOWN`` matches a
    real rule, every other status must match that same rule -- meaning the rule
    does not read the status at all. Anywhere the status does matter, ``UNKNOWN``
    may only reach the no-rule-matched fallthrough.

    Stronger than the indifference probe, which certifies one operation at a
    time. This reds if anyone ever admits ``UNKNOWN`` into a substantive rule's
    accepted set, whether or not the assembly happens to reach that rule today.

    **The closing assertion is on what the sweep VERIFIED, never on what it
    visited.** It previously counted shapes and compared the count to the loop
    bounds, incrementing before the fallthrough ``continue`` — so it equalled the
    product of the iterables unconditionally and could not fail. Emptying the rule
    table, which sends every shape to the fallthrough and skips the inner check
    entirely, still left it passing: a sweep that verified nothing reported
    success.

    A tally of shapes visited is structurally incapable of detecting that,
    because the shapes it counts are exactly the ones the check skips. So the
    property replaces it: at least one rule must have been ridden by ``UNKNOWN``
    without reading the status, which is false precisely when the inner assertion
    never ran. The set is deliberately not compared against a fixed size — a rule
    entering or leaving the table is a legitimate change, while verifying nothing
    never is.
    """
    from ....domain.iva import EUMemberState, IvaInvoiceClassificationCriteria, classify_iva

    fallthrough = "R99_fallthrough"
    reachable_kinds = (TransactionKind.GOODS, TransactionKind.SERVICES_GENERAL)
    ridden_without_reading_the_status: set[str] = set()

    def _rule(status: CustomerTaxStatus, issuer, customer, kind, direction) -> str:
        return classify_iva(
            IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=issuer,
                customer_residency=customer,
                customer_tax_status=status,
                kind=kind,
                direction=direction,
                issuer_identification_state=EUMemberState.DE if issuer is IvaTerritorialScope.EU_MEMBER else None,
                customer_identification_state=EUMemberState.FR if customer is IvaTerritorialScope.EU_MEMBER else None,
                rate_tier=IvaRateKind.GENERAL,
            ),
        ).matched_rule_id

    for issuer in IvaTerritorialScope:
        for customer in IvaTerritorialScope:
            for kind in reachable_kinds:
                for direction in InvoiceKind:
                    shape = (issuer, customer, kind, direction)
                    matched = _rule(CustomerTaxStatus.UNKNOWN, *shape)
                    if matched == fallthrough:
                        continue
                    ridden_without_reading_the_status.add(matched)
                    for status in CustomerTaxStatus:
                        assert _rule(status, *shape) == matched, (
                            f"UNKNOWN matched {matched} on {shape} but {status} does not: "
                            "the rule reads the customer status, so UNKNOWN triggered it"
                        )

    assert ridden_without_reading_the_status, (
        "the sweep verified nothing: UNKNOWN reached the no-rule-matched fallthrough on every "
        "shape, so the status-blindness assertion never executed once"
    )
