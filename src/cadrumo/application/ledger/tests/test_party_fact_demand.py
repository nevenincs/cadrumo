"""The producer demands a party's identifying State only where the branch needs it.

Two properties, and they fail in opposite directions.

**A registration must not settle a place, on either side.** The producer resolves
the identification from the party's own printed IVA number and the establishment
from country and postal evidence, and neither evidence crosses. Every case is
asserted from both sides: proving only that a German number stopped establishing
Germany would be satisfied by a repair that made the Spanish side stricter, and
the Spanish side was already right. What is wrong is asymmetry, not one rung.

**And a fact nobody's branch turns on must not be demanded.** The whole cost of
splitting the fact would be handed straight back if the producer asked every
document for a NIF-IVA: the foreign goods population resolves with no operator
question precisely because the prefix was never a proxy there, and a domestic
invoice must not be asked for a number its treatment does not consult.

The demand is read from the rule table's own declaration rather than restated
here, so no assertion below hand-derives a category from the table under test.

Model-free and network-free: typed construction and pure assembly calls.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    bundled_indexed_authority,
)
from cadrumo.domain.iva.schema import IvaRateKind

from ....core.classifier_input_source import ClassifierInputSource, CounterpartyTaxablePersonStatus
from ....domain.calculations.registry.eu_member_state_catalogue import require_eu_member_state
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.classification import (
    CustomerTaxStatus,
    IvaInvoiceClassificationCriteria,
    PartyFact,
    TransactionKind,
    classify_iva,
    resolve_iva_classification_inputs,
)
from ....domain.iva.schema import InvoiceKind, IvaCategory, IvaTerritorialScope
from ....domain.iva.supply_nature import SupplyNature
from ..classification_assembly import (
    ClassificationAssembly,
    DeclaredFact,
    DeclaredFacts,
    assemble_classification_criteria,
)
from ..classifier_inputs import ClassifierInputs

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DATE = date(_YEAR, 3, 10)
_ASSERTED = ClassifierInputSource.OPERATOR_ASSERTION

_GERMAN_IVA_NUMBER = "DE811234567"
_SPANISH_CIF = "B12345678"

_TAXABLE = ClassifierInputs(counterparty_taxable_person=CounterpartyTaxablePersonStatus.TAXABLE_PERSON)


def _missing_fields(
    *, declared: DeclaredFacts, customer_identifier: str | None = None, operation: PinnedAuthorityOperation
) -> set[str]:
    """Return which criteria fields one assembly attempt could not fill."""
    assembly = assemble_classification_criteria(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_TAXABLE,
        declared=declared,
        customer_identifier=customer_identifier,
        operation=operation,
    )
    return {gap.field for gap in assembly.missing}


def _assemble_goods(
    operation: PinnedAuthorityOperation,
    customer_tax_status: str,
    issuer_scope: str,
    customer_scope: str,
    *,
    identification_state: str | None = None,
    customer_identifier: str | None = None,
    rate_tier: IvaRateKind | None = None,
) -> ClassificationAssembly:
    """Assemble an issued goods supply whose every declared fact is an operator assertion."""
    declared = DeclaredFacts(
        supply_nature=DeclaredFact(value=SupplyNature.GOODS, source=_ASSERTED),
        customer_tax_status=DeclaredFact(value=CustomerTaxStatus.from_registry(customer_tax_status), source=_ASSERTED),
        issuer_scope=DeclaredFact(value=IvaTerritorialScope.from_registry(issuer_scope), source=_ASSERTED),
        customer_scope=DeclaredFact(value=IvaTerritorialScope.from_registry(customer_scope), source=_ASSERTED),
        customer_identification_state=(
            None
            if identification_state is None
            else DeclaredFact(value=require_eu_member_state(identification_state), source=_ASSERTED)
        ),
    )
    return assemble_classification_criteria(
        transaction_date=_DATE,
        direction=InvoiceKind.ISSUED,
        inputs=_TAXABLE,
        declared=declared,
        customer_identifier=customer_identifier,
        rate_tier=rate_tier,
        operation=operation,
    )


class TestARegistrationSettlesNoPlace:
    """Symmetrically: the foreign side must stop being decisive, the Spanish side stay refused."""

    def test_a_printed_german_number_alone_leaves_the_establishment_unsettled(
        self, *, operation: PinnedAuthorityOperation
    ) -> None:
        """The failure that produced this split: it used to resolve silently to EU_MEMBER."""
        assert "customer_residency" in _missing_fields(
            declared=DeclaredFacts(),
            customer_identifier=_GERMAN_IVA_NUMBER,
            operation=operation,
        )

    def test_a_printed_spanish_number_alone_leaves_the_establishment_unsettled(
        self, *, operation: PinnedAuthorityOperation
    ) -> None:
        """The side that already failed loud, pinned unchanged by the same assertion."""
        assert "customer_residency" in _missing_fields(
            declared=DeclaredFacts(),
            customer_identifier=_SPANISH_CIF,
            operation=operation,
        )

    def test_the_two_sides_report_the_same_establishment_gaps(self, *, operation: PinnedAuthorityOperation) -> None:
        """The symmetry itself, rather than each side separately.

        A repair that made one side safe by tightening the other would satisfy
        both cases above and fail here. Compared over the ESTABLISHMENT fields
        only, and that scoping is the point rather than a convenience: the two
        registrations are deliberately NOT equivalent for identification — the
        German number settles it and the Spanish one prints no prefix to settle
        it with — so demanding equality there would assert the conflation this
        gate exists to refuse.
        """
        establishment_fields = {"issuer_residency", "customer_residency"}
        german = _missing_fields(declared=DeclaredFacts(), customer_identifier=_GERMAN_IVA_NUMBER, operation=operation)
        spanish = _missing_fields(declared=DeclaredFacts(), customer_identifier=_SPANISH_CIF, operation=operation)
        assert german & establishment_fields == spanish & establishment_fields == establishment_fields

    def test_an_asserted_establishment_does_not_supply_an_identification(self) -> None:
        """The inverse crossing, closed on the same principle.

        An operator saying where a party operates from has not said which State
        registered it, so an intra-community branch still has to ask.
        """
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            assembly = _assemble_goods(_authority_operation_for_test, "b2b_iva_registered", "es_mainland", "eu_member")
            assert not assembly.assembled
            assert {gap.field for gap in assembly.missing} == {"customer_identification_state"}


class TestTheIdentificationIsDemandedOnlyByBranchesThatConsumeIt:
    """The lazy requirement, extended to the new axis through the table's declaration."""

    def test_a_domestic_operation_assembles_with_no_identification_anywhere(self) -> None:
        """The commonest document there is. Asking it for a NIF-IVA would be noise."""
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            assembly = _assemble_goods(
                _authority_operation_for_test,
                "b2c_consumer",
                "es_mainland",
                "es_mainland",
                rate_tier=IvaRateKind("general"),
            )
            assert assembly.assembled, [gap.field for gap in assembly.missing]
            assert assembly.criteria is not None
            assert assembly.criteria.customer_identification_state is None

    def test_the_foreign_goods_population_still_resolves_with_no_operator_question(self) -> None:
        """The cost the split was designed to preserve.

        An intra-community supply DOES consume the identification — and the
        printed number supplies it, because for this branch the prefix was never
        a proxy for anything. It was the operative fact.
        """
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            assembly = _assemble_goods(
                _authority_operation_for_test,
                "b2b_iva_registered",
                "es_mainland",
                "eu_member",
                customer_identifier=_GERMAN_IVA_NUMBER,
            )
            assert assembly.assembled, [gap.field for gap in assembly.missing]
            assert assembly.criteria is not None
            assert assembly.criteria.customer_identification_state == require_eu_member_state("DE")

    def test_an_intra_community_branch_with_no_printed_number_asks(self) -> None:
        """The same operation without the evidence: a question, never a blank."""
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            assembly = _assemble_goods(_authority_operation_for_test, "b2b_iva_registered", "es_mainland", "eu_member")
            assert not assembly.assembled
            gap = next(item for item in assembly.missing if item.field == "customer_identification_state")
            assert gap.settled_by

    def test_an_operator_assertion_settles_it_where_no_number_was_printed(self) -> None:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            assembly = _assemble_goods(
                _authority_operation_for_test,
                "b2b_iva_registered",
                "es_mainland",
                "eu_member",
                identification_state="FR",
            )
            assert assembly.assembled, [gap.field for gap in assembly.missing]
            assert assembly.criteria is not None
            assert assembly.criteria.customer_identification_state == require_eu_member_state("FR")


class TestTheUnplacedOperationGuardCoversTheNewAxis:
    """An operation the table places nowhere must be asked, not certified indifferent.

    The measured shape is a DE-to-FR pair: it reaches the fallthrough for every
    candidate value, and reading that uniform agreement as "nothing further was
    needed" would assemble an operation the table never placed.
    """

    def test_an_unplaced_operation_demands_the_identification(self) -> None:
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            assembly = _assemble_goods(_authority_operation_for_test, "b2b_iva_registered", "eu_member", "eu_member")
            assert not assembly.assembled
            assert "customer_identification_state" in {gap.field for gap in assembly.missing}

    def test_the_guard_is_the_tables_declaration_not_a_local_branch(self) -> None:
        """The demand tracks what the fallthrough declares, so one authority moves both.

        Read through the public result rather than restated: if the sentinel
        stopped declaring both facts, this and the producer would change
        together instead of drifting.
        """
        with bundled_indexed_authority().operation() as _authority_operation_for_test:
            projected = resolve_iva_classification_inputs(effective_date=_DATE, operation=_authority_operation_for_test)
            unplaced = classify_iva(
                IvaInvoiceClassificationCriteria(
                    transaction_date=_DATE,
                    issuer_residency=IvaTerritorialScope.from_registry("eu_member"),
                    customer_residency=IvaTerritorialScope.from_registry("eu_member"),
                    customer_tax_status=CustomerTaxStatus.from_registry("b2b_iva_registered"),
                    kind=TransactionKind("goods"),
                    direction=InvoiceKind.ISSUED,
                ),
                operation=_authority_operation_for_test,
                rules=projected.rules,
                rate_categories=projected.rate_categories,
                rate_territories=projected.rate_territories,
            )
            assert unplaced.category == IvaCategory("unknown")
            assert PartyFact.IVA_IDENTIFICATION_STATE in unplaced.consumes_party_facts
