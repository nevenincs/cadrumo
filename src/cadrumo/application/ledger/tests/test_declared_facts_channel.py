"""One channel for supplied facts, carrying who supplied each one.

The assembly used to take three flat ``asserted_*`` parameters. They could carry
a VALUE but not its ATTRIBUTION, so by the time a criteria field existed nothing
recorded whether a human had claimed it or the page had stated it. An auditor
asking "why does this record say the customer is a consumer?" got the value back
and nothing else.

Two properties are gated here, and they fail differently.

**Extensible by FIELD, never by a second route.** The channel is a model rather
than more keyword parameters precisely so a later stage contributes a fact by
adding an attribute. If it has to invent a parallel supply route instead, the
attribution forks exactly the way the flat parameters forked it — and a fork is
invisible until someone asks who said what.

**One source vocabulary.** The channel reuses the shipped
:class:`~core.ClassifierInputSource` rather than declaring its own enum. A second
spelling of "who says so" beside the audit envelope's own is the duplication this
whole design exists to prevent, and it would be introduced by exactly the person
who thought a private two-member enum was tidier.

Model-free and network-free: typed construction and one pure assembly call.

See Also:
    :class:`~application.ledger.ClassifierInputFact`
        The audit envelope that speaks the same source vocabulary.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core import ClassifierInputSource
from ....domain.iva import CustomerTaxStatus, IvaTerritorialScope, SupplyNature
from ...invoices import InvoiceKind
from .._classification_assembly import (
    DeclaredFact,
    DeclaredFacts,
    assemble_classification_criteria,
)
from .._classifier_inputs import ClassifierInputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DATE = date(2026, 3, 10)
_ASSERTED = ClassifierInputSource.OPERATOR_ASSERTION
_FROM_DOCUMENT = ClassifierInputSource.DOCUMENT_EVIDENCE


class TestTheChannelCarriesAttributionBesideTheValue:
    """A supplied fact is two claims -- what, and who -- and they travel together."""

    def test_a_fact_keeps_the_source_that_supplied_it(self) -> None:
        operator = DeclaredFact(value=SupplyNature.GOODS, source=_ASSERTED)
        document = DeclaredFact(value=SupplyNature.GOODS, source=_FROM_DOCUMENT)

        assert operator.value is document.value
        assert operator.source is not document.source

    def test_the_same_value_from_two_sources_is_two_different_facts(self) -> None:
        """The property the flat parameters structurally could not express."""
        assert DeclaredFact(value=SupplyNature.SERVICES, source=_ASSERTED) != DeclaredFact(
            value=SupplyNature.SERVICES,
            source=_FROM_DOCUMENT,
        )

    def test_an_absent_fact_is_absent_rather_than_a_supplied_none(self) -> None:
        """Nobody established it, which the assembly reports rather than papers over."""
        assert DeclaredFacts().supply_nature is None

    def test_a_fact_cannot_be_supplied_without_naming_its_source(self) -> None:
        """The one thing the channel exists to make impossible."""
        with pytest.raises(Exception, match="source"):
            DeclaredFact(value=SupplyNature.GOODS)  # type: ignore[call-arg]


class TestTheChannelSpeaksTheShippedSourceVocabulary:
    """No second enum for "who says so"."""

    def test_the_source_type_is_the_shipped_classifier_input_source(self) -> None:
        fact = DeclaredFact(value=SupplyNature.GOODS, source=_ASSERTED)

        assert isinstance(fact.source, ClassifierInputSource)

    def test_every_source_member_is_acceptable_on_the_channel(self) -> None:
        """Derived from the enum, so a member added there is covered here too.

        Pinned this way rather than by listing members: a hand-listed set would
        pass while a newly-added source silently had no channel support.
        """
        for member in ClassifierInputSource:
            assert DeclaredFact(value=SupplyNature.GOODS, source=member).source is member


class TestTheChannelIsExtendedByFieldNotByRoute:
    """The design property that stops the next stage inventing a parallel supply."""

    def test_every_supplied_fact_the_assembly_reads_arrives_on_this_one_channel(self) -> None:
        """The assembly takes exactly one supplied-fact parameter.

        Recomputed from the real signature rather than asserted in prose: a
        second supply route added later shows up here as an extra parameter the
        channel does not own, which is the shape this gate exists to catch.
        """
        import inspect

        parameters = inspect.signature(assemble_classification_criteria).parameters
        supplied = {name for name in parameters if name.startswith("asserted_") or name == "declared"}

        assert supplied == {"declared"}, f"a second supply route appeared: {sorted(supplied)}"

    def test_a_new_fact_is_a_new_attribute_on_the_channel(self) -> None:
        """Every declared field is a DeclaredFact, so adding one needs no new plumbing."""
        annotations = DeclaredFacts.model_fields

        assert annotations, "the channel must carry at least one declared fact"
        for name in annotations:
            supplied = DeclaredFacts(**{name: DeclaredFact(value=SupplyNature.GOODS, source=_ASSERTED)})

            assert getattr(supplied, name) is not None, name


class TestTheChannelReachesTheAssembly:
    """Wiring, not just shape: a fact supplied here changes what the assembly does."""

    def test_a_declared_status_settles_a_gap_the_evidence_leaves_open(self) -> None:
        bare = assemble_classification_criteria(
            transaction_date=_DATE,
            direction=InvoiceKind.ISSUED,
            inputs=ClassifierInputs(),
            declared=DeclaredFacts(supply_nature=DeclaredFact(value=SupplyNature.GOODS, source=_ASSERTED)),
            issuer_country_code="DE",
            customer_country_code="FR",
        )
        supplied = assemble_classification_criteria(
            transaction_date=_DATE,
            direction=InvoiceKind.ISSUED,
            inputs=ClassifierInputs(),
            declared=DeclaredFacts(
                supply_nature=DeclaredFact(value=SupplyNature.GOODS, source=_ASSERTED),
                customer_tax_status=DeclaredFact(value=CustomerTaxStatus.B2C_CONSUMER, source=_ASSERTED),
            ),
            issuer_country_code="DE",
            customer_country_code="FR",
        )

        assert "customer_tax_status" in {gap.field for gap in bare.missing}
        assert "customer_tax_status" not in {gap.field for gap in supplied.missing}

    def test_a_declared_scope_settles_the_territory_a_country_code_cannot(self) -> None:
        """Spain: the code names the State while the IVA territory stays undetermined."""
        supplied = assemble_classification_criteria(
            transaction_date=_DATE,
            direction=InvoiceKind.ISSUED,
            inputs=ClassifierInputs(),
            declared=DeclaredFacts(
                supply_nature=DeclaredFact(value=SupplyNature.GOODS, source=_ASSERTED),
                customer_tax_status=DeclaredFact(value=CustomerTaxStatus.B2B_IVA_REGISTERED, source=_ASSERTED),
                issuer_scope=DeclaredFact(value=IvaTerritorialScope.ES_MAINLAND, source=_ASSERTED),
                customer_scope=DeclaredFact(value=IvaTerritorialScope.ES_MAINLAND, source=_ASSERTED),
            ),
            issuer_country_code="ES",
            customer_country_code="ES",
        )

        assert "issuer_residency" not in {gap.field for gap in supplied.missing}
        assert "customer_residency" not in {gap.field for gap in supplied.missing}
