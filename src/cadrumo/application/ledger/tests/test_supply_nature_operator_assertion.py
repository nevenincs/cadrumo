"""The operator can answer the supply-nature question the classifier asks.

The classification assembly demands the nature of the supply only where the law
forks on it -- the cross-border and reverse-charge families -- and reports it as
a missing input otherwise. Until this channel existed it could REPORT that gap
and nothing could answer it: ``supply_nature`` appeared nowhere outside the
assembly, and the confirm path built its declared facts without one. So a
cross-border document printing no statutory citation reached a category of
ABSENT with no route forward for the operator.

**The provenance is the contract, not the value.** The governing decision sanctions
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
from ....domain.iva import (
    InvoiceKind,
    IvaCategory,
    IvaTerritorialScope,
    SupplyNature,
    supply_nature_implied_by_category,
)
from ...ledger._classification_assembly import DeclaredFact
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


# -- the OTHER sanctioned source, which nothing read ------------------------
#
# Two sources are sanctioned for this axis and the suite above covered
# one. The citation axis was fully built, exported on the domain facade and
# covered by its own suite -- and had NO production caller, so the gap message
# telling an operator that a printed statutory citation settles this named a
# route that could not fire. A document printing an art. 21 exemption asked
# them anyway.
#
# The provenance is again the contract. A citation is established by the PAGE,
# so it is stamped DOCUMENT_EVIDENCE: an auditor asking why this record says
# goods is sent to the printed article, not to a person. A wiring that reused
# the operator stamp would pass every value check while telling the auditor to
# go and ask someone about a fact the document states.

#: Prints an article the table reads, and it establishes GOODS by the law's own
#: definition -- art. 21 exempts "las entregas de bienes expedidos o
#: transportados fuera de la Comunidad".
_GOODS_CITATION = "Exencion art. 21 LIVA"


def test_a_printed_citation_now_settles_the_nature() -> None:
    """The measured gap: this route existed and could not fire."""
    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        printed_citation=_GOODS_CITATION,
    )

    assert declared.supply_nature is not None, "the printed citation did not reach the criteria"
    assert declared.supply_nature.value is SupplyNature.GOODS


def test_a_citation_derived_nature_is_backed_by_the_page_not_by_a_person() -> None:
    """The provenance contract, and the reason a value-only check is insufficient.

    An auditor asking why this record says goods must be sent to the printed
    article. Reusing the operator stamp would make the document's own statement
    indistinguishable from somebody vouching for it.
    """
    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        printed_citation=_GOODS_CITATION,
    )

    assert declared.supply_nature is not None
    assert declared.supply_nature.source is ClassifierInputSource.DOCUMENT_EVIDENCE


@pytest.mark.parametrize("kind", [InvoiceKind.ISSUED, InvoiceKind.RECEIVED])
def test_the_citation_is_direction_independent_like_the_assertion(kind: InvoiceKind) -> None:
    """The supply's own property still does not swap sides when the filer does."""
    declared = _declared_facts(
        kind=kind,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        printed_citation=_GOODS_CITATION,
    )

    assert declared.supply_nature is not None, f"the citation did not reach the criteria on {kind}"
    assert declared.supply_nature.value is SupplyNature.GOODS


def test_the_operators_own_answer_beats_the_printed_citation() -> None:
    """They hold the document and can see a mention the reader mis-transcribed.

    So an assertion is a CORRECTION rather than a duplicate, and it must win --
    including its provenance, because the record should say a person vouched
    for this rather than that the page did.
    """
    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        supply_nature=SupplyNature.SERVICES,
        printed_citation=_GOODS_CITATION,
    )

    assert declared.supply_nature is not None
    assert declared.supply_nature.value is SupplyNature.SERVICES
    assert declared.supply_nature.source is ClassifierInputSource.OPERATOR_ASSERTION


@pytest.mark.parametrize(
    "printed",
    [None, "", "Factura sujeta al regimen general", "Inversion del sujeto pasivo, art. 84 LIVA"],
    ids=["no-legend", "empty-legend", "no-article-cited", "article-establishing-nothing"],
)
def test_a_document_establishing_nothing_still_leaves_the_axis_open(printed: str | None) -> None:
    """The precision half, and the ordinary outcome for the domestic majority.

    A domestic invoice is obliged to cite no article at all, and art. 84's
    sub-rules reach goods and services alike -- the table records it as
    establishing nothing rather than omitting it, so a caller can see it was
    read. Neither may be turned into a nature.
    """
    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        printed_citation=printed,
    )

    assert declared.supply_nature is None


def test_reading_the_citation_is_what_settles_it() -> None:
    """Mutation proof: without the derivation the citing document asks again.

    Re-runs the pre-change builder, which consulted only the operator's answer.
    It leaves the axis open on a document that plainly cites art. 21 -- which is
    the dormant route this closes. Without this the suite would prove a nature
    ARRIVES, not that reading the citation is what produced it.
    """
    without_citation = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
    )
    with_citation = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        printed_citation=_GOODS_CITATION,
    )

    assert without_citation.supply_nature is None
    assert with_citation.supply_nature is not None


# -- the THIRD route: what the category itself rests on ---------------------
#
# A category is grounded in specific LIVA articles, and some of those DEFINE the
# operation as one of goods -- an entrega intracomunitaria is exempt under
# art. 25, which exempts "las entregas de bienes definidas en el articulo 8". So
# an operator asked goods-or-services about one is being asked a question the
# law has already answered, with no citation needing to be printed at all.
#
# Two existing authorities are JOINED and nothing new is ruled: the component
# table already declares which articles ground each category, and the citation
# table already declares what each article establishes, each row with its
# corpus_ref. That is what keeps a second category-keyed table -- a rival
# authority on one question -- from existing.


def _stated(category: IvaCategory) -> DeclaredFact[IvaCategory]:
    """The category as a document record declares it."""
    return DeclaredFact(value=category, source=ClassifierInputSource.DOCUMENT_EVIDENCE)


def test_a_declared_category_settles_the_nature_with_nothing_printed() -> None:
    """The population this closes: cross-border documents citing no article."""
    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=_stated(IvaCategory.INTRA_COMMUNITY_SUPPLY),
    )

    assert declared.supply_nature is not None, "the declared category did not settle the nature"
    assert declared.supply_nature.value is SupplyNature.GOODS
    assert declared.supply_nature.source is ClassifierInputSource.DOCUMENT_EVIDENCE


@pytest.mark.parametrize(
    "category",
    [IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED, IvaCategory.DOMESTIC_REVERSE_CHARGE],
    ids=["assimilated-exports-art-22", "domestic-reverse-charge-art-84"],
)
def test_a_category_whose_law_reaches_both_limbs_stays_open(category: IvaCategory) -> None:
    """The two traps, and the reason this is a join rather than a hand-written map.

    LIVA art. 22 covers "las entregas, construcciones, transformaciones,
    reparaciones, mantenimiento, fletamento... y arrendamiento" -- services as
    much as goods -- so a map that treated the export family uniformly would
    assert GOODS on service exports. Art. 84 reaches both limbs likewise.
    Neither may produce a nature, and neither does: art. 22 has no row in the
    citation table because nothing ever ruled what it establishes, and art. 84's
    row establishes nothing on purpose.
    """
    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=_stated(category),
    )

    assert declared.supply_nature is None


def test_the_traps_are_excluded_by_the_tables_rather_than_by_a_special_case() -> None:
    """Anchor: the safety is structural, so it survives someone editing this file.

    If a row for art. 22 is ever added to the citation table, this fails here
    rather than silently starting to assert a nature on service exports.
    """
    assert supply_nature_implied_by_category(IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED).nature is None
    assert supply_nature_implied_by_category(IvaCategory.DOMESTIC_REVERSE_CHARGE).nature is None


def test_a_printed_citation_outranks_the_category_it_disagrees_with() -> None:
    """The page is more specific than the family.

    A document citing an article states something about ITSELF; the category
    states what its family rests on. So a services citation beats a goods
    category rather than contradicting it into silence.
    """
    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=_stated(IvaCategory.INTRA_COMMUNITY_SUPPLY),
        printed_citation="Exencion art. 163 octiesdecies LIVA",
    )

    assert declared.supply_nature is not None
    assert declared.supply_nature.value is SupplyNature.SERVICES


def test_the_operator_still_outranks_both_derivations() -> None:
    """The precedence holds all the way down, provenance included."""
    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=_stated(IvaCategory.INTRA_COMMUNITY_SUPPLY),
        supply_nature=SupplyNature.SERVICES,
    )

    assert declared.supply_nature is not None
    assert declared.supply_nature.value is SupplyNature.SERVICES
    assert declared.supply_nature.source is ClassifierInputSource.OPERATOR_ASSERTION


def test_the_category_join_is_what_settles_it() -> None:
    """Mutation proof: without the category route the same document asks again.

    Re-runs the builder with no category declared, which is the pre-change
    input. It leaves the axis open on an operation whose own exemption article
    defines it as goods.
    """
    without_category = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
    )
    with_category = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=_stated(IvaCategory.INTRA_COMMUNITY_SUPPLY),
    )

    assert without_category.supply_nature is None
    assert with_category.supply_nature is not None


# -- the proposal is made where the transcription is, and decides nothing ----
#
# The governing amendment permits a model to PRE-SUGGEST the nature, and the
# input it named -- the line descriptions -- does not exist on the lane that
# needs it: only the structured reader populates a line decomposition, and a
# text- or vision-read draft keeps raw_text_length, a number, not the text.
#
# So the proposal is made at the reading stage where the transcription is still
# in hand, opt-in, and it never reaches the classifier: the value that does is
# the one the operator states at confirm.


def test_the_draft_carries_a_proposal_that_is_not_an_extracted_field() -> None:
    """A judgement, not a transcription, so it lives outside the anchor contract.

    An extracted field must be anchorable to a printed form. A proposal has no
    printed form to point at, so folding it into the extraction contract would
    put an unanchorable value inside the model whose whole guarantee is that
    values are copied.
    """
    from ...ledger._evidence_draft import InvoiceDraft

    assert "proposed_supply_nature" in InvoiceDraft.model_fields
    assert InvoiceDraft().proposed_supply_nature is None


def test_a_proposal_does_not_reach_the_classifier_on_its_own() -> None:
    """The load-bearing separation: a proposal nobody confirmed has no effect.

    The declared facts are built from the operator's answer and the document's
    own statements. A draft carrying a proposal and nothing else must leave the
    axis exactly as open as one carrying none, or the model would be deciding
    through a channel labelled as the operator's.
    """
    from ...ledger._evidence_draft import InvoiceDraft

    proposed = InvoiceDraft(proposed_supply_nature=SupplyNature.SERVICES)

    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        printed_citation=proposed.regime_legend,
    )

    assert proposed.proposed_supply_nature is SupplyNature.SERVICES
    assert declared.supply_nature is None, "a proposal nobody confirmed reached the criteria"


def test_the_operators_answer_is_what_the_classifier_consumes() -> None:
    """The other half: confirming is what makes a value an input.

    Together with the case above this is the whole contract -- unconfirmed
    reaches nothing, confirmed reaches the classifier as the operator's own
    assertion.
    """
    declared = _declared_facts(
        kind=InvoiceKind.ISSUED,
        counterparty=_counterparty(),
        filer_scope=IvaTerritorialScope.ES_MAINLAND,
        stated_category=None,
        supply_nature=SupplyNature.SERVICES,
    )

    assert declared.supply_nature is not None
    assert declared.supply_nature.value is SupplyNature.SERVICES
    assert declared.supply_nature.source is ClassifierInputSource.OPERATOR_ASSERTION
