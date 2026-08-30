"""Registration settles the identifying State and settles NO place, on either side.

The ladder these facts feed once answered two legally distinct questions with one
output, and the conflation had a direction. A printed foreign IVA prefix was read
as decisive evidence of PLACE, so a German-identified entity actually established
in Spain resolved silently to ``EU_MEMBER`` and reached the table as settled
fact — while the mirror case, a non-resident holding a Spanish registration,
correctly refused and surfaced to the operator. One side failed loud and the
other failed silent on the same underlying situation.

**So every case here is asserted in BOTH directions.** A gate that only proved
the foreign side had stopped being decisive would be satisfied by a fix that made
the Spanish side stricter, which is the wrong repair: the two sides are one
principle, and the principle is that registration evidences registration.

Nothing here computes a tax figure. What is under test is which FACT a branch
turns on, so the assertions are about declarations and about which axis moves a
verdict — a category asserted against a number hand-derived from this same table
would prove only that the table equals itself.
"""

from __future__ import annotations

from datetime import date

import pytest

from ..classification import (
    _CLASSIFICATION_RULES,
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    PartyFact,
    TransactionKind,
    classify_iva,
)
from ..identification import identification_state_for_printed_tax_identifier
from ..schema import EUMemberState, IvaCategory, IvaRateKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DATE = date(2026, 3, 10)

#: A structurally valid German IVA number, and a Spanish CIF for the same party
#: shape. Both are registrations; the point of every case below is that they are
#: registrations and nothing more.
_GERMAN_IVA_NUMBER = "DE811234567"
_SPANISH_CIF = "B12345678"


class TestRegistrationEvidenceSettlesTheIdentificationState:
    """The fact registration IS evidence of — decisively, with nothing to corroborate."""

    def test_a_printed_foreign_iva_number_names_its_member_state(self) -> None:
        assert identification_state_for_printed_tax_identifier(_GERMAN_IVA_NUMBER) is EUMemberState.DE

    def test_a_greek_number_resolves_to_its_iso_code_not_its_iva_prefix(self) -> None:
        """``EL`` leads the number while ``GR`` keys every catalogue downstream."""
        assert identification_state_for_printed_tax_identifier("EL123456789") is EUMemberState.GR

    def test_a_number_whose_body_contradicts_its_prefix_establishes_nothing(self) -> None:
        """The prefix alone is not evidence; ``FRANCISCO`` must not identify France."""
        assert identification_state_for_printed_tax_identifier("FRANCISCO") is None

    def test_absence_never_manufactures_a_spanish_identification(self) -> None:
        """A bare Spanish CIF prints no prefix, and silence is not a registration."""
        assert identification_state_for_printed_tax_identifier(_SPANISH_CIF) is None
        assert identification_state_for_printed_tax_identifier(None) is None


class TestNoRegistrationEvidencesEstablishment:
    """The symmetry, asserted from both sides of it.

    The criteria model is where the conflation was structurally possible: while
    an EU establishment REQUIRED an identification state, holding one implied the
    other and a producer had to invent whichever it lacked.
    """

    def test_a_foreign_identification_does_not_require_or_imply_a_foreign_establishment(self) -> None:
        """The dangerous population: German-identified, established in Spain."""
        criteria = IvaInvoiceClassificationCriteria(
            transaction_date=_DATE,
            issuer_residency=IvaTerritorialScope.ES_MAINLAND,
            customer_residency=IvaTerritorialScope.ES_MAINLAND,
            customer_identification_state=EUMemberState.DE,
            customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.ISSUED,
            rate_tier=IvaRateKind.GENERAL,
        )
        assert criteria.customer_identification_state is EUMemberState.DE
        assert criteria.customer_residency is IvaTerritorialScope.ES_MAINLAND

    def test_a_foreign_establishment_does_not_require_an_identification_state(self) -> None:
        """The removed coupling, from the other side: EU_MEMBER with no State named.

        This construction raised before the split. It must not now, because the
        demand for an identification belongs to the branches that report against
        a NIF-IVA, not to the fact that a party is abroad.
        """
        criteria = IvaInvoiceClassificationCriteria(
            transaction_date=_DATE,
            issuer_residency=IvaTerritorialScope.ES_MAINLAND,
            customer_residency=IvaTerritorialScope.EU_MEMBER,
            customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.ISSUED,
        )
        assert criteria.customer_identification_state is None

    def test_a_spanish_party_may_hold_a_foreign_identification_and_stay_spanish(self) -> None:
        """The Spanish side, unchanged: registration abroad displaces no territory."""
        criteria = IvaInvoiceClassificationCriteria(
            transaction_date=_DATE,
            issuer_residency=IvaTerritorialScope.ES_CANARIAS,
            customer_residency=IvaTerritorialScope.ES_MAINLAND,
            issuer_identification_state=EUMemberState.DE,
            customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
            kind=TransactionKind.GOODS,
            direction=InvoiceKind.ISSUED,
            rate_tier=IvaRateKind.GENERAL,
        )
        assert classify_iva(criteria).category is IvaCategory.DOMESTIC_NOT_SUBJECT


class TestTheSplitRemovesNoRefusal:
    """The direction that produces no red, and which a green suite then certifies.

    Every other risk this split carries is a WRONG ANSWER, which surfaces. This
    one is a GUARD THAT STOPS RUNNING, and nothing announces it.

    The rate-tier refusal fires for ES-to-ES domestic operations, keyed on the
    residency fields. Those fields are the ESTABLISHMENT fact, so the refusal is
    already stated in the vocabulary the split leaves it in — but only an
    assertion makes that durable. Restating "ES-to-ES" in terms of the
    identification state, or keying it on either fact indifferently, would stop
    it firing for exactly the population the split exists to describe: a party
    identified in Germany and established in Spain, whose domestic supply is
    taxed at Spanish rates and therefore needs a tier as much as any other.
    """

    def test_a_german_identified_spanish_established_party_still_needs_a_rate_tier(self) -> None:
        with pytest.raises(ValueError, match="rate_tier is required"):
            IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.ES_MAINLAND,
                customer_residency=IvaTerritorialScope.ES_MAINLAND,
                issuer_identification_state=EUMemberState.DE,
                customer_identification_state=EUMemberState.DE,
                customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
                kind=TransactionKind.GOODS,
                direction=InvoiceKind.ISSUED,
            )

    def test_the_refusal_is_unchanged_for_a_party_carrying_no_identification(self) -> None:
        """The control: the same operation without the identification refuses identically.

        Paired with the case above so the pair discriminates. If the refusal
        depended on the identification in either direction — firing only with one
        present, or only with one absent — exactly one of these two would fail.
        """
        with pytest.raises(ValueError, match="rate_tier is required"):
            IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.ES_MAINLAND,
                customer_residency=IvaTerritorialScope.ES_MAINLAND,
                customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
                kind=TransactionKind.GOODS,
                direction=InvoiceKind.ISSUED,
            )


class TestEveryBranchDeclaresWhatItConsumes:
    """The declaration is the mechanism; an undeclared branch is not a silent branch."""

    def test_every_rule_consumes_the_establishment(self) -> None:
        """Every predicate reads the residencies, so every row declares the place."""
        undeclared = [
            rule.rule_id for rule in _CLASSIFICATION_RULES if PartyFact.TERRITORIAL_ESTABLISHMENT not in rule.consumes
        ]
        assert undeclared == []

    def test_no_rule_declares_an_empty_or_unknown_consumption(self) -> None:
        for rule in _CLASSIFICATION_RULES:
            assert rule.consumes, f"{rule.rule_id} declares no party fact and would demand nothing"
            assert rule.consumes <= frozenset(PartyFact), rule.rule_id

    def test_the_intra_community_branches_are_the_ones_needing_the_identification(self) -> None:
        """The families reported against a NIF-IVA, and no others.

        Named by rule id rather than derived from the same ``consumes`` field
        under test: deriving the expectation from the declaration would assert
        the declaration equals itself.
        """
        declaring = {
            rule.rule_id for rule in _CLASSIFICATION_RULES if PartyFact.IVA_IDENTIFICATION_STATE in rule.consumes
        }
        assert declaring == {
            "R10_intra_community_supply",
            "R11_intra_community_acquisition",
            "R12_services_b2b_eu_outbound",
            "R13_services_b2b_eu_inbound",
        }

    def test_a_domestic_operation_reports_needing_only_the_establishment(self) -> None:
        result = classify_iva(
            IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.ES_MAINLAND,
                customer_residency=IvaTerritorialScope.ES_MAINLAND,
                customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
                kind=TransactionKind.GOODS,
                direction=InvoiceKind.ISSUED,
                rate_tier=IvaRateKind.GENERAL,
            ),
        )
        assert result.consumes_party_facts == frozenset({PartyFact.TERRITORIAL_ESTABLISHMENT})

    def test_an_intra_community_supply_reports_needing_the_identification(self) -> None:
        result = classify_iva(
            IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.ES_MAINLAND,
                customer_residency=IvaTerritorialScope.EU_MEMBER,
                customer_identification_state=EUMemberState.DE,
                customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
                kind=TransactionKind.GOODS,
                direction=InvoiceKind.ISSUED,
            ),
        )
        assert result.matched_rule_id == "R10_intra_community_supply"
        assert PartyFact.IVA_IDENTIFICATION_STATE in result.consumes_party_facts


class TestAnUnplacedOperationDemandsEverything:
    """The guard the sibling indifference probe already carries, on the new axis.

    An operation no rule places agrees with itself about everything, so a
    consumption set read off it would report a small, undemanding answer for the
    reason that nothing was decided rather than the reason that nothing was
    needed. The fallthrough therefore declares BOTH facts.
    """

    def test_the_fallthrough_declares_both_facts(self) -> None:
        result = classify_iva(
            IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.EU_MEMBER,
                customer_residency=IvaTerritorialScope.EU_MEMBER,
                customer_tax_status=CustomerTaxStatus.B2B_IVA_REGISTERED,
                kind=TransactionKind.GOODS,
                direction=InvoiceKind.ISSUED,
            ),
        )
        assert result.category is IvaCategory.UNKNOWN
        assert result.consumes_party_facts == frozenset(PartyFact)

    def test_a_result_that_declares_nothing_defaults_to_demanding_everything(self) -> None:
        """The fail-toward-asking default, so a forgotten declaration costs a question."""
        from ..classification import IvaClassificationResult

        bare = IvaClassificationResult(category=IvaCategory.UNKNOWN, matched_rule_id="R99_fallthrough")
        assert bare.consumes_party_facts == frozenset(PartyFact)


class TestTheRateScheduleFollowsTheEstablishmentNotTheIdentification:
    """Where the split reaches the money.

    The rate a supply bears is fixed by the territory that taxes it. Keying the
    lookup on the identification State would price a domestic Spanish supply off
    the German schedule for exactly the population the split exists to describe.
    """

    def test_a_german_identified_spanish_issuer_is_priced_on_the_spanish_schedule(self) -> None:
        spanish_only = classify_iva(
            IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.ES_MAINLAND,
                customer_residency=IvaTerritorialScope.ES_MAINLAND,
                customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
                kind=TransactionKind.GOODS,
                direction=InvoiceKind.ISSUED,
                rate_tier=IvaRateKind.GENERAL,
            ),
        )
        german_identified = classify_iva(
            IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.ES_MAINLAND,
                customer_residency=IvaTerritorialScope.ES_MAINLAND,
                issuer_identification_state=EUMemberState.DE,
                customer_tax_status=CustomerTaxStatus.B2C_CONSUMER,
                kind=TransactionKind.GOODS,
                direction=InvoiceKind.ISSUED,
                rate_tier=IvaRateKind.GENERAL,
            ),
        )
        assert spanish_only.rate is not None
        assert german_identified.rate == spanish_only.rate
