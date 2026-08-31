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
    :class:`~application.ledger.classifier_inputs.ClassifierInputFact`
        The audit envelope that speaks the same source vocabulary.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core.classifier_input_source import ClassifierInputSource
from ....domain.iva.classification import CustomerTaxStatus, InvoiceKind, IvaTerritorialScope
from ....domain.iva.schema import IvaRateKind
from ....domain.iva.supply_nature import SupplyNature
from ..classification_assembly import (
    DeclaredFact,
    DeclaredFacts,
    assemble_classification_criteria,
)
from ..classifier_inputs import ClassifierInputFact, ClassifierInputs

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
        with pytest.raises(ValidationError, match="source"):
            DeclaredFact[SupplyNature].model_validate({"value": SupplyNature.GOODS})


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

    def test_every_declared_field_is_an_optional_attributed_fact(self) -> None:
        """Adding a fact needs an attribute, not plumbing -- asserted on the shape.

        Checked against the field annotations rather than by constructing one of
        each: the facts are typed per field, so a constructed probe would have to
        carry a value map that drifts from the model. The property that matters
        is that every field is an OPTIONAL DeclaredFact -- optional so absence
        stays absence, DeclaredFact so it cannot be supplied unattributed.
        """
        fields = DeclaredFacts.model_fields

        assert fields, "the channel must carry at least one declared fact"
        for name, info in fields.items():
            rendered = str(info.annotation)

            assert "DeclaredFact[" in rendered, f"{name} is not an attributed fact: {rendered}"
            assert info.default is None, f"{name} must default to absent, not to a value"


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
            rate_tier=IvaRateKind.GENERAL,
        )

        assert "issuer_residency" not in {gap.field for gap in supplied.missing}
        assert "customer_residency" not in {gap.field for gap in supplied.missing}


class TestTheEnvelopeRefusesLaunderedBacking:
    """A fact must be backed the way its own source can be backed, and no other.

    The source split only means anything if each member's backing is enforced.
    An operator assertion carrying a document anchor is the sharpest case: it
    would state that the page printed the very fact the operator had to supply
    BECAUSE the page did not, and an auditor sent to look at that anchor finds
    nothing. The value survives, plausibly, with a citation that does not exist.
    """

    def test_an_operator_assertion_may_not_carry_a_document_anchor(self) -> None:
        with pytest.raises(ValueError, match="must not carry a document anchor"):
            ClassifierInputFact(
                name="customer_tax_status",
                value=CustomerTaxStatus.B2C_CONSUMER.value,
                source=_ASSERTED,
                anchor="Cliente particular",
            )

    def test_an_operator_assertion_may_not_borrow_a_profile_authority(self) -> None:
        """The operator vouches for it; dressing that as the censo hides who decided."""
        with pytest.raises(ValueError, match="vouched for by the operator"):
            ClassifierInputFact(
                name="customer_tax_status",
                value=CustomerTaxStatus.B2C_CONSUMER.value,
                source=_ASSERTED,
                authority="censo",
            )

    def test_an_unbacked_operator_assertion_is_accepted(self) -> None:
        """Positive control: the refusals above are about BACKING, not the source.

        Without this, a validator rejecting every operator assertion outright
        would satisfy both refusals and the channel would be unusable.
        """
        fact = ClassifierInputFact(
            name="customer_tax_status",
            value=CustomerTaxStatus.B2C_CONSUMER.value,
            source=_ASSERTED,
        )

        assert fact.anchor is None
        assert fact.authority is None

    def test_the_document_and_profile_refusals_still_hold(self) -> None:
        """The pre-existing branches, so the third member did not displace them."""
        with pytest.raises(ValueError, match="must name the authority"):
            ClassifierInputFact(
                name="filer_iva_regime", value="general", source=ClassifierInputSource.PROFILE_AUTHORITY
            )
        with pytest.raises(ValueError, match="vouched for by its anchor"):
            ClassifierInputFact(name="x", value="y", source=_FROM_DOCUMENT, authority="censo")
