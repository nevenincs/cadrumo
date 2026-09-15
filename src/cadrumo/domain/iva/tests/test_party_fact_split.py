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

from collections.abc import Iterator
from datetime import date

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.calculations.registry.tests.published_authority import PublishedGovernedFactSource

from ...calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ...calculations.registry.schema_base import DateAxis
from ..classification import (
    CustomerTaxStatus,
    InvoiceKind,
    IvaInvoiceClassificationCriteria,
    IvaTerritorialScope,
    PartyFact,
    TransactionKind,
)
from ..errors import IvaValidationError
from ..identification import identification_state_for_printed_tax_identifier
from ..schema import EUMemberState, IvaCategory, IvaRateKind
from .classification_authority_support import classify_with_registry_rules

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module", autouse=True)
def _registry_authority_scope() -> Iterator[None]:
    with _indexed_authority_for_test().operation():
        yield


_DATE = date(2026, 3, 10)


def _classification_fact_entries(*, on: date) -> dict[str, str]:
    """Resolve the published classification declaration at its filing coordinate."""
    resolved = PublishedGovernedFactSource().resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-invoice-classification-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=on,
        ),
    )
    assert isinstance(resolved, ResolvedMappingFact)
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        assert isinstance(entry.key, str) and isinstance(entry.value, str)
        entries[entry.key] = entry.value
    return entries


def _classification_rule_consumptions(*, on: date) -> dict[str, frozenset[PartyFact]]:
    """Read each non-terminal rule's declared party-fact consumption from authority."""
    entries = _classification_fact_entries(on=on)
    rule_order = entries["rule_order"].split(",")
    return {
        rule_id: frozenset(PartyFact(fact) for fact in entries[f"rule.{rule_id}.consumes"].split(","))
        for rule_id in rule_order
        if f"rule.{rule_id}.consumes" in entries
    }


#: A structurally valid German IVA number, and a Spanish CIF for the same party
#: shape. Both are registrations; the point of every case below is that they are
#: registrations and nothing more.
_GERMAN_IVA_NUMBER = "DE811234567"
_SPANISH_CIF = "B12345678"


class TestRegistrationEvidenceSettlesTheIdentificationState:
    """The fact registration IS evidence of — decisively, with nothing to corroborate."""

    def test_a_printed_foreign_iva_number_names_its_member_state(self) -> None:
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert identification_state_for_printed_tax_identifier(
                _GERMAN_IVA_NUMBER, operation=_authority_operation_for_test
            ) == EUMemberState.from_registry("de")

    def test_a_greek_number_resolves_to_its_iso_code_not_its_iva_prefix(self) -> None:
        """``EL`` leads the number while ``GR`` keys every catalogue downstream."""
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert identification_state_for_printed_tax_identifier(
                "EL123456789", operation=_authority_operation_for_test
            ) == EUMemberState.from_registry("gr")

    def test_a_number_whose_body_contradicts_its_prefix_establishes_nothing(self) -> None:
        """The prefix alone is not evidence; ``FRANCISCO`` must not identify France."""
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert (
                identification_state_for_printed_tax_identifier("FRANCISCO", operation=_authority_operation_for_test)
                is None
            )

    def test_absence_never_manufactures_a_spanish_identification(self) -> None:
        """A bare Spanish CIF prints no prefix, and silence is not a registration."""
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            assert (
                identification_state_for_printed_tax_identifier(_SPANISH_CIF, operation=_authority_operation_for_test)
                is None
            )
            assert (
                identification_state_for_printed_tax_identifier(None, operation=_authority_operation_for_test) is None
            )


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
            issuer_residency=IvaTerritorialScope.from_registry("es_mainland"),
            customer_residency=IvaTerritorialScope.from_registry("es_mainland"),
            customer_identification_state=EUMemberState.from_registry("de"),
            customer_tax_status=CustomerTaxStatus.from_registry("b2b_iva_registered"),
            kind=TransactionKind("goods"),
            direction=InvoiceKind.ISSUED,
            rate_tier=IvaRateKind("general"),
        )
        assert criteria.customer_identification_state == EUMemberState.from_registry("de")
        assert criteria.customer_residency == IvaTerritorialScope.from_registry("es_mainland")

    def test_a_foreign_establishment_does_not_require_an_identification_state(self) -> None:
        """The removed coupling, from the other side: EU_MEMBER with no State named.

        This construction raised before the split. It must not now, because the
        demand for an identification belongs to the branches that report against
        a NIF-IVA, not to the fact that a party is abroad.
        """
        criteria = IvaInvoiceClassificationCriteria(
            transaction_date=_DATE,
            issuer_residency=IvaTerritorialScope.from_registry("es_mainland"),
            customer_residency=IvaTerritorialScope.from_registry("eu_member"),
            customer_tax_status=CustomerTaxStatus.from_registry("b2b_iva_registered"),
            kind=TransactionKind("goods"),
            direction=InvoiceKind.ISSUED,
        )
        assert criteria.customer_identification_state is None

    def test_a_spanish_party_may_hold_a_foreign_identification_and_stay_spanish(self) -> None:
        """The Spanish side, unchanged: registration abroad displaces no territory."""
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            criteria = IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.from_registry("es_canarias"),
                customer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                issuer_identification_state=EUMemberState.from_registry("de"),
                customer_tax_status=CustomerTaxStatus.from_registry("b2c_consumer"),
                kind=TransactionKind("goods"),
                direction=InvoiceKind.ISSUED,
                rate_tier=IvaRateKind("general"),
            )
            assert classify_with_registry_rules(
                criteria, operation=_authority_operation_for_test
            ).category == IvaCategory("domestic_not_subject")


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
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            criteria = IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                customer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                issuer_identification_state=EUMemberState.from_registry("de"),
                customer_identification_state=EUMemberState.from_registry("de"),
                customer_tax_status=CustomerTaxStatus.from_registry("b2b_iva_registered"),
                kind=TransactionKind("goods"),
                direction=InvoiceKind.ISSUED,
            )
            with pytest.raises(IvaValidationError, match="rate/category mapping"):
                classify_with_registry_rules(criteria, operation=_authority_operation_for_test)

    def test_the_refusal_is_unchanged_for_a_party_carrying_no_identification(self) -> None:
        """The control: the same operation without the identification refuses identically.

        Paired with the case above so the pair discriminates. If the refusal
        depended on the identification in either direction — firing only with one
        present, or only with one absent — exactly one of these two would fail.
        """
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            criteria = IvaInvoiceClassificationCriteria(
                transaction_date=_DATE,
                issuer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                customer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                customer_tax_status=CustomerTaxStatus.from_registry("b2b_iva_registered"),
                kind=TransactionKind("goods"),
                direction=InvoiceKind.ISSUED,
            )
            with pytest.raises(IvaValidationError, match="rate/category mapping"):
                classify_with_registry_rules(criteria, operation=_authority_operation_for_test)


class TestEveryBranchDeclaresWhatItConsumes:
    """The declaration is the mechanism; an undeclared branch is not a silent branch."""

    def test_every_rule_consumes_the_establishment(self) -> None:
        """Every predicate reads the residencies, so every row declares the place."""
        undeclared = [
            rule_id
            for rule_id, consumes in _classification_rule_consumptions(on=_DATE).items()
            if PartyFact.TERRITORIAL_ESTABLISHMENT not in consumes
        ]
        assert undeclared == []

    def test_no_rule_declares_an_empty_or_unknown_consumption(self) -> None:
        for rule_id, consumes in _classification_rule_consumptions(on=_DATE).items():
            assert consumes, f"{rule_id} declares no party fact and would demand nothing"
            assert consumes <= frozenset(PartyFact), rule_id

    def test_the_intra_community_branches_are_the_ones_needing_the_identification(self) -> None:
        """The families reported against a NIF-IVA, and no others.

        The registry predicate independently identifies branches requiring
        another Member State, so the assertion does not compare ``consumes``
        to itself.
        """
        entries = _classification_fact_entries(on=_DATE)
        declaring = {
            rule_id
            for rule_id, consumes in _classification_rule_consumptions(on=_DATE).items()
            if PartyFact.IVA_IDENTIFICATION_STATE in consumes
        }
        expected = {
            rule_id
            for rule_id in entries["rule_order"].split(",")
            if "identification=other_member_state" in entries.get(f"rule.{rule_id}.predicate", "")
        }
        assert expected
        assert declaring == expected

    def test_a_domestic_operation_reports_needing_only_the_establishment(self) -> None:
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            result = classify_with_registry_rules(
                IvaInvoiceClassificationCriteria(
                    transaction_date=_DATE,
                    issuer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                    customer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                    customer_tax_status=CustomerTaxStatus.from_registry("b2b_iva_registered"),
                    kind=TransactionKind("goods"),
                    direction=InvoiceKind.ISSUED,
                    rate_tier=IvaRateKind("general"),
                ),
                operation=_authority_operation_for_test,
            )
            assert result.consumes_party_facts == frozenset({PartyFact.TERRITORIAL_ESTABLISHMENT})

    def test_an_intra_community_supply_reports_needing_the_identification(self) -> None:
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            result = classify_with_registry_rules(
                IvaInvoiceClassificationCriteria(
                    transaction_date=_DATE,
                    issuer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                    customer_residency=IvaTerritorialScope.from_registry("eu_member"),
                    customer_identification_state=EUMemberState.from_registry("de"),
                    customer_tax_status=CustomerTaxStatus.from_registry("b2b_iva_registered"),
                    kind=TransactionKind("goods"),
                    direction=InvoiceKind.ISSUED,
                ),
                operation=_authority_operation_for_test,
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
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            result = classify_with_registry_rules(
                IvaInvoiceClassificationCriteria(
                    transaction_date=_DATE,
                    issuer_residency=IvaTerritorialScope.from_registry("eu_member"),
                    customer_residency=IvaTerritorialScope.from_registry("eu_member"),
                    customer_tax_status=CustomerTaxStatus.from_registry("b2b_iva_registered"),
                    kind=TransactionKind("goods"),
                    direction=InvoiceKind.ISSUED,
                ),
                operation=_authority_operation_for_test,
            )
            assert result.category == IvaCategory("unknown")
            assert result.consumes_party_facts == frozenset(PartyFact)

    def test_a_result_that_declares_nothing_defaults_to_demanding_everything(self) -> None:
        """The fail-toward-asking default, so a forgotten declaration costs a question."""
        from ..classification import IvaClassificationResult

        bare = IvaClassificationResult(category=IvaCategory("unknown"), matched_rule_id="R99_fallthrough")
        assert bare.consumes_party_facts == frozenset(PartyFact)


class TestTheRateScheduleFollowsTheEstablishmentNotTheIdentification:
    """Where the split reaches the money.

    The rate a supply bears is fixed by the territory that taxes it. Keying the
    lookup on the identification State would price a domestic Spanish supply off
    the German schedule for exactly the population the split exists to describe.
    """

    def test_a_german_identified_spanish_issuer_is_priced_on_the_spanish_schedule(self) -> None:
        with _indexed_authority_for_test().operation() as _authority_operation_for_test:
            spanish_only = classify_with_registry_rules(
                IvaInvoiceClassificationCriteria(
                    transaction_date=_DATE,
                    issuer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                    customer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                    customer_tax_status=CustomerTaxStatus.from_registry("b2c_consumer"),
                    kind=TransactionKind("goods"),
                    direction=InvoiceKind.ISSUED,
                    rate_tier=IvaRateKind("general"),
                ),
                operation=_authority_operation_for_test,
            )
            german_identified = classify_with_registry_rules(
                IvaInvoiceClassificationCriteria(
                    transaction_date=_DATE,
                    issuer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                    customer_residency=IvaTerritorialScope.from_registry("es_mainland"),
                    issuer_identification_state=EUMemberState.from_registry("de"),
                    customer_tax_status=CustomerTaxStatus.from_registry("b2c_consumer"),
                    kind=TransactionKind("goods"),
                    direction=InvoiceKind.ISSUED,
                    rate_tier=IvaRateKind("general"),
                ),
                operation=_authority_operation_for_test,
            )
            assert spanish_only.rate is not None
            assert german_identified.rate == spanish_only.rate
