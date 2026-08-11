"""The operator can answer the supply-nature question the classifier asks.

The classification assembly demands the nature of the supply only where the law
forks on it -- the cross-border and reverse-charge families -- and reports it as
a missing input otherwise. Until this channel existed it could REPORT that gap
and nothing could answer it: ``supply_nature`` appeared nowhere outside the
assembly, and the confirm path built its declared facts without one. So a
cross-border document printing no statutory citation reached a category of
ABSENT with no route forward for the operator.

**The provenance is the contract, not the value.** The governing ADR sanctions
exactly two sources for this axis: a printed statutory citation, which decides
by law because an article number is a closed legal vocabulary, and an explicit
operator assertion. Both are facts about who established the answer, and they
must not arrive looking alike -- so the assertion is stamped ``OPERATOR``
rather than any evidence provenance, and a test that only checked the VALUE
would pass on a wiring that laundered a model's guess into the classifier.

**Direction-independent, unlike every other fact the builder places.** Goods or
services is a property of the supply, so it does not swap sides when the filer
does. The two directions are asserted separately here because the builder's
whole job is swapping the party facts around them, and a nature that rode along
with the scopes would be silently wrong on exactly one direction.
"""

from __future__ import annotations

import pytest

from ....core import ClassifierInputSource
from ....domain.iva import InvoiceKind, IvaTerritorialScope, SupplyNature
from ...ledger._confirm_establishment import _declared_facts
from ...ledger._establishment_ladder import CounterpartyEstablishment

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _counterparty() -> CounterpartyEstablishment:
    """A counterparty whose territory resolved, so the nature is the only variable."""
    return CounterpartyEstablishment(scope=IvaTerritorialScope.EU_MEMBER)


@pytest.mark.parametrize("kind", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
@pytest.mark.parametrize("nature", [SupplyNature.GOODS, SupplyNature.SERVICES])
def test_the_assertion_reaches_the_classifier_on_either_direction(
    kind: InvoiceKind,
    nature: SupplyNature,
) -> None:
    """Both members, both directions: the supply's own property does not swap sides."""
    declared = _declared_facts(
        kind=kind,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        supply_nature=nature,
    )

    assert declared.supply_nature is not None, f"the assertion did not reach the criteria on {kind}"
    assert declared.supply_nature.value is nature


@pytest.mark.parametrize("kind", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
def test_the_assertion_is_stamped_operator_and_not_an_evidence_provenance(kind: InvoiceKind) -> None:
    """The half a value-only assertion would miss.

    A wiring that carried the right answer under a document or profile
    provenance would satisfy every check about the VALUE while laundering the
    operator's claim into something that reads as read-off-the-page. The
    classifier's inputs are facts about who established them.
    """
    declared = _declared_facts(
        kind=kind,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        supply_nature=SupplyNature.SERVICES,
    )

    assert declared.supply_nature is not None
    assert declared.supply_nature.source is ClassifierInputSource.OPERATOR_ASSERTION, (
        "an operator's answer must not arrive stamped as document or profile evidence"
    )


@pytest.mark.parametrize("kind", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
def test_no_assertion_leaves_the_axis_unstated_rather_than_defaulted(kind: InvoiceKind) -> None:
    """The precision half, and the one that protects the lazy demand.

    An operator who says nothing must leave the axis UNSTATED, so the assembly
    can still report it as a gap on the branches that need it. Defaulting to
    either member would answer for them -- and goods is the tempting default
    precisely because it is the commoner case, which is what would make the
    wrong answer invisible.
    """
    declared = _declared_facts(
        kind=kind,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
    )

    assert declared.supply_nature is None, "an unanswered axis must stay unanswered, never default"
